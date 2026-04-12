"""
Views for the ticketing application.

Provides cart management, ticket submission, and ticket viewing functionality.
"""

from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView, View

from ticketing.cart import CartService
from ticketing.services.ticketing_service import TicketingService

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
        if request.headers.get('HX-Request'):
            cart_count = CartService.count(request.session)
            cart_dataset_ids = {item['name'] for item in CartService.get(request.session)}
            btn_style = request.POST.get('btn_style', 'hero')
            template = (
                'includes/_cart_inline_btn.html'
                if btn_style == 'inline'
                else 'includes/_cart_add_btn.html'
            )
            ctx_key = 'cart_app' if btn_style == 'inline' else 'cart_source'
            btn_html = render_to_string(
                template,
                {
                    ctx_key: app,
                    'cart_name': name,
                    'cart_title': title,
                    'cart_dataset_ids': cart_dataset_ids,
                },
                request=request,
            )
            badge_visibility = '' if cart_count else ' hidden'
            oob_badge = (
                f'<span id="cart-badge" hx-swap-oob="outerHTML"'
                f' class="absolute -top-1 -right-1 flex items-center justify-center'
                f' rounded-full text-white font-mono font-bold text-[9px] bg-mou-orange{badge_visibility}"'
                f' style="min-width:15px;height:15px;padding:0 3px;">{cart_count}</span>'
            )
            return HttpResponse(btn_html + oob_badge)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(
                {
                    'success': True,
                    'in_cart': in_cart,
                    'cart_count': CartService.count(request.session),
                }
            )
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
        if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            next_url = '/'
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
                    str(_('Your request has been submitted \u2014 ticket #%(ticket_id)s'))
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


# ── History view ──────────────────────────────────────────────────────────────


class TicketHistoryView(LoginRequiredMixin, ListView):
    """List of the current user's past ticket requests."""

    template_name = 'ticketing/history.html'
    context_object_name = 'tickets'
    paginate_by = 25

    def get_queryset(self):
        return TicketingService.get_user_tickets(self.request.user)
