"""
Warehouse Views

Class-based views for the warehouse catalogue application.
"""

from typing import Any

from django.db.models import Q, QuerySet
from django.views.generic import ListView

from .models import DatasetList


class CatalogueView(ListView):
    """
    Main catalogue view displaying all datasets.

    Supports filtering by:
    - Search query (name, description, subject)
    """

    model = DatasetList
    template_name = 'warehouse/catalogue.html'
    context_object_name = 'datasets'

    def get_queryset(self) -> QuerySet[DatasetList]:
        """Return filtered queryset with optimized prefetching."""
        queryset = DatasetList.objects.select_related('data_source').prefetch_related(
            'dataclasses__db_tables'
        )

        query = self.request.GET.get('query', '').strip()
        if query:
            queryset = queryset.filter(
                Q(data_set_name__icontains=query)
                | Q(description__icontains=query)
                | Q(subject__icontains=query)
            ).distinct()

        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Add filter options to context."""
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('query', '')

        # Get unique subject tags (comma-separated field requires parsing)
        subjects = DatasetList.objects.exclude(subject='').values_list('subject', flat=True)

        subject_tags = set()
        for subject in subjects:
            if subject:
                tags = [tag.strip() for tag in subject.split(',')]
                subject_tags.update(tag for tag in tags if tag)

        context['subject_tags'] = sorted(subject_tags)

        # Get unique data sources
        context['data_sources'] = sorted(
            filter(
                None,
                DatasetList.objects.values_list(
                    'data_source__data_source_name', flat=True
                ).distinct(),
            )
        )

        # Get unique rights holders
        context['rights_holders'] = sorted(
            filter(
                None,
                DatasetList.objects.exclude(rights_holder='')
                .values_list('rights_holder', flat=True)
                .distinct(),
            )
        )

        return context


catalogue = CatalogueView.as_view()
