#!/usr/bin/env bash
# Local (non-Docker) XRay full-chain launcher for the ms-image repository.
#
# This launcher is the single local owner for:
#   1. Runtime API            -> http://127.0.0.1:8010/api/v1
#   2. Imaging Outbox Relay   (polls the transactional outbox)
#   3. Celery imaging worker  (consumes imaging.image.validate)
#
# The AI Attempt reconcile Beat is intentionally not owned by this launcher.
# Keep it disabled unless a separate, explicitly qualified scheduler owns it.
#
# Requirements
#   - Local MySQL on 127.0.0.1:3306 with the ms_image schema already created
#   - Local RabbitMQ on localhost:5672 (guest login, vhost /)
#   - Local Redis on localhost:6379
#   - ms-ai-fast/.env contains AI_PLATFORM_API_KEY
#   - ms-image/.env contains Nacos and Runtime Basic Auth credentials
#   - scripts/dev/keys/public.pem exists (NEVER commit the private key)
#
# Secrets are injected into process environments only. They are never printed.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="/opt/homebrew/anaconda3/bin/python3.12"
FAST_ENV="/Users/mozhicheng/workspace/code/cy-code/ms-ai-fast/.env"
IMAGE_ENV="$REPO_ROOT/.env"
KEYS_DIR="$REPO_ROOT/scripts/dev/keys"
PUB="$KEYS_DIR/public.pem"
API_PORT="${MS_IMAGE_LOCAL_API_PORT:-8010}"
WORKER_CONCURRENCY="${MS_IMAGE_LOCAL_WORKER_CONCURRENCY:-2}"
RECONCILE_SCHEDULE_ENABLED="${AI_ATTEMPT_RECONCILE_SCHEDULE_ENABLED:-false}"
STARTUP_TIMEOUT_SECONDS="${MS_IMAGE_LOCAL_STARTUP_TIMEOUT_SECONDS:-60}"
SHUTDOWN_TIMEOUT_SECONDS="${MS_IMAGE_LOCAL_SHUTDOWN_TIMEOUT_SECONDS:-130}"
RELAY_HEARTBEAT_PATH="${IMAGING_RELAY_HEARTBEAT_PATH:-/tmp/ms-image-imaging-relay.heartbeat}"
LOCK_DIR="/tmp/ms-image-local-chain-${API_PORT}.lock"
LOCK_PID_FILE="$LOCK_DIR/owner.pid"
LOCK_META_FILE="$LOCK_DIR/owner.meta"

LOCK_ACQUIRED=false
OWN_PIDS=()
API_PID=""
RELAY_PID=""
WORKER_PID=""
STARTED_AT_EPOCH=""

fail() {
    echo "ERROR: $*" >&2
    return 1
}

release_lock() {
    if [[ "$LOCK_ACQUIRED" != "true" ]]; then
        return
    fi
    local recorded_pid=""
    if [[ -f "$LOCK_PID_FILE" ]]; then
        read -r recorded_pid < "$LOCK_PID_FILE" || true
    fi
    if [[ "$recorded_pid" == "$$" ]]; then
        rm -f "$LOCK_PID_FILE" "$LOCK_META_FILE"
        rmdir "$LOCK_DIR" 2>/dev/null || true
    fi
    LOCK_ACQUIRED=false
}

cleanup() {
    local status=$?
    trap - EXIT INT TERM
    if (( ${#OWN_PIDS[@]} > 0 )); then
        echo "Stopping launcher-owned local processes ..."
        local pid
        for pid in "${OWN_PIDS[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then
                kill -TERM "$pid" 2>/dev/null || true
            fi
        done

        local deadline=$(( $(date +%s) + SHUTDOWN_TIMEOUT_SECONDS ))
        local any_alive
        while :; do
            any_alive=false
            for pid in "${OWN_PIDS[@]}"; do
                if kill -0 "$pid" 2>/dev/null; then
                    any_alive=true
                    break
                fi
            done
            if [[ "$any_alive" == "false" ]]; then
                break
            fi
            if (( $(date +%s) >= deadline )); then
                echo "Launcher-owned process shutdown timed out; forcing only owned PIDs." >&2
                for pid in "${OWN_PIDS[@]}"; do
                    if kill -0 "$pid" 2>/dev/null; then
                        kill -KILL "$pid" 2>/dev/null || true
                    fi
                done
                break
            fi
            sleep 1
        done
        for pid in "${OWN_PIDS[@]}"; do
            wait "$pid" 2>/dev/null || true
        done
    fi
    release_lock
    exit "$status"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

validate_integer() {
    local name="$1"
    local value="$2"
    case "$value" in
        ''|*[!0-9]*) fail "$name must be a positive integer" ;;
        0) fail "$name must be a positive integer" ;;
    esac
}

validate_integer "MS_IMAGE_LOCAL_API_PORT" "$API_PORT"
validate_integer "MS_IMAGE_LOCAL_WORKER_CONCURRENCY" "$WORKER_CONCURRENCY"
validate_integer "MS_IMAGE_LOCAL_STARTUP_TIMEOUT_SECONDS" "$STARTUP_TIMEOUT_SECONDS"
validate_integer "MS_IMAGE_LOCAL_SHUTDOWN_TIMEOUT_SECONDS" "$SHUTDOWN_TIMEOUT_SECONDS"
if (( API_PORT > 65535 )); then
    fail "MS_IMAGE_LOCAL_API_PORT must be between 1 and 65535"
fi
if [[ "$RECONCILE_SCHEDULE_ENABLED" != "false" ]]; then
    fail "This launcher does not own Celery Beat; set AI_ATTEMPT_RECONCILE_SCHEDULE_ENABLED=false"
fi

acquire_lock() {
    if mkdir "$LOCK_DIR" 2>/dev/null; then
        LOCK_ACQUIRED=true
    else
        local owner_pid=""
        local attempt
        for attempt in 1 2 3; do
            if [[ -f "$LOCK_PID_FILE" ]]; then
                read -r owner_pid < "$LOCK_PID_FILE" || true
                break
            fi
            sleep 1
        done
        case "$owner_pid" in
            ''|*[!0-9]*)
                fail "Local-chain lock exists without a valid owner: $LOCK_DIR"
                ;;
        esac
        if kill -0 "$owner_pid" 2>/dev/null; then
            fail "Another local-chain launcher owns port $API_PORT (PID $owner_pid)"
        fi
        echo "Removing stale local-chain lock for exited PID $owner_pid."
        rm -f "$LOCK_PID_FILE" "$LOCK_META_FILE"
        rmdir "$LOCK_DIR" 2>/dev/null || fail "Unable to remove stale lock: $LOCK_DIR"
        mkdir "$LOCK_DIR" 2>/dev/null || fail "Unable to acquire local-chain lock: $LOCK_DIR"
        LOCK_ACQUIRED=true
    fi

    printf '%s\n' "$$" > "$LOCK_PID_FILE"
    {
        printf 'repo=%s\n' "$REPO_ROOT"
        printf 'port=%s\n' "$API_PORT"
        printf 'started_at_epoch=%s\n' "$(date +%s)"
    } > "$LOCK_META_FILE"
}

print_process_matches() {
    local label="$1"
    local pattern="$2"
    local matches=""
    matches="$(pgrep -f "$pattern" 2>/dev/null || true)"
    if [[ -z "$matches" ]]; then
        return 1
    fi
    echo "Existing $label process(es):" >&2
    local pid
    for pid in $matches; do
        ps -p "$pid" -o pid=,ppid=,command= >&2 || true
    done
    return 0
}

preflight_process_ownership() {
    local conflict=false
    if lsof -nP -iTCP:"$API_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
        echo "Port $API_PORT is already listening:" >&2
        lsof -nP -iTCP:"$API_PORT" -sTCP:LISTEN >&2 || true
        conflict=true
    fi
    if print_process_matches \
        "ms-image Runtime API" \
        'uvicorn[[:space:]]+apps\.backend\.services\.runtime\.main:app'; then
        conflict=true
    fi
    if print_process_matches \
        "ms-image imaging Relay" \
        'apps\.backend\.workers\.imaging_worker\.outbox_relay'; then
        conflict=true
    fi
    if print_process_matches \
        "ms-image imaging Worker" \
        'celery.*apps\.backend\.workers\.imaging_worker\.celery_app:celery_app.*[[:space:]]worker([[:space:]]|$)'; then
        conflict=true
    fi
    if print_process_matches \
        "ms-image imaging Beat" \
        'celery.*apps\.backend\.workers\.imaging_worker\.celery_app:celery_app.*[[:space:]]beat([[:space:]]|$)'; then
        conflict=true
    fi
    if [[ "$conflict" == "true" ]]; then
        fail "Refusing to start alongside an existing ms-image local-chain process"
    fi
}

own_processes_alive() {
    local pid
    for pid in "${OWN_PIDS[@]}"; do
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "Launcher-owned process exited before readiness: PID $pid" >&2
            return 1
        fi
    done
}

probe_health() {
    "$PYTHON" - "http://127.0.0.1:${API_PORT}/api/v1/health" <<'PY'
import json
import sys
import urllib.error
import urllib.request

try:
    with urllib.request.urlopen(sys.argv[1], timeout=3) as response:
        status = response.status
        payload = json.loads(response.read())
except (OSError, ValueError, urllib.error.URLError):
    raise SystemExit(1)
data = payload.get("data") or {}
ok = status == 200 and payload.get("success") is True and data.get("status") == "healthy"
raise SystemExit(0 if ok else 1)
PY
}

probe_readiness() {
    "$PYTHON" - "http://127.0.0.1:${API_PORT}/api/v1/readiness" <<'PY'
import json
import sys
import urllib.error
import urllib.request

try:
    with urllib.request.urlopen(sys.argv[1], timeout=3) as response:
        status = response.status
        body = response.read()
except urllib.error.HTTPError as exc:
    status = exc.code
    body = exc.read()
except (OSError, urllib.error.URLError):
    raise SystemExit(1)
try:
    payload = json.loads(body)
except (TypeError, ValueError):
    raise SystemExit(1)
data = payload.get("data") or {}
components = data.get("components") or {}
database = components.get("database") or {}
redis = components.get("redis") or {}
broker = components.get("imaging_broker") or {}
ok = (
    status == 200
    and payload.get("success") is True
    and data.get("ready") is True
    and data.get("worker_ready") is True
    and database.get("ready") is True
    and redis.get("ready") is True
    and broker.get("ready") is True
    and broker.get("consumer_count") == 1
)
raise SystemExit(0 if ok else 1)
PY
}

probe_relay_heartbeat() {
    "$PYTHON" - "$RELAY_HEARTBEAT_PATH" "$STARTED_AT_EPOCH" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
started_at = float(sys.argv[2])
try:
    fresh = path.is_file() and path.stat().st_mtime >= started_at
except OSError:
    fresh = False
raise SystemExit(0 if fresh else 1)
PY
}

wait_for_probe() {
    local description="$1"
    local probe="$2"
    local deadline=$(( $(date +%s) + STARTUP_TIMEOUT_SECONDS ))
    while (( $(date +%s) < deadline )); do
        own_processes_alive || return 1
        if "$probe"; then
            echo "$description: ready"
            return 0
        fi
        sleep 1
    done
    fail "$description did not become ready within ${STARTUP_TIMEOUT_SECONDS}s"
}

acquire_lock
preflight_process_ownership

if [[ ! -x "$PYTHON" ]]; then
    fail "Python 3.12 executable not found at $PYTHON"
fi
if [[ ! -f "$PUB" ]]; then
    fail "Missing dev RSA public key at $PUB; run scripts/dev/gen_dev_keys.py"
fi
if [[ ! -f "$FAST_ENV" ]]; then
    fail "Missing ms-ai-fast environment file at $FAST_ENV"
fi
if [[ ! -f "$IMAGE_ENV" ]]; then
    fail "Missing ms-image environment file at $IMAGE_ENV"
fi

PLATFORM_BASE="http://8.149.245.40:8060/api/v1"
PLATFORM_KEY="$("$PYTHON" - "$FAST_ENV" <<'PY'
from dotenv import dotenv_values
import sys

print(dotenv_values(sys.argv[1]).get("AI_PLATFORM_API_KEY", ""))
PY
)"
NACOS_VALUES="$("$PYTHON" - "$IMAGE_ENV" <<'PY'
from dotenv import dotenv_values
import sys

values = dotenv_values(sys.argv[1])
for key, default in (
    ("NACOS_SERVER_ADDR", ""),
    ("NACOS_CONTEXT_PATH", "/nacos"),
    ("NACOS_USERNAME", ""),
    ("NACOS_PASSWORD", ""),
    ("NACOS_PROMPT_TIMEOUT_SECONDS", "10"),
):
    value = values.get(key, default)
    print("" if value is None else value)
PY
)"
RUNTIME_AUTH_VALUES="$("$PYTHON" - "$IMAGE_ENV" <<'PY'
from dotenv import dotenv_values
import os
import sys

values = dotenv_values(sys.argv[1])
for key, default in (
    ("BASIC_AUTH_USERNAME", ""),
    ("BASIC_AUTH_PASSWORD", ""),
    ("BASIC_AUTH_SUBJECT", "ms-image-basic-user"),
    ("BASIC_AUTH_SCOPES", "imaging:run"),
):
    value = os.environ[key] if key in os.environ else values.get(key, default)
    print("" if value is None else value)
PY
)"
{
    IFS= read -r NACOS_SERVER_ADDR
    IFS= read -r NACOS_CONTEXT_PATH
    IFS= read -r NACOS_USERNAME
    IFS= read -r NACOS_PASSWORD
    IFS= read -r NACOS_PROMPT_TIMEOUT_SECONDS
} <<< "$NACOS_VALUES"
{
    IFS= read -r BASIC_AUTH_USERNAME
    IFS= read -r BASIC_AUTH_PASSWORD
    IFS= read -r BASIC_AUTH_SUBJECT
    IFS= read -r BASIC_AUTH_SCOPES
} <<< "$RUNTIME_AUTH_VALUES"
if [[ -z "$PLATFORM_KEY" ]]; then
    fail "AI_PLATFORM_API_KEY is missing"
fi
if [[ -z "$NACOS_SERVER_ADDR" ]]; then
    fail "NACOS_SERVER_ADDR is missing"
fi
if [[ -z "$BASIC_AUTH_USERNAME" || -z "$BASIC_AUTH_PASSWORD" ]]; then
    fail "BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD must be configured for the local Runtime chain"
fi

export PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}"
export RSA_PUBLIC_KEY_PATH="$PUB"
export SECRET_KEY="$(<"$PUB")"
export APPLICATION_PORT="$API_PORT"
export AI_PLATFORM_OPENAI_BASE_URL="$PLATFORM_BASE"
export AI_PLATFORM_API_KEY="$PLATFORM_KEY"
export PROMPT_RUNTIME_PROVIDER="nacos"
export PROMPT_RUNTIME_CALLER_SERVICE="ms-image"
export NACOS_SERVER_ADDR
export NACOS_CONTEXT_PATH
export NACOS_USERNAME
export NACOS_PASSWORD
export NACOS_PROMPT_NAMESPACE_ID="c0cc9e0e-0fed-4faf-bc57-e9bab46a78a9"
export NACOS_PROMPT_TIMEOUT_SECONDS
export BASIC_AUTH_USERNAME
export BASIC_AUTH_PASSWORD
export BASIC_AUTH_SUBJECT
export BASIC_AUTH_SCOPES
export BROKER_ENABLED=true
export AI_ATTEMPT_RECONCILE_SCHEDULE_ENABLED=false
export AI_ATTEMPT_RECONCILE_POLICY_VERSION="${AI_ATTEMPT_RECONCILE_POLICY_VERSION:-ai-attempt-reconcile.v1}"
export AI_ATTEMPT_RECONCILE_MAX_COUNT="${AI_ATTEMPT_RECONCILE_MAX_COUNT:-3}"
export AI_ATTEMPT_RECONCILE_MAX_UNKNOWN_AGE_SECONDS="${AI_ATTEMPT_RECONCILE_MAX_UNKNOWN_AGE_SECONDS:-10800}"

STARTED_AT_EPOCH="$(date +%s)"

echo "Starting local Runtime API on 127.0.0.1:$API_PORT ..."
"$PYTHON" -m uvicorn apps.backend.services.runtime.main:app \
    --host 127.0.0.1 --port "$API_PORT" --log-level info &
API_PID=$!
OWN_PIDS+=("$API_PID")
wait_for_probe "Runtime health" probe_health

echo "Starting imaging outbox relay ..."
"$PYTHON" -m apps.backend.workers.imaging_worker.outbox_relay &
RELAY_PID=$!
OWN_PIDS+=("$RELAY_PID")

echo "Starting imaging celery worker ..."
"$PYTHON" -m celery -A apps.backend.workers.imaging_worker.celery_app:celery_app \
    worker --loglevel=INFO --concurrency="$WORKER_CONCURRENCY" \
    --queues=imaging.image.validate --hostname='ms-image-local@%h' &
WORKER_PID=$!
OWN_PIDS+=("$WORKER_PID")

wait_for_probe "Imaging relay heartbeat" probe_relay_heartbeat
wait_for_probe "Runtime readiness with exactly one imaging consumer" probe_readiness

echo
echo "Local Runtime, Relay and Worker are ready under one launcher owner."
echo "Imaging worker concurrency: $WORKER_CONCURRENCY"
echo "Reconcile scheduler enabled: false"
echo "API:      http://127.0.0.1:$API_PORT/api/v1/health"
echo "E2E run:  $REPO_ROOT/scripts/dev/run_e2e_local.py --help"
echo "Press Ctrl-C to stop."

while :; do
    own_processes_alive || exit 1
    sleep 2
done
