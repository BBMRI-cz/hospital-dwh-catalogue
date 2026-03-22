#!/bin/sh
set -e

INTERVAL="${FAIR_GENOMES_SYNC_INTERVAL_HOURS:-24}"

# Write the cron job — executes the management command and streams output to
# the container's stdout/stderr so it appears in `docker compose logs`.
cat > /etc/cron.d/fair_genomes_sync << EOF
0 */${INTERVAL} * * * root cd /app && python manage.py sync_fair_genomes >> /proc/1/fd/1 2>> /proc/1/fd/2
EOF

chmod 0644 /etc/cron.d/fair_genomes_sync
crontab /etc/cron.d/fair_genomes_sync

# Run an immediate sync so the data is fresh right after startup, before the
# first scheduled cron window.
echo "Running initial Fair Genomes sync on startup..."
python manage.py sync_fair_genomes

exec cron -f
