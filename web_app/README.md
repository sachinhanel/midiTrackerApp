MIDI Tracker - Web UI

This folder contains a Flask + Socket.IO web server that mirrors the Tkinter UI in a browser and broadcasts live updates.

Getting started

1. Install dependencies in your Python environment (recommended to use a venv):

   python -m pip install -r requirements.txt

2. Run the web server (from this folder):

   python server.py

   The server listens on 0.0.0.0:5000 by default so you can open http://<host-ip>:5000 on another machine.

3. Forward live events from your existing `main.py` to the web server by sending POST requests to http://localhost:5000/api/event. Example JSON payloads:

   {"active_notes": [60,64,67], "throughput": 24}
   {"type": "note_on", "note": 60, "velocity": 100}

You can add a small helper in `main.py` to POST updates when MIDI messages arrive. See the example below:

   import requests
   def post_event(payload):
       try:
           requests.post('http://localhost:5000/api/event', json=payload, timeout=0.5)
       except Exception:
           pass

Then call `post_event(...)` from your `process_midi_message` code paths.

Notes
- The web UI is intentionally lightweight and mirrors the core displays: dashboard, stats, heatmap and chord finder.
- The heatmap image endpoint is generated from the SQLite `note_distribution` table.
- The chord finder uses your existing `music21` logic via `chord_symbol_from_midi`.

WebSocket (lower latency) support
---------------------------------
By default the server will prefer `eventlet` for async websocket support if it's installed. `eventlet` provides efficient websocket handling and lower latency than polling. To enable:

1. Install eventlet in the web venv:

   pip install eventlet

2. Restart the server. If eventlet is available the server will log that it's using eventlet and the client will use websockets for lower-latency updates.

Note: On a Raspberry Pi with very rapid MIDI input, websockets are usually fine. If you have bursty updates you may want to rate-limit what you POST from `main.py` (for example, only send note-on/off and a short debug snippet) — I implemented minimal payloads already to reduce load.
