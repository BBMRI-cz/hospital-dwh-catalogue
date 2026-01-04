"""
Fair Genomes Views
"""
from django.views.generic import ListView, DetailView
from django.db.models import Q
from .models import Personal


class PersonalListView(ListView):
    """
    List view for Personal records from Fair Genomes API.
    Includes search and filtering capabilities.
    """
    model = Personal
    template_name = 'fair_genomes/personal_list.html'
    context_object_name = 'records'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Personal.objects.all()
        
        # Search functionality
        search = self.request.GET.get('query', '').strip()
        if search:
            queryset = queryset.filter(
                Q(personal_identifier__icontains=search) |
                Q(inserted_by__icontains=search)
            )
        
        # Year of birth filter
        yob = self.request.GET.get('yob', '').strip()
        if yob:
            try:
                queryset = queryset.filter(year_of_birth=int(yob))
            except ValueError:
                pass
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('query', '')
        context['yob'] = self.request.GET.get('yob', '')
        context['total_count'] = Personal.objects.count()
        
        # Get unique years for filter dropdown
        context['years_of_birth'] = Personal.objects.exclude(
            year_of_birth__isnull=True
        ).values_list('year_of_birth', flat=True).distinct().order_by('year_of_birth')
        
        return context


class PersonalDetailView(DetailView):
    """
    Detail view for a single Personal record.
    """
    model = Personal
    template_name = 'fair_genomes/personal_detail.html'
    context_object_name = 'record'
