#!/bin/sh
set -eu

APP_DIR="/home/swag/Documents/git/midiTrackerApp/web_app"
VENV="/home/swag/Documents/git/.venv"

cd "$APP_DIR"

# Prefer the known venv; fall back to local ones; else system Python.
if [ -x "$VENV/bin/python" ]; then
  exec "$VENV/bin/python" server.py
elif [ -x ".venv/bin/python" ]; then
  exec ".venv/bin/python" server.py
elif [ -x "../.venv/bin/python" ]; then
  exec "../.venv/bin/python" server.py
else
  echo "Warning: no venv at $VENV, .venv, or ../.venv — using system python3" >&2
  exec python3 server.py
fi
