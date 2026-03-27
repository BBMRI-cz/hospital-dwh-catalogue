"""
Views for the ticketing application.

Provides cart management, ticket submission, and ticket viewing functionality.
"""

from __future__ import annotations

import logging

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView, View

from ticketing.cart import CartService
from ticketing.models import TicketRequest, TicketRequestItem
from ticketing.services.base import TicketData
from ticketing.services.factory import get_ticket_service

logger = logging.getLogger(__name__)


# ── Forms ─────────────────────────────────────────────────────────────────────


class TicketSubmitForm(forms.Form):
    description = forms.CharField(
        required=True,
        label=_('Request description'),
        widget=forms.Textarea(
            attrs={
                'class': 'w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:border-[#53c0d7] focus:outline-none focus:ring-2 focus:ring-[#53c0d7]/20 transition resize-none',
                'rows': 4,
                'placeholder': _('Describe your request…'),
            }
        ),
    )


# ── Cart views ────────────────────────────────────────────────────────────────


class CartAddView(LoginRequiredMixin, View):
    """POST: add a dataset to the session cart."""

    def post(self, request):
        app = request.POST.get('app', '')
        name = request.POST.get('name', '')
        title = request.POST.get('title', '')
        in_cart = False
        if app and name:
            cart = CartService.get(request.session)
            already_in = any(i['app'] == app and i['name'] == name for i in cart)
            if already_in:
                CartService.remove(request.session, app, name)
                in_cart = False
            else:
                CartService.add(request.session, app, name, title)
                in_cart = True
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(
                {
                    'success': True,
                    'in_cart': in_cart,
                    'cart_count': CartService.count(request.session),
                }
            )
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
        return redirect(next_url)


class CartRemoveView(LoginRequiredMixin, View):
    """POST: remove a dataset from the session cart."""

    def post(self, request):
        app = request.POST.get('app', '')
        name = request.POST.get('name', '')
        if app and name:
            CartService.remove(request.session, app, name)
        return redirect('ticketing:cart')


class CartView(LoginRequiredMixin, View):
    """Cart review + ticket submission form."""

    template_name = 'ticketing/cart.html'

    def get(self, request):
        cart = CartService.get(request.session)
        form = TicketSubmitForm()
        return render(request, self.template_name, {'cart': cart, 'form': form})

    def post(self, request):
        cart = CartService.get(request.session)
        form = TicketSubmitForm(request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {'cart': cart, 'form': form})

        # Create TicketRequest
        dataset_names = ', '.join(item['title'] for item in cart)
        auto_subject = (
            (str(_('Data access request')) + f' \u2014 {dataset_names}')
            if dataset_names
            else str(_('Data access request'))
        )[:500]
        ticket = TicketRequest.objects.create(
            requester_email=request.user.email,
            requester_name=request.user.get_full_name() or request.user.username,
            subject=auto_subject,
            description=form.cleaned_data.get('description', ''),
            status=TicketRequest.Status.DRAFT,
            session_key=request.session.session_key,
        )
        logger.info(
            'TicketRequest created: pk=%s user=%s items=%d',
            ticket.pk, request.user, len(cart),
        )

        for item in cart:
            TicketRequestItem.objects.create(
                ticket_request=ticket,
                item_type=TicketRequestItem.ItemType.DATASET,
                item_id=f'{item["app"]}/{item["name"]}',
                item_name=item['title'],
                parent_dataset=item['name'],
            )

        # Submit to Alvao
        try:
            service = get_ticket_service()
            ticket_data = TicketData(
                subject=ticket.subject,
                description=_build_ticket_description(ticket, cart),
                requester_email=ticket.requester_email,
                requester_name=ticket.requester_name,
            )
            response = service.create_ticket(ticket_data)
            ticket.alvao_ticket_id = response.ticket_id
            ticket.status = TicketRequest.Status.SUBMITTED
            ticket.submitted_at = timezone.now()
            ticket.save()
            logger.info(
                'Ticket submitted to Alvao: local_pk=%s alvao_id=%s user=%s',
                ticket.pk, response.ticket_id, request.user,
            )
            CartService.clear(request.session)
            ticket_id = response.ticket_id or ''
            if ticket_id:
                messages.success(
                    request,
                    str(_('Your request has been submitted \u2014 ticket #%(ticket_id)s'))
                    % {'ticket_id': ticket_id},
                )
            else:
                messages.success(request, _('Your request has been submitted.'))
        except Exception:
            logger.exception(
                'Ticket submission failed for ticket pk=%s user=%s', ticket.pk, request.user
            )
            ticket.status = TicketRequest.Status.FAILED
            ticket.save()
            messages.error(
                request,
                _(
                    'Submission to the ticketing system failed. Your request has been saved and our team will follow up.'
                ),
            )

        return redirect('ticketing:ticket_history')


def _build_ticket_description(ticket: TicketRequest, cart: list[dict]) -> str:
    lines = [ticket.description]
    if cart:
        lines += ['', '--- Requested datasets ---']
        for item in cart:
            lines.append(f'  [{item["app"]}] {item["title"]} ({item["name"]})')
    return '\n'.join(lines)


# ── History view ──────────────────────────────────────────────────────────────


class TicketHistoryView(LoginRequiredMixin, ListView):
    """List of the current user's past ticket requests."""

    template_name = 'ticketing/history.html'
    context_object_name = 'tickets'
    paginate_by = 25

    def get_queryset(self):
        return (
            TicketRequest.objects.filter(requester_email=self.request.user.email)
            .prefetch_related('items')
            .order_by('-created_at')
        )
