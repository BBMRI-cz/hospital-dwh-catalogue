# Admin Guide

## Accessing the admin panel

Go to `/admin/` in your browser (for example, http://localhost/admin/ in development).

You need a superuser account to log in. The recommended way is to configure one via environment variables (see below).

## Configuring the superuser via environment variables

The container startup script (`docker/startup.py`) automatically creates and maintains a superuser account from two environment variables:

```env
DJANGO_SUPERUSER_USERNAME=app-admin
DJANGO_SUPERUSER_PASSWORD=your-strong-password
```

Set these in your `.env` file (see the `.env.*.example` files for the correct template per environment). The account is created — or updated — on **every container startup**, so:

- Changing `DJANGO_SUPERUSER_PASSWORD` and restarting the container immediately applies the new password.
- Changing `DJANGO_SUPERUSER_USERNAME` deletes the old env-managed account and creates a new one with the new name.
- If either variable is absent or blank, the step is silently skipped.

### Choosing a username

> **Important:** The env username must **not** exist in Active Directory.

In production, authentication goes through LDAP first (`LDAPBackend`), then falls back to Django's `ModelBackend` for local accounts (the comment in `settings/base.py` notes this explicitly). The env superuser authenticates via `ModelBackend` using its local password — this works correctly as long as the username is not a real AD account.

If an AD user with the same username logs in via LDAP, `AUTH_LDAP_ALWAYS_UPDATE_USER = True` will overwrite the sentinel email that tracks env-managed accounts. The startup script detects this on the next restart and re-claims the account if it still has a locally usable password and superuser flag. To avoid this ambiguity entirely, use a service-account-style name that does not appear in AD:

```
app-admin     ✔
_dwh-admin    ✔
john.smith    ✗  (real AD user)
admin         ✗  (commonly exists in AD)
```

This account is intended as a bootstrap/emergency account. Real staff should authenticate through LDAP.

## Creating an admin user manually

If you need to create an additional superuser by hand (e.g. the env vars are not set), run this inside the web container:

```bash
docker compose -f docker-compose.<env>.yml exec web python manage.py createsuperuser
```

Replace `<env>` with `dev`, `test`, or `prod`.

> **Note:** If the manually created username matches `DJANGO_SUPERUSER_USERNAME` and the user has no usable local password (i.e. it is a pure LDAP account), the startup script will leave it untouched. If it does have a local password, the startup script will re-claim it as the env-managed account on next restart.

## Managing content

From the admin panel you can:

- Manage FAIR Genomes stat definitions (add, edit, activate/deactivate, reorder)
- Trigger a manual FAIR Genomes sync (see [Stats Setup](STATS.md) for details)
- Manage users and their permissions
- View ticket requests

Warehouse metadata (datasets, distributions, tables, columns) is not registered in the admin panel. That data is managed externally and the catalogue reads it directly from the `metadata_db` database.

## Managing users

When a user logs in for the first time (via LDAP in production or the dev backend in development), Django creates their account automatically with no special permissions.

To grant permissions:

1. Go to `/admin/` and navigate to Users
2. Find the user
3. Edit and assign:
   - Staff status -- allows access to the admin panel
   - Superuser status -- full administrative permissions
   - Groups -- for specific permission sets
