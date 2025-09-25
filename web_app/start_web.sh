#!/bin/sh
# Small wrapper to start the web server (useful for systemd)
cd "$(dirname "$0")"
# Robust virtualenv handling: prefer web_app/.venv, then ../.venv. If missing, fall back to system python3.
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
  exec python server.py
elif [ -f "../.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  . ../.venv/bin/activate
  exec python server.py
elif [ -x ".venv/bin/python" ]; then
  exec .venv/bin/python server.py
elif [ -x "../.venv/bin/python" ]; then
  exec ../.venv/bin/python server.py
else
  echo "Warning: virtualenv not found in .venv or ../.venv — falling back to system python3" >&2
  exec python3 server.py
fi
