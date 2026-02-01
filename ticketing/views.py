"""
Views for the ticketing application.

Provides cart management, ticket submission, and ticket viewing functionality.
"""

import contextlib
import logging
from typing import Any

from django.contrib import messages
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import (
    DetailView,
    FormView,
    ListView,
    TemplateView,
)

from warehouse.models import DataclassList, DatasetList, DbTableList

from .forms import TicketSubmitForm
from .models import TicketRequest, TicketRequestItem
from .services.alvao_service import AlvaoServiceException
from .services.base import TicketData
from .services.factory import get_ticket_service

logger = logging.getLogger(__name__)


class CartMixin:
    """Mixin for cart-related functionality."""

    def get_or_create_cart(self, request: HttpRequest) -> TicketRequest:
        """
        Get or create a cart (draft ticket request) for the current session.

        Args:
            request: HTTP request with session

        Returns:
            TicketRequest in draft status
        """
        # Ensure session exists
        if not request.session.session_key:
            request.session.create()

        session_key = request.session.session_key

        # Try to find existing draft cart
        cart = TicketRequest.objects.filter(
            session_key=session_key, status=TicketRequest.Status.DRAFT
        ).first()

        if not cart:
            cart = TicketRequest.objects.create(
                session_key=session_key,
                status=TicketRequest.Status.DRAFT,
                subject=_('Data Access Request'),
                requester_email='',
            )

        return cart

    def get_cart_count(self, request: HttpRequest) -> int:
        """Get the number of items in the current cart."""
        if not request.session.session_key:
            return 0

        cart = TicketRequest.objects.filter(
            session_key=request.session.session_key, status=TicketRequest.Status.DRAFT
        ).first()

        return cart.item_count if cart else 0


class CartView(CartMixin, TemplateView):
    """View the current cart contents."""

    template_name = 'ticketing/cart.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Add cart data to context."""
        context = super().get_context_data(**kwargs)

        cart = self.get_or_create_cart(self.request)
        context['cart'] = cart
        context['items'] = cart.items.all()
        context['form'] = TicketSubmitForm(
            initial={
                'subject': cart.subject,
                'description': cart.description,
                'requester_email': cart.requester_email,
                'requester_name': cart.requester_name,
            }
        )

        return context


class AddToCartView(CartMixin, View):
    """Toggle an item in the cart (add if not present, remove if present)."""

    def post(self, request: HttpRequest) -> HttpResponse:
        """Handle POST request to toggle item in cart."""
        item_type = request.POST.get('item_type')
        item_id = request.POST.get('item_id')

        if not item_type or not item_id:
            return JsonResponse(
                {'success': False, 'error': _('Missing item type or ID')}, status=400
            )

        # Validate item type
        if item_type not in [choice[0] for choice in TicketRequestItem.ItemType.choices]:
            return JsonResponse({'success': False, 'error': _('Invalid item type')}, status=400)

        # Get or create cart
        cart = self.get_or_create_cart(request)

        # Check if item already in cart - if so, remove it
        existing = cart.items.filter(item_type=item_type, item_id=item_id).first()
        if existing:
            existing.delete()
            logger.info(f"Removed {item_type} '{item_id}' from cart {cart.pk}")
            return JsonResponse(
                {
                    'success': True,
                    'action': 'removed',
                    'message': _('Item removed from cart'),
                    'cart_count': cart.item_count,
                }
            )

        # Get item details from warehouse models
        try:
            item_name, item_description, parent_dataset = self._get_item_details(item_type, item_id)
        except Exception as e:
            logger.error(f'Error fetching item details: {e}')
            return JsonResponse({'success': False, 'error': str(e)}, status=404)

        # Add item to cart
        TicketRequestItem.objects.create(
            ticket_request=cart,
            item_type=item_type,
            item_id=item_id,
            item_name=item_name,
            item_description=item_description,
            parent_dataset=parent_dataset,
        )

        logger.info(f"Added {item_type} '{item_id}' to cart {cart.pk}")

        return JsonResponse(
            {
                'success': True,
                'action': 'added',
                'message': _('Item added to cart'),
                'cart_count': cart.item_count,
            }
        )

    def _get_item_details(self, item_type: str, item_id: str) -> tuple[str, str, str]:
        """
        Get details for an item from warehouse models.

        Returns:
            Tuple of (name, description, parent_dataset_id)
        """
        if item_type == TicketRequestItem.ItemType.DATASET:
            item = get_object_or_404(DatasetList, pk=item_id)
            return item.display_name, item.description or '', ''

        elif item_type == TicketRequestItem.ItemType.DATACLASS:
            item = get_object_or_404(DataclassList, pk=item_id)
            parent = item.data_set.data_set if item.data_set else ''
            return item.display_name, item.description or '', parent

        elif item_type == TicketRequestItem.ItemType.TABLE:
            item = get_object_or_404(DbTableList, pk=item_id)
            parent = ''
            if item.data_class and item.data_class.data_set:
                parent = item.data_class.data_set.data_set
            return item.display_name, item.description or '', parent

        raise ValueError(f'Unknown item type: {item_type}')


class RemoveFromCartView(CartMixin, View):
    """Remove an item from the cart."""

    def post(self, request: HttpRequest, item_id: int) -> HttpResponse:
        """Handle POST request to remove item from cart."""
        cart = self.get_or_create_cart(request)

        try:
            item = cart.items.get(pk=item_id)
            item.delete()
            logger.info(f'Removed item {item_id} from cart {cart.pk}')

            return JsonResponse(
                {
                    'success': True,
                    'message': _('Item removed from cart'),
                    'cart_count': cart.item_count,
                }
            )
        except TicketRequestItem.DoesNotExist:
            return JsonResponse(
                {'success': False, 'error': _('Item not found in cart')}, status=404
            )


class ClearCartView(CartMixin, View):
    """Clear all items from the cart."""

    def post(self, request: HttpRequest) -> HttpResponse:
        """Handle POST request to clear the cart."""
        cart = self.get_or_create_cart(request)
        cart.items.all().delete()

        logger.info(f'Cleared cart {cart.pk}')

        return JsonResponse({'success': True, 'message': _('Cart cleared'), 'cart_count': 0})


class SubmitCartView(CartMixin, FormView):
    """Submit the cart as a ticket to Alvao."""

    template_name = 'ticketing/cart.html'
    form_class = TicketSubmitForm
    success_url = reverse_lazy('ticketing:ticket_submitted')

    def form_valid(self, form: TicketSubmitForm) -> HttpResponse:
        """Process form and submit ticket to Alvao."""
        cart = self.get_or_create_cart(self.request)

        if cart.item_count == 0:
            messages.error(self.request, _('Your cart is empty.'))
            return redirect('ticketing:cart')

        # Update cart with form data
        cart.subject = form.cleaned_data['subject']
        cart.description = form.cleaned_data['description']
        cart.requester_email = form.cleaned_data['requester_email']
        cart.requester_name = form.cleaned_data.get('requester_name', '')

        # Build ticket description with items
        full_description = self._build_ticket_description(cart)

        # Create ticket data
        ticket_data = TicketData(
            subject=cart.subject,
            description=full_description,
            requester_email=cart.requester_email,
            requester_name=cart.requester_name,
        )

        # Submit to Alvao
        try:
            service = get_ticket_service()
            response = service.create_ticket(ticket_data)

            # Update cart with Alvao response
            cart.alvao_ticket_id = response.ticket_id
            cart.alvao_response = response.raw_response  # type: ignore[assignment]
            cart.status = TicketRequest.Status.SUBMITTED
            cart.submitted_at = timezone.now()
            cart.save()

            logger.info(f'Submitted ticket {response.ticket_id} for {cart.requester_email}')

            # Store ticket ID in session for success page
            self.request.session['submitted_ticket_id'] = cart.pk

            messages.success(
                self.request,
                _('Your request has been submitted successfully. Ticket ID: %(ticket_id)s')
                % {'ticket_id': response.ticket_id},
            )

            return super().form_valid(form)

        except AlvaoServiceException as e:
            logger.error(f'Failed to submit ticket: {e}')
            cart.status = TicketRequest.Status.FAILED
            cart.alvao_response = {'error': str(e)}  # type: ignore[assignment]
            cart.save()

            messages.error(
                self.request,
                _('Failed to submit your request. Please try again later. Error: %(error)s')
                % {'error': str(e)},
            )
            return redirect('ticketing:cart')

    def form_invalid(self, form: TicketSubmitForm) -> HttpResponse:
        """Handle invalid form submission."""
        messages.error(self.request, _('Please correct the errors below.'))
        return super().form_invalid(form)

    def _build_ticket_description(self, cart: TicketRequest) -> str:
        """Build the full ticket description including all items."""
        lines = []

        if cart.description:
            lines.append(cart.description)
            lines.append('')
            lines.append('---')
            lines.append('')

        lines.append(_('Requested Data Items:'))
        lines.append('')

        for item in cart.items.all():
            item_type_display = TicketRequestItem.ItemType(item.item_type).label
            lines.append(f'• [{item_type_display}] {item.item_name} (ID: {item.item_id})')
            if item.item_description:
                lines.append(f'  {item.item_description[:200]}...')
            if item.parent_dataset:
                lines.append(f'  Dataset: {item.parent_dataset}')
            lines.append('')

        return '\n'.join(str(line) for line in lines)


class TicketSubmittedView(TemplateView):
    """Success page after ticket submission."""

    template_name = 'ticketing/ticket_submitted.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Add submitted ticket data to context."""
        context = super().get_context_data(**kwargs)

        ticket_id = self.request.session.get('submitted_ticket_id')
        if ticket_id:
            with contextlib.suppress(TicketRequest.DoesNotExist):
                context['ticket'] = TicketRequest.objects.get(pk=ticket_id)

        return context


class MyTicketsView(ListView):
    """View tickets submitted by the current user."""

    template_name = 'ticketing/my_tickets.html'
    context_object_name = 'tickets'
    paginate_by = 20

    def get_queryset(self) -> QuerySet[TicketRequest]:
        """Get tickets for the provided email."""
        email = self.request.GET.get('email', '').strip()

        if not email:
            return TicketRequest.objects.none()

        # Get local tickets
        local_tickets = TicketRequest.objects.filter(
            requester_email__iexact=email,
            status__in=[TicketRequest.Status.SUBMITTED, TicketRequest.Status.CONFIRMED],
        ).order_by('-submitted_at')

        return local_tickets

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Add extra context."""
        context = super().get_context_data(**kwargs)
        context['search_email'] = self.request.GET.get('email', '')

        # Try to fetch remote tickets from Alvao
        email = self.request.GET.get('email', '').strip()
        if email:
            try:
                service = get_ticket_service()
                context['remote_tickets'] = service.get_tickets_by_requester(email)
            except AlvaoServiceException as e:
                logger.warning(f'Could not fetch remote tickets: {e}')
                context['remote_error'] = str(e)

        return context


class TicketDetailView(DetailView):
    """View details of a specific ticket."""

    model = TicketRequest
    template_name = 'ticketing/ticket_detail.html'
    context_object_name = 'ticket'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Add Alvao ticket info if available."""
        context = super().get_context_data(**kwargs)

        ticket: TicketRequest = self.get_object()  # type: ignore[assignment]
        if ticket.alvao_ticket_id:
            try:
                service = get_ticket_service()
                context['alvao_info'] = service.get_ticket(ticket.alvao_ticket_id)
            except AlvaoServiceException as e:
                logger.warning(f'Could not fetch Alvao ticket info: {e}')
                context['alvao_error'] = str(e)

        return context


class CartCountView(CartMixin, View):
    """API endpoint to get current cart count."""

    def get(self, request: HttpRequest) -> JsonResponse:
        """Return current cart count."""
        return JsonResponse({'count': self.get_cart_count(request)})


class CartItemsView(CartMixin, View):
    """API endpoint to get list of item IDs in cart."""

    def get(self, request: HttpRequest) -> JsonResponse:
        """Return list of items in cart with their type and ID."""
        cart = self.get_or_create_cart(request)
        items = list(cart.items.values_list('item_type', 'item_id'))
        return JsonResponse(
            {
                'items': [{'type': item_type, 'id': item_id} for item_type, item_id in items],
                'count': len(items),
            }
        )
