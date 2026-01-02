from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def get_availability_icon(dataset):
    """Returns HTML icon based on dataset availability status"""
    if hasattr(dataset, 'has_tables') and dataset.has_tables:
        return mark_safe(
            '<i class="fa-solid fa-circle-check" title="Data připravena v podobě tabulek" '
            'style="color: #afca0b; font-size: 1.3rem;"></i>'
        )
    elif hasattr(dataset, 'has_classes') and dataset.has_classes:
        return mark_safe(
            '<i class="fa-solid fa-circle-question" title="Zdrojová data bez úpravy" '
            'style="color: #009fc9; font-size: 1.3rem;"></i>'
        )
    else:
        return mark_safe(
            '<i class="fa-solid fa-circle-xmark" title="Aktuálně nedostupná data" '
            'style="color: #888888; font-size: 1.3rem;"></i>'
        )


@register.filter
def get_availability_class(dataset):
    """Returns CSS class based on dataset availability"""
    if hasattr(dataset, 'has_tables') and dataset.has_tables:
        return 'footer-green'
    elif hasattr(dataset, 'has_classes') and dataset.has_classes:
        return 'footer-blue'
    return 'footer-grey'


@register.filter
def get_availability_text(dataset):
    """Returns text based on dataset availability"""
    if hasattr(dataset, 'has_tables') and dataset.has_tables:
        return 'Zobrazit tabulky'
    elif hasattr(dataset, 'has_classes') and dataset.has_classes:
        return 'Zobrazit dostupná data'
    return 'Data nejsou momentálně k dispozici'


@register.filter
def get_toggle_type(dataset):
    """Returns toggle type for dataset"""
    if hasattr(dataset, 'has_tables') and dataset.has_tables:
        return 'tables'
    elif hasattr(dataset, 'has_classes') and dataset.has_classes:
        return 'classes'
    return 'none'


@register.inclusion_tag('warehouse/includes/dataset_card.html')
def dataset_card(dataset, loop_counter):
    """Renders a dataset card"""
    return {
        'dataset': dataset,
        'counter': loop_counter,
    }


@register.inclusion_tag('warehouse/includes/dataclass_card.html')
def dataclass_card(dataclass, parent_counter, loop_counter):
    """Renders a data class card"""
    return {
        'dataclass': dataclass,
        'parent_counter': parent_counter,
        'counter': loop_counter,
    }


@register.inclusion_tag('warehouse/includes/table_card.html')
def table_card(table, parent_counter, loop_counter):
    """Renders a database table card"""
    return {
        'table': table,
        'parent_counter': parent_counter,
        'counter': loop_counter,
    }


@register.filter
def yesno_cz(value):
    """Czech version of yesno filter"""
    if value:
        return 'Ano'
    return 'Ne'


@register.filter
def split_tags(subject_string):
    """Split subject string into list of tags"""
    if not subject_string:
        return []
    return [tag.strip() for tag in subject_string.split(',') if tag.strip()]


@register.simple_tag
def query_transform(request, **kwargs):
    """Update query string with new parameters"""
    updated = request.GET.copy()
    for key, value in kwargs.items():
        if value is not None:
            updated[key] = value
        else:
            updated.pop(key, None)
    return updated.urlencode()
