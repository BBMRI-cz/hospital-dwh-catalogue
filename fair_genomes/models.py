"""
Fair Genomes Models

Django models for Fair Genomes GraphQL API integration.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class FairGenomesBase(models.Model):
    """
    Abstract base model for Fair Genomes entities.
    Provides common metadata fields.
    """

    inserted_by = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_('Inserted By'),
        help_text=_('User who created this record'),
    )
    inserted_on = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Inserted On'),
        help_text=_('Timestamp when record was created'),
    )
    updated_by = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_('Updated By'),
        help_text=_('User who last updated this record'),
    )
    updated_on = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Updated On'),
        help_text=_('Timestamp when record was last updated'),
    )

    class Meta:
        abstract = True


class Personal(FairGenomesBase):
    """
    Personal information from Fair Genomes GraphQL API.

    This model stores patient demographic data synced from the
    Fair Genomes MOLGENIS instance.
    """

    personal_identifier = models.CharField(
        max_length=255,
        primary_key=True,
        verbose_name=_('Personal Identifier'),
        help_text=_('Unique identifier for the individual'),
    )
    year_of_birth = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_('Year of Birth'),
        help_text=_('Year the individual was born'),
    )

    class Meta(FairGenomesBase.Meta):
        db_table = 'fair_genomes_personal'
        verbose_name = _('Personal Record')
        verbose_name_plural = _('Personal Records')
        ordering = ['-inserted_on']
        indexes = [
            models.Index(fields=['year_of_birth'], name='idx_personal_yob'),
            models.Index(fields=['inserted_on'], name='idx_personal_inserted'),
        ]

    def __str__(self):
        return f'{self.personal_identifier}'

    def __repr__(self):
        return f'<Personal: {self.personal_identifier} (born {self.year_of_birth})>'
