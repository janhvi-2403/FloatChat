#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if ! command -v python >/dev/null 2>&1; then
  echo "Python is required" >&2
  exit 1
fi

if [ ! -d "$ROOT_DIR/venv" ]; then
  python -m venv venv
fi

source "$ROOT_DIR/venv/Scripts/activate" 2>/dev/null || source "$ROOT_DIR/venv/bin/activate" 2>/dev/null || true

python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt >/dev/null

if command -v redis-server >/dev/null 2>&1; then
  (redis-cli ping >/dev/null 2>&1) || (redis-server --daemonize yes || true)
fi

if command -v psql >/dev/null 2>&1; then
  (PGPASSWORD=password123 psql -h localhost -U admin -d floatchat -c 'SELECT 1' >/dev/null 2>&1) || true
fi

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
