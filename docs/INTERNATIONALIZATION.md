# Internationalization (i18n)

The application supports multiple languages (currently Czech and English).

## Updating Translations

When developing and adding or modifying translatable strings:

1. **Extract new strings** from your code to `.po` files:
   ```bash
   python manage.py makemessages --all
   ```

2. **Edit the `.po` files** in `locale/cs/LC_MESSAGES/django.po` and `locale/en/LC_MESSAGES/django.po` to add translations.

3. **For local development** (outside Docker), compile translations:
   ```bash
   python manage.py compilemessages
   ```

4. **Commit only `.po` files** to git. The `.mo` files are automatically generated in Docker and excluded from version control.
