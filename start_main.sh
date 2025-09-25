#!/bin/sh
# Wrapper to start the main Tk app headlessly (for Pi you might run headless or with an X server)
cd "$(dirname "$0")"
# Robust virtualenv handling for main app
if [ -f "web_app/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  . web_app/.venv/bin/activate
  exec python main.py
elif [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
  exec python main.py
elif [ -x "web_app/.venv/bin/python" ]; then
  exec web_app/.venv/bin/python main.py
elif [ -x ".venv/bin/python" ]; then
  exec .venv/bin/python main.py
else
  echo "Warning: virtualenv not found in web_app/.venv or .venv — falling back to system python3" >&2
  exec python3 main.py
fi
