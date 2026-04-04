# Internationalization

The application supports Czech and English. All user-facing strings in templates use Django's translation system.

## Adding or updating translations

1. After adding or changing translatable strings in templates or Python code, extract them:

   ```bash
   docker exec hospital_dwh_web_dev python manage.py makemessages --all
   ```

2. Edit the `.po` files to add the translations:

   - `locale/cs/LC_MESSAGES/django.po` (Czech)
   - `locale/en/LC_MESSAGES/django.po` (English)

3. Compile the `.po` files into `.mo` files:

   ```bash
   docker exec hospital_dwh_web_dev python manage.py compilemessages
   ```

4. Commit both the `.po` and `.mo` files together.

## How strings work in templates

Use `{% trans "..." %}` for simple strings:

```html
{% trans "Search" %}
```

Use `{% blocktrans %}` for strings with variables:

```html
{% blocktrans with count=items|length %}{{ count }} items found{% endblocktrans %}
```

To pass translated strings to JavaScript, use a `json_script` data island in the template:

```html
{{ translated_value|json_script:"my-data" }}
```

Then read it from JavaScript in a separate `.js` file.

## If the container is not running

Start it first:

```bash
docker compose -f docker-compose.dev.yml up -d db web
```

Wait for it to be healthy, then run the `makemessages` or `compilemessages` commands above.

## Automatic compilation on deploy

The Docker startup script (`docker/startup.py`) checks if any `.po` file is newer than its `.mo` counterpart and recompiles automatically. You still need to compile and commit locally so that CI checks pass.

## CI check

The `scripts/check-translations.sh` script checks that:

- No translations are marked as fuzzy
- No translations are empty
- All `.mo` files exist and are up to date

This runs as part of `./scripts/check.sh` and in CI.
