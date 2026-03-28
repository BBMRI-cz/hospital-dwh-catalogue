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
# first scheduled cron window. Runs in the background so the container starts
# immediately without waiting for the (potentially slow) network sync to finish.
echo "Running initial Fair Genomes sync in background..."
python manage.py sync_fair_genomes &

exec cron -f
