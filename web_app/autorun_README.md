Autostart on Raspberry Pi (systemd)

This folder includes helper scripts and a suggested systemd setup to run the web server and the main app automatically at boot.

1) Create a Python virtualenv in the project root and install requirements:

   python3 -m venv .venv
   . .venv/bin/activate
   pip install -r web_app/requirements.txt

2) Copy the systemd service files to /etc/systemd/system/:
   (Use sudo)

   sudo cp web_app/midi-web.service /etc/systemd/system/
   sudo cp midi-main.service /etc/systemd/system/

3) Enable and start services:

   sudo systemctl daemon-reload
   sudo systemctl enable midi-web.service
   sudo systemctl enable midi-main.service
   sudo systemctl start midi-web.service
   sudo systemctl start midi-main.service

Notes:
- The web service runs the web_app/start_web.sh script which starts the Flask+Socket.IO server.
- The main service runs start_main.sh from the project root.
- Adjust paths and users in the .service files below to fit your Pi setup.

Security/Robustness suggestions:
- Run services under a dedicated user (e.g., "midi") rather than root.
- Use a virtualenv per-user and ensure the venv path is set in the .service file's ExecStart or the script.
- If you run headless, ensure the main app can run without a GUI (or run it under an X server if you need GUI). For purely headless usage you may want to remove Tk GUI components or use xvfb-run.
