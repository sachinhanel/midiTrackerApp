#!/bin/sh
# Small wrapper to start the web server (useful for systemd)
cd "$(dirname "$0")"
# Activate venv if present
if [ -d ".venv" ]; then
  . .venv/bin/activate
fi
python server.py
