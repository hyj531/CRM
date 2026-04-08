#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PY="$ROOT_DIR/.venv/bin/python"
FRONTEND_VITE="$ROOT_DIR/frontend/node_modules/.bin/vite"

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

kill_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t || true)"
    if [[ -n "${pids}" ]]; then
      echo "Killing processes on port ${port}: ${pids}"
      kill -9 ${pids} >/dev/null 2>&1 || true
    fi
  fi
}

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

echo "Starting backend..."
cd "$ROOT_DIR"
nohup "$BACKEND_PY" manage.py runserver 127.0.0.1:8000 --noreload > /tmp/django.log 2>&1 &
BACK_PID=$!

echo "Starting frontend..."
cd "$ROOT_DIR/frontend"
nohup "$FRONTEND_VITE" --host 127.0.0.1 --port 5173 > /tmp/vite.log 2>&1 &
FRONT_PID=$!

echo "Backend PID: ${BACK_PID}"
echo "Frontend PID: ${FRONT_PID}"
echo "Backend:  http://127.0.0.1:8000/"
echo "Frontend: http://127.0.0.1:5173/app/"
echo "Logs: /tmp/django.log, /tmp/vite.log"
