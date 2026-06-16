#!/usr/bin/env bash
# run.sh — 启动 Web 服务
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
HOST="${HOST:-0.0.0.0}"; PORT="${PORT:-8000}"
PY="$DIR/.venv/bin/python"; [ -x "$PY" ] || PY=python3
exec "$PY" -m uvicorn app:app --host "$HOST" --port "$PORT"
