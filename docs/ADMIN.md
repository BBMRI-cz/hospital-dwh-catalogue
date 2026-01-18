# Admin Guide

## Django Admin Panel

The Django admin interface provides a powerful way to manage the data warehouse catalogue content.

### Accessing the Admin Panel

Navigate to:
```
http://localhost:8080/admin/
```

### Creating an Admin User

To access the admin panel, you need to create a superuser account. Run this command (change the <env> to represent your environment):

```bash
docker compose -f docker-compose.<env>.yml exec web python manage.py createsuperuser
```

Follow the prompts to enter:
- Username
- Email address (optional)
- Password (enter twice for confirmation)


## Managing Content

Once logged in, you can:
- Add, edit, and delete data warehouse metadata
- Manage users and permissions
- View and manage all database models
