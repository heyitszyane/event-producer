#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Open Settings in the app to choose a provider and save your key."
fi

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install -r requirements.txt
pnpm -C web install --frozen-lockfile

cleanup() {
  if [ -n "${BACKEND_PID:-}" ]; then kill "$BACKEND_PID" 2>/dev/null || true; fi
  if [ -n "${FRONTEND_PID:-}" ]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

.venv/bin/python -m uvicorn event_producer.main:create_app \
  --factory \
  --host 127.0.0.1 \
  --port 8080 \
  --reload \
  --env-file .env &
BACKEND_PID=$!

NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://127.0.0.1:8080}" \
  pnpm -C web run dev &
FRONTEND_PID=$!

echo "Backend:  http://127.0.0.1:8080"
echo "Frontend: http://127.0.0.1:3000"
echo "Open Route Map -> 10 Settings to configure Gemini, OpenRouter, LM Studio, or local models."

wait "$BACKEND_PID" "$FRONTEND_PID"
