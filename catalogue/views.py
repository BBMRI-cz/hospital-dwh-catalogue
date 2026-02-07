"""
Authentication views for the catalogue application.
"""
from django.conf import settings
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _


class CustomLoginView(LoginView):
    """
    Custom login view using Active Directory authentication.

    Users authenticate with their Windows domain credentials.
    User accounts are automatically created on first successful login.
    """
    template_name = 'catalogue/login.html'
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Sign In')
        context['debug'] = settings.DEBUG
        context['mock_ldap_enabled'] = getattr(settings, 'AUTH_USE_MOCK_LDAP', False)
        context['ldap_configured'] = bool(getattr(settings, 'AUTH_LDAP_SERVER_URI', ''))
        return context


def logout_view(request):
    """
    Logout view that ends the user session.
    """
    auth_logout(request)
    return redirect('login')
