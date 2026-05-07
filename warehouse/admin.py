"""
Admin configuration for the catalogue project - user management.

The admin panel exposes exactly two sections:
  - Users           - staff can assign the staff role; superusers can also revoke it.
  - Stat definitions - managed in fair_genomes/admin.py.

Everything else (groups, tickets, distributions, stat results ...) is deliberately
kept out of the admin interface.
"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _

User = get_user_model()

# Remove the built-in Group admin - groups are not managed through this panel.
admin.site.unregister(Group)

# Re-register User with the custom admin below.
admin.site.unregister(User)


@admin.register(User)
class CatalogueUserAdmin(BaseUserAdmin):
    """
    Simplified user admin restricted to the single task of managing the staff role.

    Permission model
    ----------------
    Superuser  - can assign *and* revoke the staff role (is_staff) for any user.
    Staff user - can only assign the staff role; once a user already has staff status they
                 cannot be changed by a regular staff member.

    Users are created automatically on first LDAP login; the add flow is therefore
    disabled here.
    """

    list_display = ('username', 'first_name', 'last_name', 'email', 'is_staff')
    list_filter = ('is_staff',)
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('username',)
    filter_horizontal = ()

    # Fieldsets shown when editing an existing user.
    fieldsets = (
        (None, {'fields': ('username',)}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Staff role'), {'fields': ('is_staff',)}),
    )

    # All staff can view and change users (to grant is_staff).
    # No explicit model permission needed - access is governed by is_staff alone.
    def has_module_permission(self, request):  # type: ignore[override]
        return request.user.is_staff

    def has_view_permission(self, request, obj=None):  # type: ignore[override]
        return request.user.is_staff

    def has_change_permission(self, request, obj=None):  # type: ignore[override]
        return request.user.is_staff

    # Disable the "add user" form - users are created via LDAP/dev auth.
    def has_add_permission(self, request):  # type: ignore[override]
        return False

    def has_delete_permission(self, request, obj=None):  # type: ignore[override]
        return request.user.is_superuser

    def get_readonly_fields(self, request, obj=None):
        """
        Lock down editable fields based on the caller's privilege level.

        All non-staff fields (username, name, email) are always readonly -
        they come from Active Directory and should not be edited here.

        is_staff is readonly for regular staff members when the target user
        already has staff or superuser status (i.e. nothing to grant, and
        they are not allowed to revoke).
        """
        base_readonly = ('username', 'first_name', 'last_name', 'email')

        # Nobody can change their own staff status.
        if obj is not None and obj.pk == request.user.pk:
            return (*base_readonly, 'is_staff')

        if not request.user.is_superuser and obj is not None and (obj.is_staff or obj.is_superuser):
            return (*base_readonly, 'is_staff')

        return base_readonly
