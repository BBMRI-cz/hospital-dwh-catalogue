#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py migrate --database=fair_genomes_db --noinput
python manage.py compilemessages

exec "$@"
