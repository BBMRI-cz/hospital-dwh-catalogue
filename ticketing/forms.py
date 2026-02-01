"""
Forms for the ticketing application.
"""
from django import forms
from django.utils.translation import gettext_lazy as _


class TicketSubmitForm(forms.Form):
    """Form for submitting a ticket request."""
    
    requester_email = forms.EmailField(
        label=_('Your Email'),
        help_text=_('We will use this email to contact you about your request.'),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': _('your.email@example.com'),
            'required': True,
        })
    )
    
    requester_name = forms.CharField(
        label=_('Your Name'),
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('John Doe'),
        })
    )
    
    subject = forms.CharField(
        label=_('Subject'),
        max_length=500,
        initial=_('Data Access Request'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Brief description of your request'),
            'required': True,
        })
    )
    
    description = forms.CharField(
        label=_('Additional Notes'),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': _('Please provide any additional information about your data request, such as purpose of use, timeframe needed, etc.'),
        })
    )
    
    def clean_requester_email(self) -> str:
        """Normalize email to lowercase."""
        email = self.cleaned_data['requester_email']
        return email.lower().strip()
