"""
Models for the ticketing application.

Stores ticket requests and cart items locally before sending to Alvao.
"""

from typing import TYPE_CHECKING

from django.apps import apps as django_apps
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from django.db.models import Manager


class TicketRequest(models.Model):
    """
    Represents a ticket request to be sent to Alvao Service Desk.

    Stores the request locally with all items before submission,
    and tracks the Alvao ticket ID after successful submission.
    """

    class Status(models.TextChoices):
        """Ticket request status choices."""

        DRAFT = 'draft', _('Draft')
        SUBMITTED = 'submitted', _('Submitted')
        CONFIRMED = 'confirmed', _('Confirmed by Alvao')
        FAILED = 'failed', _('Submission Failed')

    # Requester information
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='ticket_requests',
        verbose_name=_('Requester'),
        db_constraint=False,
    )
    requester_email = models.EmailField(
        verbose_name=_('Requester Email'), help_text=_('Email of the person requesting data access')
    )
    requester_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Requester Name'),
        help_text=_('Full name of the requester'),
    )

    # Ticket content
    subject = models.CharField(
        max_length=500, verbose_name=_('Subject'), help_text=_('Ticket subject/title')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Additional details or notes for the request'),
    )

    # Status tracking
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT, verbose_name=_('Status')
    )

    # Alvao integration
    alvao_ticket_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('Alvao Ticket ID'),
        help_text=_('Ticket ID returned by Alvao after submission'),
    )
    alvao_response = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_('Alvao Response'),
        help_text=_('Full response from Alvao API'),
    )

    # Session tracking (for anonymous users)
    session_key = models.CharField(
        max_length=40,
        blank=True,
        null=True,
        db_index=True,
        verbose_name=_('Session Key'),
        help_text=_('Session key for tracking cart before submission'),
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created At'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Updated At'))
    submitted_at = models.DateTimeField(blank=True, null=True, verbose_name=_('Submitted At'))

    class Meta:
        db_table = 'ticketing_ticket_request'
        verbose_name = _('Ticket Request')
        verbose_name_plural = _('Ticket Requests')
        ordering = ['-created_at']

    # Type hint for reverse relation from TicketRequestItem
    if TYPE_CHECKING:
        items: 'Manager[TicketRequestItem]'

    def __str__(self) -> str:
        if self.alvao_ticket_id:
            return f'Ticket {self.alvao_ticket_id} - {self.subject[:50]}'
        return f'Draft - {self.subject[:50]}'

    @property
    def item_count(self) -> int:
        """Returns the number of items in this ticket request."""
        return self.items.count()

    @property
    def is_submitted(self) -> bool:
        """Check if ticket has been submitted to Alvao."""
        return self.status in [self.Status.SUBMITTED, self.Status.CONFIRMED]


class TicketRequestItem(models.Model):
    """
    Individual item in a ticket request.

    Represents a dataset, dataclass, or table that the user wants to request.
    """

    class ItemType(models.TextChoices):
        """Types of items that can be requested."""

        DATASET = 'dataset', _('Dataset')
        DATACLASS = 'dataclass', _('Data Class')
        TABLE = 'table', _('Database Table')

    ticket_request = models.ForeignKey(
        TicketRequest,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name=_('Ticket Request'),
    )

    item_type = models.CharField(
        max_length=20, choices=ItemType.choices, verbose_name=_('Item Type')
    )
    item_id = models.CharField(
        max_length=100, verbose_name=_('Item ID'), help_text=_('Primary key of the requested item')
    )
    item_name = models.CharField(
        max_length=255,
        verbose_name=_('Item Name'),
        help_text=_('Display name of the requested item'),
    )
    item_description = models.TextField(blank=True, verbose_name=_('Item Description'))

    # Additional metadata
    parent_dataset = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Parent Dataset'),
        help_text=_('Parent dataset ID for dataclasses and tables'),
    )

    added_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Added At'))

    class Meta:
        db_table = 'ticketing_ticket_request_item'
        verbose_name = _('Ticket Request Item')
        verbose_name_plural = _('Ticket Request Items')
        ordering = ['added_at']
        unique_together = [['ticket_request', 'item_type', 'item_id']]

    def __str__(self) -> str:
        return f'{self.ItemType(self.item_type).label}: {self.item_name}'

    @property
    def detail_url(self) -> str | None:
        """Return URL to the dataset detail page, or None if not applicable or dataset no longer exists."""
        if self.item_type == self.ItemType.DATASET and '/' in self.item_id:
            app, name = self.item_id.split('/', 1)

            try:
                model = django_apps.get_model(app, 'Dataset')
                if not model.objects.filter(pk=name).exists():
                    return None
            except LookupError:
                return None
            return reverse('frontend:dataset_detail', kwargs={'app': app, 'name': name})
        return None
