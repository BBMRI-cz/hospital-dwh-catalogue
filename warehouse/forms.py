from django import forms


class DatasetFilterForm(forms.Form):
    """Form for filtering datasets in the catalogue"""
    
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'filter-search',
            'placeholder': 'Zadejte hledaný text',
            'id': 'searchInput'
        }),
        label='Vyhledávání'
    )
    
    data_availability = forms.MultipleChoiceField(
        required=False,
        choices=[
            ('tables', 'Tabulky připraveny'),
            ('classes', 'Surová data'),
            ('none', 'Nedostupná data'),
        ],
        widget=forms.CheckboxSelectMultiple(),
        label='Dostupnost dat'
    )
    
    subject_tags = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple(),
        label='Klíčová slova'
    )
    
    data_source = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple(),
        label='Zdroj dat'
    )
    
    rights_holders = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple(),
        label='Držitel práv'
    )
    
    def __init__(self, *args, **kwargs):
        subject_tags_choices = kwargs.pop('subject_tags_choices', [])
        data_source_choices = kwargs.pop('data_source_choices', [])
        rights_holders_choices = kwargs.pop('rights_holders_choices', [])
        
        super().__init__(*args, **kwargs)
        
        self.fields['subject_tags'].choices = subject_tags_choices
        self.fields['data_source'].choices = data_source_choices
        self.fields['rights_holders'].choices = rights_holders_choices
