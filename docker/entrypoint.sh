#!/bin/sh
set -e

# Ensure the logs directory exists (required for file-based logging handlers)
mkdir -p /app/logs

# Run migrations for all databases
# auth_db: sessions, auth, contenttypes, admin
python manage.py migrate --database=auth_db --noinput

# default: ticketing and other managed apps
python manage.py migrate --noinput

# fair_genomes_db: fair_genomes app
python manage.py migrate --database=fair_genomes_db --noinput

# Repair drifted fair_genomes_db migration state where 0001 is marked applied
# but core tables are missing (legacy schema leftovers, manual DB changes).
if ! python manage.py shell -c "from django.db import connections; print(int('fair_genomes_contact_point' in connections['fair_genomes_db'].introspection.table_names()))" | grep -q '^1$'; then
    echo "fair_genomes_db migration drift detected (missing fair_genomes_contact_point). Repairing migration state..."
    python manage.py migrate fair_genomes zero --database=fair_genomes_db --fake --noinput
    python manage.py migrate fair_genomes --database=fair_genomes_db --noinput
fi

# metadata_db: warehouse app
python manage.py migrate --database=metadata_db --noinput

# Seed fair_genomes_db with mock data when MOCK_FAIR_GENOMES=True.
# Tables must already exist (migration above), so this runs after migrate.
if [ "${MOCK_FAIR_GENOMES:-False}" = "True" ]; then
    echo "MOCK_FAIR_GENOMES=True — seeding fair_genomes_db with mock data..."
    python manage.py seed_fair_genomes_mock
fi

# Compile translation messages (cs and en only)
python manage.py compilemessages -l cs -l en

# Collect static files so nginx can serve them directly (skip in dev to speed up restarts)
if [ "${DJANGO_SETTINGS_MODULE}" != "catalogue.settings.dev" ]; then
    python manage.py collectstatic --noinput
fi

exec "$@"
