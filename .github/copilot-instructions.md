# Copilot Instructions

- Never compile message translations (do not run `django-admin compilemessages` or `python manage.py compilemessages`).
- Never add inline `<script>` blocks with JavaScript logic to HTML templates. Instead, put all JavaScript in a dedicated static file under `warehouse/static/js/` and load it with `<script src="{% static 'js/filename.js' %}">`. The only exception is `<script type="application/json">` data islands used to pass Django template variables to external JS files, and the Tailwind CDN config script in `_tailwind_config.html` which must remain inline.
- Put all static images (SVG, PNG, JPEG, ICO, WebP) under `warehouse/static/img/` and reference them in templates with `<img src="{% static 'img/filename.ext' %}">`. Never place image assets in the project root or outside the `warehouse/static/` hierarchy.
