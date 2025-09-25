#!/bin/sh
# Wrapper to start the main Tk app headlessly (for Pi you might run headless or with an X server)
cd "$(dirname "$0")"
# Activate venv if present in web_app/.venv or repo root .venv
if [ -d "web_app/.venv" ]; then
  . web_app/.venv/bin/activate
elif [ -d ".venv" ]; then
  . .venv/bin/activate
fi

# exec to let systemd track the Python process directly
exec python main.py
