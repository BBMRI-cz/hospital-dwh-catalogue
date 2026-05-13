#!/bin/bash

COMMON_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$COMMON_LIB_DIR/../.." && pwd)"
DOTENV_FILE="$REPO_ROOT/.env"

_python_candidate_works() {
    local candidate="$1"
    [ -n "$candidate" ] && [ -x "$candidate" ] && "$candidate" -V >/dev/null 2>&1
}

python_module_available() {
    local python="$1"
    local module="$2"
    "$python" -c "import $module" >/dev/null 2>&1
}

python_dev_toolchain_available() {
    local python="$1"
    [ -n "$python" ] \
        && python_module_available "$python" django \
        && python_module_available "$python" ruff \
        && python_module_available "$python" mypy \
        && python_module_available "$python" bandit
}

resolve_host_python() {
    if command -v python3 >/dev/null 2>&1; then
        command -v python3
        return 0
    fi

    if command -v python >/dev/null 2>&1; then
        command -v python
        return 0
    fi

    echo "No system Python executable found." >&2
    return 1
}

resolve_python() {
    if _python_candidate_works "$REPO_ROOT/.venv/bin/python"; then
        echo "$REPO_ROOT/.venv/bin/python"
        return 0
    fi

    if _python_candidate_works "$REPO_ROOT/venv/bin/python"; then
        echo "$REPO_ROOT/venv/bin/python"
        return 0
    fi

    resolve_host_python
}

resolve_check_python() {
    local candidate
    for candidate in "$REPO_ROOT/.venv/bin/python" "$REPO_ROOT/venv/bin/python"; do
        if _python_candidate_works "$candidate" && python_dev_toolchain_available "$candidate"; then
            echo "$candidate"
            return 0
        fi
    done

    candidate="$(resolve_host_python 2>/dev/null || true)"
    if _python_candidate_works "$candidate" && python_dev_toolchain_available "$candidate"; then
        echo "$candidate"
        return 0
    fi

    return 1
}

ensure_repo_root() {
    cd "$REPO_ROOT"
}

load_dotenv() {
    if [ ! -f "$DOTENV_FILE" ]; then
        echo "Missing $DOTENV_FILE. Run ./init-env.sh <dev|staging|prod> first." >&2
        return 1
    fi

    local dotenv_source="$DOTENV_FILE"
    local temp_file=""

    # Accept Windows-edited .env files copied onto Linux hosts.
    if LC_ALL=C grep -q $'\r' "$DOTENV_FILE"; then
        temp_file="$(mktemp)"
        tr -d '\r' < "$DOTENV_FILE" > "$temp_file"
        dotenv_source="$temp_file"
    fi

    set -a
    # shellcheck disable=SC1090
    . "$dotenv_source"
    set +a

    if [ -n "$temp_file" ]; then
        rm -f "$temp_file"
    fi
}

require_valid_deploy_env() {
    case "${DEPLOY_ENV:-}" in
        dev|staging|prod)
            return 0
            ;;
        *)
            echo "DEPLOY_ENV must be set to dev, staging, or prod in $DOTENV_FILE." >&2
            return 1
            ;;
    esac
}

export_mou_root_ca_fingerprint() {
    local cert_path="${MOU_ROOT_CA_CERT_PATH:-}"
    local cert_file
    local hash_line

    if [ -z "$cert_path" ]; then
        export MOU_ROOT_CA_SHA256=""
        return 0
    fi

    case "$cert_path" in
        /*) cert_file="$cert_path" ;;
        *) cert_file="$REPO_ROOT/$cert_path" ;;
    esac

    if [ -f "$cert_file" ] && command -v sha256sum >/dev/null 2>&1; then
        hash_line="$(sha256sum "$cert_file")"
        export MOU_ROOT_CA_SHA256="${hash_line%% *}"
    else
        export MOU_ROOT_CA_SHA256=""
    fi
}

build_compose_args() {
    local deploy_env="$1"
    local include_check="${2:-false}"
    local include_observability="${3:-false}"

    COMPOSE_ARGS=(
        -f docker/compose/base.yml
        -f "docker/compose/${deploy_env}.yml"
    )

    if [ "$include_check" = true ]; then
        COMPOSE_ARGS+=(-f docker/compose/check.yml)
    fi

    if [ "$deploy_env" = "prod" ] || [ "$deploy_env" = "staging" ] || [ "$include_observability" = true ]; then
        COMPOSE_ARGS+=(-f docker/compose/observability.yml)
    fi
}

compose_args_for_current_env() {
    local include_check="${1:-false}"
    local include_observability="${2:-false}"

    load_dotenv >/dev/null
    require_valid_deploy_env >/dev/null
    export_mou_root_ca_fingerprint
    build_compose_args "$DEPLOY_ENV" "$include_check" "$include_observability"
}

compose_args_for_dev_check() {
    build_compose_args "dev" true false
}

run_compose() {
    local deploy_env="$1"
    local include_check="${2:-false}"
    local include_observability="${3:-false}"
    shift 3

    ensure_repo_root
    load_dotenv >/dev/null
    export_mou_root_ca_fingerprint
    build_compose_args "$deploy_env" "$include_check" "$include_observability"
    DEPLOY_ENV="$deploy_env" docker compose --env-file "$DOTENV_FILE" "${COMPOSE_ARGS[@]}" "$@"
}

run_dev_check_compose() {
    ensure_repo_root
    compose_args_for_dev_check
    DEPLOY_ENV=dev docker compose --env-file "$DOTENV_FILE" "${COMPOSE_ARGS[@]}" "$@"
}

docker_check_runner_available() {
    command -v docker >/dev/null 2>&1 \
        && docker compose version >/dev/null 2>&1 \
        && [ -f "$REPO_ROOT/docker/compose/base.yml" ]
}

should_use_docker_check_runner() {
    case "${CHECK_RUNNER:-}" in
        docker)
            docker_check_runner_available
            return
            ;;
        local)
            return 1
            ;;
    esac

    local python
    python="$(resolve_check_python 2>/dev/null || true)"
    if [ -n "$python" ]; then
        return 1
    fi

    docker_check_runner_available
}

run_check_container() {
    run_dev_check_compose run --rm check "$@"
}

ensure_virtualenv() {
    ensure_repo_root

    if [ ! -d ".venv" ] || ! _python_candidate_works ".venv/bin/python"; then
        echo "Creating virtual environment..."
        "$(resolve_host_python)" -m venv .venv
    fi
}

ensure_project_dependencies() {
    if should_use_docker_check_runner; then
        return 0
    fi

    local python
    python="$(resolve_check_python 2>/dev/null || true)"
    if [ -n "$python" ]; then
        return 0
    fi

    ensure_virtualenv
    ensure_repo_root

    python=".venv/bin/python"
    local deps_stamp=".venv/.deps_installed"

    if [ ! -f "$deps_stamp" ] || [ "requirements.txt" -nt "$deps_stamp" ] || [ "requirements-dev.txt" -nt "$deps_stamp" ]; then
        echo "Installing/updating dependencies..."
        "$python" -m pip install --upgrade pip
        "$python" -m pip install -r requirements-dev.txt
        touch "$deps_stamp"
        echo "Dependencies installed successfully"
        echo ""
    fi
}
