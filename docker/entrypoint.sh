#!/bin/sh

[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"

set -euo pipefail

install_ca_certificates() {
    local ca_cert
    for ca_cert in /usr/local/share/ca-certificates/*.crt; do
        [ -f "$ca_cert" ] || continue
        echo "Installing custom CA certificates into container trust store..."
        update-ca-certificates > /dev/null
        return 0
    done
}


# Ensure the logs directory exists (required for file-based logging handlers)
mkdir -p /app/logs

install_ca_certificates

# Run all one-off setup tasks (migrations, seed, compilemessages, collectstatic)
# Must run from /app so that the 'catalogue' package is on the Python path.
cd /app && python docker/startup.py

exec "$@"
