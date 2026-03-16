#!/bin/sh
set -e

# Run migrations for all databases
# auth_db: sessions, auth, contenttypes, admin
python manage.py migrate --database=auth_db --noinput

# default: ticketing and other managed apps
python manage.py migrate --noinput

# fair_genomes_db: fair_genomes app
python manage.py migrate --database=fair_genomes_db --noinput

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
