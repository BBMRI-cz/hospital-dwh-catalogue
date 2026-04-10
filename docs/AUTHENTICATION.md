# Authentication

## Overview

The application has two authentication modes:

- Mock LDAP -- accepts any username and password. No Active Directory needed.
- Real LDAP -- authenticates users against Active Directory.

## Mock authentication

When `MOCK_LDAP=True` is set in your `.env`, the mock auth backend is active. This is suitable for local development and for staging when you want to validate the rest of the deployment without depending on Active Directory.

How it works:

- Any username and password combination is accepted
- Email is set to `{username}@example.com`
- The first user created becomes a superuser
- Every subsequent login creates a regular user if the username does not exist yet

The backend checks only the `MOCK_LDAP` setting.

## LDAP setup

When `MOCK_LDAP=False`, users authenticate against your organization's Active Directory server. This is the only supported mode in production.

### What happens when a user logs in

1. The app connects to your LDAP server using a service account
2. It searches for the user by username
3. It tries to authenticate with the password the user entered
4. If successful, it creates or updates the user in Django
5. It syncs the user's name and email from Active Directory

### Information you need from your IT team

1. LDAP server address and port (for example, `ldaps://dc01.hospital.local:636`)
2. Service account DN and password (a read-only account for searching the directory)
3. User search base (the directory path where user accounts are stored)

### Configuration

Add these to your `.env` file:

```bash
AUTH_LDAP_SERVER_URI=ldaps://dc01.hospital.local:636
AUTH_LDAP_BIND_DN=cn=django-ldap,ou=ServiceAccounts,dc=hospital,dc=local
AUTH_LDAP_BIND_PASSWORD=YourServiceAccountPassword
AUTH_LDAP_USER_SEARCH_BASE=ou=Employees,dc=hospital,dc=local
```

Use `ldaps://` (LDAP over SSL) in production. If your organization uses plain `ldap://` with StartTLS instead, set:

```bash
AUTH_LDAP_START_TLS=True
```

### Managing permissions after first login

New users have no special permissions. An admin must grant them through the Django admin panel at `/admin/`. See the [Admin Guide](ADMIN.md) for details.

## Databases

Authentication data lives in the `auth_db` database, separate from application data:

| Database | Contents |
|---|---|
| `auth_db` | Users, groups, permissions, sessions, admin logs |
| `metadata_db` | Warehouse catalogue tables |
| `fair_genomes_db` | FAIR Genomes data and stats |
| `default` | Ticketing models |

## Login flow

1. User goes to `/accounts/login/`
2. Enters their username (for example, `jnovak`) and password
3. The system authenticates against LDAP or the mock backend, depending on `MOCK_LDAP`
4. On first login, Django creates the user account automatically
5. User is redirected to the homepage
