# Authentication System

This document covers the complete authentication setup for the Hospital Data Warehouse Catalogue, including development setup, production LDAP configuration.

## Overview

The application supports two authentication methods depending on the environment:

**Development Mode**: Uses a simple development backend that allows any username and any password. This bypasses Active Directory entirely for easier local development.

**Production Mode**: Integrates with Active Directory (LDAP) to authenticate users against their Windows domain credentials. User accounts are automatically created in Django on first login, and administrators can then assign roles and permissions.
## Quick Start for Development

For local development, you don't need access to Active Directory. The application includes a development authentication backend that makes testing much easier.
The first user you create will automatically become a superuser with full administrative privileges.

### How Development Authentication Works

The `DevAuthBackend` automatically creates user accounts when you log in:

- Any username and password works
- Email is set to `{username}@dev.local`
- Display name is the capitalized username
- First user created becomes a superuser

**Important**: The development backend only works when both `DEBUG=True` and `AUTH_USE_MOCK_LDAP=True` are set to true. It cannot be accidentally used in production.

## Production Setup with LDAP

For production deployment, the application authenticates users against your organization's Active Directory server.

### Understanding the Components

**LDAP (Lightweight Directory Access Protocol)** is the protocol used to communicate with Active Directory. Your organization's IT team manages an LDAP server that stores information about all users, computers, and other network resources.

When a user logs in, the application:
1. Connects to your LDAP server using a service account
2. Searches for the user by their username
3. Attempts to authenticate with the provided password
4. If successful, creates or updates the user in the Django database
5. Synchronizes the user's name and email from Active Directory

### Required Information from IT

You'll need to gather this information from your IT or network team:

**1. LDAP Server URI**
   - The address and port of your Active Directory server
   - Format: `ldap://server-name:389` (standard) or `ldaps://server-name:636` (secure)
   - Example: `ldap://dc01.hospital.local:389`

**2. Service Account Credentials (Bind DN)**
   - A read-only account that the application uses to search the directory
   - Format: `cn=account-name,ou=ServiceAccounts,dc=company,dc=com`
   - Example: `cn=django-ldap,ou=ServiceAccounts,dc=hospital,dc=local`
   - This account needs read access to user accounts but should not have any write permissions

**3. User Search Base**
   - The location in the directory where user accounts are stored
   - Format: `ou=OrganizationalUnit,dc=company,dc=com`
   - Example: `ou=Employees,dc=hospital,dc=local`

### Configuration

Add these settings to your `.env` file:

```bash
# LDAP Server Connection
AUTH_LDAP_SERVER_URI=ldaps://dc01.hospital.local:636

# Service Account
AUTH_LDAP_BIND_DN=cn=django-ldap,ou=ServiceAccounts,dc=hospital,dc=local
AUTH_LDAP_BIND_PASSWORD=YourServiceAccountPassword

# User Search Location
AUTH_LDAP_USER_SEARCH_BASE=ou=Employees,dc=hospital,dc=local

# Optional: Enable StartTLS (for ldap:// connections)
AUTH_LDAP_START_TLS=False
```

**Security Note**: Always use `ldaps://` (LDAP over SSL) in production. Only use `ldap://` with `AUTH_LDAP_START_TLS=True` if your organization requires it.


### Managing User Permissions

When users log in for the first time, Django creates their account but doesn't assign any special permissions. An administrator must grant roles through the Django admin interface:

1. Log in to Django Admin at `/admin/`
2. Navigate to **Users**
3. Find the user (created automatically on their first login)
4. Edit the user and assign:
   - **Staff status**: Allows access to Django admin
   - **Superuser status**: Full administrative permissions
   - **Groups**: For specific sets of permissions

### Database Structure

The project uses four databases:

| Database | Purpose | Models Stored |
|----------|---------|---------------|
| `auth_db` | Authentication & Authorization | User, Group, Permission, Session, ContentType, Admin logs |
| `metadata_db` | Warehouse Metadata | Hospital data warehouse catalog tables |
| `fair_genomes_db` | FAIR Genomes Data | Personal data and related FAIR Genomes models |
| `default` | Fallback | SQLite database for development and testing |

## User Authentication Flow

1. User navigates to the application
2. They see the login page at `/login/`
3. They enter their **Windows domain username** (e.g., `jnovak` or `HOSPITAL\jnovak`)
4. They enter their **Windows password**
5. They click "Sign in"
6. If it's their first login, Django automatically creates their account
7. They're redirected to the application homepage
