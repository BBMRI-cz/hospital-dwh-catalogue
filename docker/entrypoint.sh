#!/bin/sh
set -e

# Run migrations for all databases
# auth_db: sessions, auth, contenttypes, admin
python manage.py migrate --database=auth_db --noinput

# default: ticketing and other managed apps
python manage.py migrate --noinput

# fair_genomes_db: fair_genomes app
python manage.py migrate --database=fair_genomes_db --noinput

# Compile translation messages
python manage.py compilemessages

exec "$@"
