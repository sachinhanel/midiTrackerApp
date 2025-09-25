#!/bin/sh
# Wrapper to start the main Tk app headlessly (for Pi you might run headless or with an X server)
cd "$(dirname "$0")"
# Activate venv if present
if [ -d ".venv" ]; then
  . .venv/bin/activate
fi
python main.py
