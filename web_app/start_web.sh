#!/bin/sh
# Small wrapper to start the web server (useful for systemd)
cd "$(dirname "$0")"
# Activate venv if present. Try web_app/.venv then repo root ../.venv
if [ -d ".venv" ]; then
  . .venv/bin/activate
elif [ -d "../.venv" ]; then
  . ../.venv/bin/activate
fi

# Use exec so the python process replaces this shell (cleaner for systemd)
exec python server.py
