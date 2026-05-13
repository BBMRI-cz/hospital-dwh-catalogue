#!/bin/sh

[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"

set -euo pipefail

install_ca_certificates() {
    local mou_ca_cert="/usr/local/share/ca-certificates/MOURootCA.crt"
    local ca_cert

    case "${DJANGO_SETTINGS_MODULE:-}" in
        catalogue.settings.staging|catalogue.settings.prod)
            if [ ! -f "$mou_ca_cert" ]; then
                echo "Missing mounted MOU root CA certificate at $mou_ca_cert." >&2
                echo "Check MOU_ROOT_CA_CERT_PATH in .env and redeploy with ./deploy.sh." >&2
                exit 1
            fi
            ;;
    esac

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
