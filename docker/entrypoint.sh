#!/bin/sh
set -e

# Ensure the logs directory exists (required for file-based logging handlers)
mkdir -p /app/logs

# Run all one-off setup tasks (migrations, seed, compilemessages, collectstatic)
# Must run from /app so that the 'catalogue' package is on the Python path.
cd /app && python docker/startup.py

exec "$@"
