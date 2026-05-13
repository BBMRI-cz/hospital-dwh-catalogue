#!/bin/sh
set -e

MOU_CA_CERT="/usr/local/share/ca-certificates/MOURootCA.crt"
COMBINED_CA_BUNDLE="/tmp/mou-ca-bundle.crt"

case "${DJANGO_SETTINGS_MODULE:-}" in
    catalogue.settings.staging|catalogue.settings.prod)
        if [ ! -f "$MOU_CA_CERT" ]; then
            echo "Missing mounted MOU root CA certificate at $MOU_CA_CERT." >&2
            echo "Check MOU_ROOT_CA_CERT_PATH in .env and redeploy with ./deploy.sh." >&2
            exit 1
        fi

        cat /etc/ssl/certs/ca-certificates.crt "$MOU_CA_CERT" > "$COMBINED_CA_BUNDLE"
        export REQUESTS_CA_BUNDLE="$COMBINED_CA_BUNDLE"
        export SSL_CERT_FILE="$COMBINED_CA_BUNDLE"
        export CURL_CA_BUNDLE="$COMBINED_CA_BUNDLE"
        ;;
esac

if [ -f "$MOU_CA_CERT" ]; then
    echo "Installing custom CA certificates into container trust store..."
    update-ca-certificates > /dev/null
fi

INTERVAL="${FAIR_GENOMES_SYNC_INTERVAL_HOURS:-24}"

# Persist the container's environment variables so the cron job can access them
# (cron runs with a minimal environment that lacks DJANGO_SETTINGS_MODULE,
# POSTGRES_*, FAIR_GENOMES_*, SECRET_KEY, etc.).
env | grep -Ev '^(HOME|USER|LOGNAME|PATH|SHELL|TERM|HOSTNAME|PWD|SHLVL|_)=' \
    > /etc/environment

# Write the cron job - executes the management command and streams output to
# the container's stdout/stderr so it appears in `docker compose logs`.
cat > /etc/cron.d/fair_genomes_sync << EOF
0 */${INTERVAL} * * * root . /etc/environment; cd /app && python manage.py sync_fair_genomes >> /proc/1/fd/1 2>> /proc/1/fd/2
EOF

chmod 0644 /etc/cron.d/fair_genomes_sync
crontab /etc/cron.d/fair_genomes_sync

# Run an immediate sync so the data is fresh right after startup, before the
# first scheduled cron window. Runs in the background so the container starts
# immediately without waiting for the (potentially slow) network sync to finish.
echo "Running initial FAIR Genomes sync in background..."
python manage.py sync_fair_genomes &

exec cron -f
