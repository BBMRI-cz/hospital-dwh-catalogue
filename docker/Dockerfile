FROM python:3.13-slim AS base

# Prevent Python from writing .pyc files and buffer output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    postgresql-client \
    gettext \
    cron \
    gcc \
    libldap2-dev \
    ldap-utils \
    libsasl2-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

FROM base AS check

COPY requirements-dev.txt /app/
RUN pip install --no-cache-dir -r requirements-dev.txt

FROM base AS runtime

# Copy project files
COPY . /app/

# Install Tailwind CSS standalone CLI (no Node.js required) and pre-build CSS.
# TARGETARCH is set automatically by Docker BuildKit for multi-platform builds.
ARG TAILWIND_VERSION=v3.4.17
ARG TARGETARCH
RUN ARCH="${TARGETARCH:-amd64}"; \
    if [ "$ARCH" = "arm64" ]; then BIN="tailwindcss-linux-arm64"; \
    else BIN="tailwindcss-linux-x64"; fi && \
    curl -fsSL "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/${BIN}" \
         -o /usr/local/bin/tailwindcss \
    && chmod +x /usr/local/bin/tailwindcss

RUN tailwindcss \
    -c /app/tailwind.config.cjs \
    -i /app/frontend/static/css/tailwind.input.css \
    -o /app/frontend/static/css/tailwind.css \
    --minify

EXPOSE 8000

# Gunicorn by default - docker compose overrides this for dev/test
CMD ["gunicorn", "catalogue.wsgi:application", "--bind", "0.0.0.0:8000"]
