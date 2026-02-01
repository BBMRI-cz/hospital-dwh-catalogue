from django import template
from django.utils.html import format_html

register = template.Library()


@register.filter
def get_availability_icon(dataset):
    """Returns HTML icon based on dataset availability status."""
    if hasattr(dataset, 'has_tables') and dataset.has_tables:
        return format_html(
            '<i class="fa-solid fa-circle-check" title="{}" style="color: {}; font-size: 1.3rem;">'
            '</i>',
            'Data připravena v podobě tabulek',
            '#afca0b',
        )
    elif hasattr(dataset, 'has_classes') and dataset.has_classes:
        return format_html(
            '<i class="fa-solid fa-circle-question" title="{}" style="color: {}; font-size: 1.3rem;">'
            '</i>',
            'Zdrojová data bez úpravy',
            '#009fc9',
        )
    else:
        return format_html(
            '<i class="fa-solid fa-circle-xmark" title="{}" style="color: {}; font-size: 1.3rem;">'
            '</i>',
            'Aktuálně nedostupná data',
            '#888888',
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
