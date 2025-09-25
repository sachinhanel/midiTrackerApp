#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME=$(basename "$0")
usage(){
  cat <<EOF
Usage: sudo $SCRIPT_NAME [--user USERNAME] [--project-dir /abs/path/to/project]

Installs and enables systemd service units for the MIDI Tracker app.
It will create/update the following units under /etc/systemd/system:
  - midi-web.service
  - midi-main.service

By default USERNAME=swag and PROJECT_DIR is the current directory.
Example:
  sudo $SCRIPT_NAME --user swag --project-dir /home/swag/Documents/git/midiTrackerApp
EOF
  exit 1
}

USERNAME="swag"
PROJECT_DIR="$(pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)
      USERNAME="$2"; shift 2;;
    --project-dir)
      PROJECT_DIR="$2"; shift 2;;
    -h|--help)
      usage;;
    *)
      echo "Unknown arg: $1"; usage;;
  esac
done

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root (sudo). Re-running under sudo..."
  exec sudo bash "$0" --user "$USERNAME" --project-dir "$PROJECT_DIR"
fi

if ! id -u "$USERNAME" >/dev/null 2>&1; then
  echo "User '$USERNAME' does not exist. Create the user or pass an existing username with --user." >&2
  exit 2
fi

# normalize PROJECT_DIR
PROJECT_DIR=$(realpath "$PROJECT_DIR")
WEB_DIR="$PROJECT_DIR/web_app"

echo "Installing services for user=$USERNAME project=$PROJECT_DIR"

WEB_START="$WEB_DIR/start_web.sh"
MAIN_START="$PROJECT_DIR/start_main.sh"

if [[ ! -f "$WEB_START" ]]; then
  echo "Warning: start script not found: $WEB_START" >&2
fi
if [[ ! -f "$MAIN_START" ]]; then
  echo "Warning: start script not found: $MAIN_START" >&2
fi

# Ensure start scripts are executable and owned by the service user
if [[ -f "$WEB_START" ]]; then
  chmod +x "$WEB_START"
  chown "$USERNAME":"$USERNAME" "$WEB_START" || true
fi
if [[ -f "$MAIN_START" ]]; then
  chmod +x "$MAIN_START"
  chown "$USERNAME":"$USERNAME" "$MAIN_START" || true
fi

echo "Writing systemd unit files to /etc/systemd/system"

cat > /etc/systemd/system/midi-web.service <<EOF
[Unit]
Description=MIDI Tracker Web Server
After=network.target

[Service]
Type=simple
User=$USERNAME
WorkingDirectory=$WEB_DIR
ExecStart=/bin/sh $WEB_START
Restart=on-failure
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/midi-main.service <<EOF
[Unit]
Description=MIDI Tracker Main App
After=network.target midi-web.service

[Service]
Type=simple
User=$USERNAME
WorkingDirectory=$PROJECT_DIR
ExecStart=/bin/sh $MAIN_START
Restart=on-failure
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

echo "Reloading systemd and enabling services"
systemctl daemon-reload
systemctl enable --now midi-web.service
systemctl enable --now midi-main.service

echo "Services enabled. Current status (midi-web):"
systemctl status midi-web.service --no-pager -l || true

echo "Tailing journal (last 200 lines) for midi-web.service"
journalctl -u midi-web.service -n 200 --no-pager || true

echo "Install script complete. Reboot will start the services automatically." 
