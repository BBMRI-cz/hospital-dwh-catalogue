"""Views for ticketing cart and submission flows."""

from __future__ import annotations

from dataclasses import replace

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView, View

from ticketing.cart import CartService
from ticketing.services.ticketing_service import TicketingService
from ticketing.view_helpers import (
    build_cart_page_context,
    get_cart_toggle_request,
    get_safe_redirect_target,
    render_cart_toggle_response,
    resolve_cart_dataset,
)


class TicketSubmitForm(forms.Form):
    description = forms.CharField(
        required=True,
        label=_('Request description'),
        widget=forms.Textarea(
            attrs={
                'class': 'w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:border-[#53c0d7] focus:outline-none focus:ring-2 focus:ring-[#53c0d7]/20 transition resize-none',
                'rows': 4,
                'placeholder': _('Describe your request...'),
            }
        ),
    )


class CartAddView(LoginRequiredMixin, View):
    """POST: add a dataset to the session cart."""

    def post(self, request):
        toggle_request = get_cart_toggle_request(request)
        in_cart = False
        dataset = resolve_cart_dataset(toggle_request)
        if dataset is not None:
            canonical_title = dataset.title or dataset.name
            in_cart = CartService.toggle(
                request.session,
                dataset.app,
                dataset.name,
                canonical_title,
            )
            toggle_request = replace(
                toggle_request,
                app=dataset.app,
                name=dataset.name,
                title=canonical_title,
            )
        if request.headers.get('HX-Request'):
            return render_cart_toggle_response(request, toggle_request)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(
                {
                    'success': True,
                    'in_cart': in_cart,
                    'cart_count': CartService.count(request.session),
                }
            )
        return redirect(get_safe_redirect_target(request))


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
        return render(
            request,
            self.template_name,
            build_cart_page_context(request.session, TicketSubmitForm()),
        )

    def post(self, request):
        cart = CartService.get(request.session)
        form = TicketSubmitForm(request.POST)

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                build_cart_page_context(request.session, form),
            )

        svc = TicketingService()
        ticket = svc.create_ticket_from_cart(
            user=request.user,
            description=form.cleaned_data.get('description', ''),
            cart=cart,
            session_key=request.session.session_key,
        )

        try:
            ticket_id = svc.submit_ticket(ticket, cart)
            CartService.clear(request.session)
            if ticket_id:
                messages.success(
                    request,
                    str(_('Your request has been submitted - ticket #%(ticket_id)s'))
                    % {'ticket_id': ticket_id},
                )
            else:
                messages.success(request, _('Your request has been submitted.'))
        except Exception:
            messages.error(
                request,
                _(
                    'Submission to the ticketing system failed. Your request has been saved and our team will follow up.'
                ),
            )

        return redirect('ticketing:ticket_history')


class TicketHistoryView(LoginRequiredMixin, ListView):
    """List of the current user's past ticket requests."""

    template_name = 'ticketing/history.html'
    context_object_name = 'tickets'
    paginate_by = 25

    def get_queryset(self):
        return TicketingService.get_user_tickets(self.request.user)
