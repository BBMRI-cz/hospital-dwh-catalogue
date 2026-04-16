#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/scripts/lib/common.sh"

usage() {
    cat <<'EOF'
Usage: ./init-env.sh [--force] <dev|staging|prod>

Creates .env from the matching example template.

- dev: keeps the fixed development SECRET_KEY placeholder
- staging/prod: generate a fresh SECRET_KEY automatically

Use --force to overwrite an existing .env file.
EOF
}

replace_env_value() {
    local key="$1"
    local value="$2"
    local file="$3"
    local temp_file
    temp_file="$(mktemp)"

    awk -v key="$key" -v value="$value" '
        BEGIN { updated = 0 }
        index($0, key "=") == 1 {
            print key "=" value
            updated = 1
            next
        }
        { print }
        END {
            if (!updated) {
                print key "=" value
            }
        }
    ' "$file" > "$temp_file"

    mv "$temp_file" "$file"
}

FORCE=false
TARGET_ENV=""

while [ $# -gt 0 ]; do
    case "$1" in
        --force)
            FORCE=true
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        dev|staging|prod)
            if [ -n "$TARGET_ENV" ]; then
                echo "Only one target environment can be specified." >&2
                exit 1
            fi
            TARGET_ENV="$1"
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

if [ -z "$TARGET_ENV" ]; then
    usage >&2
    exit 1
fi

ensure_repo_root

TEMPLATE_FILE="$REPO_ROOT/env-examples/${TARGET_ENV}.env.example"

if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "Missing template: $TEMPLATE_FILE" >&2
    exit 1
fi

if [ -f "$DOTENV_FILE" ] && [ "$FORCE" != true ]; then
    echo "$DOTENV_FILE already exists. Re-run with --force to overwrite it." >&2
    exit 1
fi

cp "$TEMPLATE_FILE" "$DOTENV_FILE"

if [ "$TARGET_ENV" = "staging" ] || [ "$TARGET_ENV" = "prod" ]; then
    HOST_PYTHON="$(resolve_host_python)"
    SECRET_KEY="$("$HOST_PYTHON" "$SCRIPT_DIR/scripts/generate_secret_key.py")"
    replace_env_value "SECRET_KEY" "$SECRET_KEY" "$DOTENV_FILE"
    echo "Generated a fresh SECRET_KEY for $TARGET_ENV."
else
    echo "Using the fixed development SECRET_KEY placeholder."
fi

echo "Created $DOTENV_FILE from env-examples/$(basename "$TEMPLATE_FILE")."
