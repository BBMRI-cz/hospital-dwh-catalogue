#!/bin/sh

[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"

set -euo pipefail

install_ldap_ca_certificate() {
    local ldap_ca_target="/usr/local/share/ca-certificates/auth-ldap-ca.crt"

    if [ -z "${AUTH_LDAP_CA_CERT_PATH:-}" ] || [ ! -f "$ldap_ca_target" ]; then
        return 0
    fi

    echo "Installing LDAP CA certificate into container trust store..."
    update-ca-certificates > /dev/null
}

# Ensure the logs directory exists (required for file-based logging handlers)
mkdir -p /app/logs

install_ldap_ca_certificate

# Run all one-off setup tasks (migrations, seed, compilemessages, collectstatic)
# Must run from /app so that the 'catalogue' package is on the Python path.
cd /app && python docker/startup.py

exec "$@"
