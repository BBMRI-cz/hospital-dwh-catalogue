#!/bin/sh

[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

WITH_CHECK=false
WITH_OBSERVABILITY=false

while [ $# -gt 0 ]; do
    case "$1" in
        --with-check)
            WITH_CHECK=true
            shift
            ;;
        --with-observability)
            WITH_OBSERVABILITY=true
            shift
            ;;
        --help|-h)
            cat <<'EOF'
Usage: ./scripts/compose.sh [--with-check] [--with-observability] <docker-compose-args...>

Staging and production include observability automatically. Use
--with-observability to add it to dev.

Examples:
  ./scripts/compose.sh up -d --build
  ./scripts/compose.sh exec web python manage.py migrate
  ./scripts/compose.sh --with-observability up -d
  ./scripts/compose.sh --with-check run --rm check python -m mypy .
EOF
            exit 0
            ;;
        --)
            shift
            break
            ;;
        -*)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
        *)
            break
            ;;
    esac
done

if [ $# -eq 0 ]; then
    echo "Usage: ./scripts/compose.sh [--with-check] [--with-observability] <docker-compose-args...>" >&2
    exit 1
fi

ensure_repo_root
load_dotenv
require_valid_deploy_env
export_mou_root_ca_fingerprint
build_compose_args "$DEPLOY_ENV" "$WITH_CHECK" "$WITH_OBSERVABILITY"

exec docker compose "${COMPOSE_ARGS[@]}" "$@"
