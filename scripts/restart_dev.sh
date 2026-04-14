#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PY="$ROOT_DIR/.venv/bin/python"
FRONTEND_VITE="$ROOT_DIR/frontend/node_modules/.bin/vite"
BACKEND_LOG="/tmp/django.log"
FRONTEND_LOG="/tmp/vite.log"
BACKEND_URL="http://127.0.0.1:8000/app/"
FRONTEND_URL="http://127.0.0.1:5173/app/"

guard_dev_only() {
  # Must be the expected repo path
  if [[ "$ROOT_DIR" != "/Users/yuanjia/python/CRM" ]]; then
    echo "This script is restricted to the local dev repo at /Users/yuanjia/python/CRM."
    exit 1
  fi

  # Require dev env marker files
  if [[ ! -f "$ROOT_DIR/.env.dev" ]]; then
    echo "Missing .env.dev. This script is dev-only."
    exit 1
  fi

  # Block explicit production settings
  if [[ "${ENV:-}" == "prod" || "${ENV:-}" == "production" ]]; then
    echo "ENV indicates production. Refusing to run."
    exit 1
  fi
  if [[ "${DJANGO_SETTINGS_MODULE:-}" == *"prod"* || "${DJANGO_SETTINGS_MODULE:-}" == *"production"* ]]; then
    echo "DJANGO_SETTINGS_MODULE looks like production. Refusing to run."
    exit 1
  fi
}

guard_dev_only

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd"
    exit 1
  fi
}

kill_port() {
  local port="$1"
  local pids
  pids="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t || true)"
  if [[ -n "${pids}" ]]; then
    echo "Stopping processes on port ${port}: ${pids}"
    kill ${pids} >/dev/null 2>&1 || true
    sleep 0.5
    local remaining
    remaining="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t || true)"
    if [[ -n "${remaining}" ]]; then
      echo "Force killing processes on port ${port}: ${remaining}"
      kill -9 ${remaining} >/dev/null 2>&1 || true
    fi
  fi
}

wait_for_port() {
  local port="$1"
  local retries="${2:-80}"
  local i
  for ((i=1; i<=retries; i++)); do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done
  return 1
}

wait_for_http() {
  local url="$1"
  local retries="${2:-80}"
  local i
  for ((i=1; i<=retries; i++)); do
    local code
    code="$(curl -sS -o /dev/null -w '%{http_code}' "$url" || true)"
    if [[ "$code" != "000" ]]; then
      return 0
    fi
    sleep 0.25
  done
  return 1
}

print_logs_on_failure() {
  echo "---- backend log tail ----"
  tail -n 80 "$BACKEND_LOG" 2>/dev/null || true
  echo "---- frontend log tail ----"
  tail -n 80 "$FRONTEND_LOG" 2>/dev/null || true
}

require_cmd lsof
require_cmd curl

echo "Stopping any processes on ports 8000 and 5173..."
kill_port 8000
kill_port 5173

if [[ ! -x "$BACKEND_PY" ]]; then
  echo "Backend python not found: $BACKEND_PY"
  exit 1
fi

if [[ ! -x "$FRONTEND_VITE" ]]; then
  echo "Frontend vite not found: $FRONTEND_VITE"
  exit 1
fi

: > "$BACKEND_LOG"
: > "$FRONTEND_LOG"

echo "Starting backend..."
cd "$ROOT_DIR"
nohup "$BACKEND_PY" manage.py runserver 127.0.0.1:8000 --noreload > "$BACKEND_LOG" 2>&1 &
BACK_PID=$!

echo "Starting frontend..."
cd "$ROOT_DIR/frontend"
nohup "$FRONTEND_VITE" --host 127.0.0.1 --port 5173 --strictPort > "$FRONTEND_LOG" 2>&1 &
FRONT_PID=$!

if ! wait_for_port 8000; then
  echo "Backend failed to listen on 8000."
  print_logs_on_failure
  exit 1
fi

if ! wait_for_port 5173; then
  echo "Frontend failed to listen on 5173."
  print_logs_on_failure
  exit 1
fi

if ! wait_for_http "$BACKEND_URL"; then
  echo "Backend HTTP check failed: $BACKEND_URL"
  print_logs_on_failure
  exit 1
fi

if ! wait_for_http "$FRONTEND_URL"; then
  echo "Frontend HTTP check failed: $FRONTEND_URL"
  print_logs_on_failure
  exit 1
fi

echo "Backend PID: ${BACK_PID}"
echo "Frontend PID: ${FRONT_PID}"
echo "Backend:  ${BACKEND_URL}"
echo "Frontend: ${FRONTEND_URL}"
echo "Logs: ${BACKEND_LOG}, ${FRONTEND_LOG}"
