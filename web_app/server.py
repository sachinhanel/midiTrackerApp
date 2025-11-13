import os
import time
import threading
import io
import json
from datetime import datetime
import sys

from flask import Flask, render_template, request, send_file, jsonify
from flask_socketio import SocketIO, emit
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Ensure project root is on sys.path so imports work when running from web_app/
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import project modules (now that project root is on sys.path)
from database_manager import DatabaseManager
from energy_calculator import PianoEnergyCalculator
from chord_window_m21 import chord_symbol_from_midi

# LED control is handled by main.py on port 5001
# Web server just proxies requests
import requests as http_requests

MAIN_APP_URL = 'http://127.0.0.1:5001'

app = Flask(__name__, static_folder='static', template_folder='templates')
# Prefer eventlet if available for efficient websocket handling; fall back to threading for dev
async_mode = 'threading'
try:
    import eventlet  # type: ignore
    async_mode = 'eventlet'
    print('[web_app] eventlet available: using eventlet async mode')
except Exception:
    print('[web_app] eventlet not available: falling back to threading async mode')

socketio = SocketIO(app, cors_allowed_origins='*', async_mode=async_mode)

# Initialize DB and helpers using project root path
db_path = os.path.join(project_root, 'midi_tracker.db')
db = DatabaseManager(db_path)
energy_calc = PianoEnergyCalculator()

# In-memory state for live events
current_state = {
    'active_notes': [],
    'sustained_notes': [],
    'pedal_pressed': False,
    'throughput': 0,
    'debug_messages': [],
}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/statistics')
def statistics():
    return render_template('statistics.html')


@app.route('/heatmap')
def heatmap():
    return render_template('heatmap.html')


@app.route('/chords')
def chords():
    return render_template('chords.html')


@app.route('/devices')
def devices():
    return render_template('devices.html')


@app.route('/api/control/devices')
def proxy_devices():
    """Proxy to the local control API in main.py to get device list."""
    try:
        import requests
        r = requests.get('http://127.0.0.1:5001/midi/devices', timeout=1.0)
        return (r.content, r.status_code, {'Content-Type': 'application/json'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/control/restart_service', methods=['POST'])
def restart_service():
    """Restart the MIDI main service."""
    try:
        import subprocess
        # Execute systemctl restart command
        result = subprocess.run(
            ['sudo', 'systemctl', 'restart', 'midi-main.service'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return jsonify({'ok': True, 'message': 'Service restart initiated. Please wait a few seconds for reconnection.'})
        else:
            return jsonify({'ok': False, 'error': f'Restart failed: {result.stderr}'}), 500
    except subprocess.TimeoutExpired:
        return jsonify({'ok': False, 'error': 'Restart command timed out'}), 500
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/control/rescan', methods=['POST'])
def proxy_rescan():
    try:
        import requests
        r = requests.post('http://127.0.0.1:5001/midi/rescan', timeout=1.0)
        return (r.content, r.status_code, {'Content-Type': 'application/json'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/control/select', methods=['POST'])
def proxy_select():
    try:
        import requests
        payload = request.get_json(force=True)
        r = requests.post('http://127.0.0.1:5001/midi/select', json=payload, timeout=1.0)
        return (r.content, r.status_code, {'Content-Type': 'application/json'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/control/status')
def proxy_status():
    try:
        import requests
        r = requests.get('http://127.0.0.1:5001/midi/status', timeout=1.0)
        return (r.content, r.status_code, {'Content-Type': 'application/json'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/stats/daily')
def api_daily_stats():
    # Query daily_stats table for last 30 days
    try:
        cur = db.conn.cursor()
        cur.execute("SELECT date, total_notes, session_time_seconds, total_duration_ms, total_bytes, total_energy, avg_velocity FROM daily_stats ORDER BY date DESC LIMIT 60")
        rows = cur.fetchall()
        data = [{'date': r[0], 'total_notes': r[1], 'session_seconds': r[2], 'note_time_ms': r[3], 'total_data': r[4], 'total_energy': r[5], 'avg_velocity': r[6]} for r in rows]
        return jsonify({'ok': True, 'data': data})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/stats/hourly')
def api_hourly_stats():
    try:
        cur = db.conn.cursor()
        cur.execute("SELECT date, hour, total_notes, session_time_seconds, total_duration_ms, total_bytes, total_energy FROM hourly_stats ORDER BY date DESC, hour DESC LIMIT 240")
        rows = cur.fetchall()
        data = [{'date': r[0], 'hour': r[1], 'total_notes': r[2], 'session_seconds': r[3], 'note_time_ms': r[4], 'total_data': r[5], 'total_energy': r[6]} for r in rows]
        return jsonify({'ok': True, 'data': data})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/stats/weekly')
def api_weekly_stats():
    try:
        cur = db.conn.cursor()
        # Aggregate daily rows into ISO week buckets (strftime('%Y-%W') groups by year-week)
        cur.execute("""
            SELECT sub.week AS week_key, MIN(sub.date) AS week_start, SUM(sub.total_notes) AS total_notes,
                   SUM(sub.session_time_seconds) AS session_seconds, SUM(sub.total_duration_ms) AS note_time_ms,
                   SUM(sub.total_bytes) AS total_data, SUM(sub.total_energy) AS total_energy
            FROM (
                SELECT date, total_notes, session_time_seconds, total_duration_ms, total_bytes, total_energy, strftime('%Y-%W', date) AS week
                FROM daily_stats
            ) AS sub
            GROUP BY sub.week
            ORDER BY sub.week DESC
            LIMIT 52
        """)
        rows = cur.fetchall()
        data = [{'week_start': r[1], 'week_key': r[0], 'total_notes': r[2] or 0, 'session_seconds': r[3] or 0, 'note_time_ms': r[4] or 0, 'total_data': r[5] or 0, 'total_energy': r[6] or 0} for r in rows]
        return jsonify({'ok': True, 'data': data})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/stats/monthly')
def api_monthly_stats():
    try:
        cur = db.conn.cursor()
        # Aggregate daily rows into month buckets (YYYY-MM) and return last 24 months
        cur.execute("""
            SELECT strftime('%Y-%m', date) AS month_key, MIN(date) AS month_start,
                   SUM(total_notes) AS total_notes, SUM(session_time_seconds) AS session_seconds,
                   SUM(total_duration_ms) AS note_time_ms, SUM(total_bytes) AS total_data,
                   SUM(total_energy) AS total_energy
            FROM daily_stats
            GROUP BY month_key
            ORDER BY month_key DESC
            LIMIT 24
        """)
        rows = cur.fetchall()
        data = [{'month_start': r[1], 'month_key': r[0], 'total_notes': r[2] or 0, 'session_seconds': r[3] or 0, 'note_time_ms': r[4] or 0, 'total_data': r[5] or 0, 'total_energy': r[6] or 0} for r in rows]
        return jsonify({'ok': True, 'data': data})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/stats/trends')
def api_trends_stats():
    try:
        cur = db.conn.cursor()
        cur.execute("SELECT date, total_notes, session_time_seconds, total_duration_ms, total_bytes, total_energy FROM daily_stats ORDER BY date DESC LIMIT 1000")
        rows = cur.fetchall()
        data = [{'date': r[0], 'total_notes': r[1], 'session_seconds': r[2], 'note_time_ms': r[3], 'total_data': r[4], 'total_energy': r[5]} for r in rows]
        return jsonify({'ok': True, 'data': data})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/note_distribution')
def api_note_distribution():
    """Return note distribution rows for a given date (default today) and overall totals.

    Response shape: { ok: True, date: 'YYYY-MM-DD', notes: [ { midi_note, note_name, count, total_velocity, avg_velocity, total_energy, note_bytes, total_duration_ms, percent }... ], totals: { total_notes, total_velocity, avg_velocity, total_energy, total_duration_ms } }
    """
    date = request.args.get('date') or datetime.now().strftime('%Y-%m-%d')
    try:
        cur = db.conn.cursor()
        cur.execute('''SELECT midi_note, note_name, count, total_velocity, total_energy, note_bytes, total_duration_ms
                       FROM note_distribution WHERE date=? ORDER BY midi_note''', (date,))
        rows = cur.fetchall()

        # Build a dict keyed by midi_note
        row_map = {r[0]: {'midi_note': r[0], 'note_name': r[1] or '', 'count': r[2] or 0,
                          'total_velocity': r[3] or 0, 'total_energy': r[4] or 0,
                          'note_bytes': r[5] or 0, 'total_duration_ms': r[6] or 0}
                  for r in rows}

        # Typical piano midi range (A0=21 .. C8=108)
        midi_min, midi_max = 21, 108
        notes = []
        total_notes = 0
        total_velocity = 0
        total_energy = 0
        total_duration = 0

        for n in range(midi_min, midi_max + 1):
            entry = row_map.get(n, {'midi_note': n, 'note_name': '', 'count': 0, 'total_velocity': 0, 'total_energy': 0, 'note_bytes': 0, 'total_duration_ms': 0})
            entry['avg_velocity'] = (entry['total_velocity'] / entry['count']) if entry['count'] else 0
            notes.append(entry)
            total_notes += entry['count']
            total_velocity += entry['total_velocity']
            total_energy += entry['total_energy']
            total_duration += entry['total_duration_ms']

        # Compute percent per note (avoid div by zero)
        for entry in notes:
            entry['percent'] = (entry['count'] / total_notes * 100.0) if total_notes else 0.0

        totals = {
            'total_notes': total_notes,
            'total_velocity': total_velocity,
            'avg_velocity': (total_velocity / total_notes) if total_notes else 0,
            'total_energy': total_energy,
            'total_duration_ms': total_duration,
        }

        return jsonify({'ok': True, 'date': date, 'notes': notes, 'totals': totals})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/stats/all_totals')
def api_all_totals():
    """Return all-time totals aggregated from daily_stats."""
    try:
        cur = db.conn.cursor()
        # Use note_distribution counts as authoritative for total_notes (avoids duplication issues)
        cur.execute("SELECT SUM(count) FROM note_distribution")
        r_notes = cur.fetchone()
        total_notes = int(r_notes[0] or 0)

        # Sum other aggregated fields from daily_stats
        cur.execute("SELECT SUM(total_energy), SUM(total_velocity), SUM(total_duration_ms), SUM(session_time_seconds), SUM(pedal_presses), SUM(total_bytes), SUM(sessions) FROM daily_stats")
        r = cur.fetchone()
        total_energy = float(r[0] or 0.0)
        total_velocity = float(r[1] or 0.0)
        total_duration_ms = float(r[2] or 0.0)
        total_session_seconds = float(r[3] or 0.0)
        total_pedal_presses = int(r[4] or 0)
        total_bytes = int(r[5] or 0)
        total_sessions = int(r[6] or 0)

        avg_velocity = (total_velocity / total_notes) if total_notes else 0

        # Convert bytes to megabytes for display
        total_midi_mb = (total_bytes or 0) / (1024.0 * 1024.0)

        # report session hours and note duration hours
        total_note_duration_hours = (total_duration_ms or 0) / (1000.0 * 3600.0)
        total_practice_hours = (total_session_seconds or 0) / 3600.0

        return jsonify({'ok': True, 'totals': {
            'total_notes': total_notes,
            'total_energy': total_energy,
            'avg_velocity': avg_velocity,
            'total_duration_ms': total_duration_ms,
            'total_note_duration_hours': total_note_duration_hours,
            'total_practice_hours': total_practice_hours,
            'total_pedal_presses': total_pedal_presses,
            'total_midi_mb': total_midi_mb,
            'total_sessions': total_sessions
        }})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/heatmap_distribution')
def api_heatmap_distribution():
    """Return aggregated note counts for heatmap rendering.

    Query params:
      - range: 'daily','hourly','weekly','monthly','trends'
      - date: YYYY-MM-DD (for daily/hourly/weekly/monthly - used as reference point)
    Response: { ok: True, notes: [ { midi_note, count, total_velocity, total_energy, total_duration_ms, note_name } ... ], totals: { total_notes, total_energy, avg_velocity } }
    """
    qrange = request.args.get('range') or 'daily'
    date = request.args.get('date') or datetime.now().strftime('%Y-%m-%d')
    try:
        cur = db.conn.cursor()
        # For daily/hourly we can use note_distribution table; for aggregated ranges sum across days
        if qrange in ('daily','hourly'):
            # use specific date
            cur.execute('''SELECT midi_note, note_name, SUM(count), SUM(total_velocity), SUM(total_energy), SUM(total_duration_ms)
                          FROM note_distribution WHERE date=? GROUP BY midi_note ORDER BY midi_note''', (date,))
            rows = cur.fetchall()
        else:
            # aggregate across daily_stats range: for monthly/weekly/trends sum note_distribution across matching dates
            if qrange == 'monthly':
                # Use the selected date to determine which month (YYYY-MM)
                month_prefix = date[:7]  # Extract YYYY-MM from YYYY-MM-DD
                cur.execute('''SELECT midi_note, note_name, SUM(count), SUM(total_velocity), SUM(total_energy), SUM(total_duration_ms)
                              FROM note_distribution WHERE date LIKE ? || '%' GROUP BY midi_note ORDER BY midi_note''', (month_prefix,))
            elif qrange == 'weekly':
                # Aggregate 7 days starting from the selected date
                cur.execute('''SELECT midi_note, note_name, SUM(count), SUM(total_velocity), SUM(total_energy), SUM(total_duration_ms)
                              FROM note_distribution WHERE date >= ? AND date < date(?, '+7 days')
                              GROUP BY midi_note ORDER BY midi_note''', (date, date))
            elif qrange == 'trends':
                # all-time
                cur.execute('''SELECT midi_note, note_name, SUM(count), SUM(total_velocity), SUM(total_energy), SUM(total_duration_ms)
                              FROM note_distribution GROUP BY midi_note ORDER BY midi_note''')
            else:
                # default: last 30 days from selected date
                cur.execute('''SELECT midi_note, note_name, SUM(count), SUM(total_velocity), SUM(total_energy), SUM(total_duration_ms)
                              FROM note_distribution WHERE date >= date(?, '-29 days') AND date <= ?
                              GROUP BY midi_note ORDER BY midi_note''', (date, date))
            rows = cur.fetchall()

        notes = [{'midi_note': r[0], 'note_name': r[1], 'count': r[2] or 0, 'total_velocity': r[3] or 0,
                  'total_energy': r[4] or 0, 'total_duration_ms': r[5] or 0} for r in rows]
        total_notes = sum(n['count'] for n in notes)
        total_energy = sum(n['total_energy'] for n in notes)
        total_velocity = sum(n['total_velocity'] for n in notes)
        avg_velocity = (total_velocity / total_notes) if total_notes > 0 else 0
        return jsonify({'ok': True, 'notes': notes, 'totals': {'total_notes': total_notes, 'total_energy': total_energy, 'avg_velocity': avg_velocity}})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/heatmap.png')
def api_heatmap_png():
    # Render a simple heatmap of note counts for today from note_distribution
    date = request.args.get('date') or datetime.now().strftime('%Y-%m-%d')
    try:
        cur = db.conn.cursor()
        cur.execute('SELECT midi_note, count FROM note_distribution WHERE date=?', (date,))
        rows = cur.fetchall()
        counts = {r[0]: r[1] for r in rows}

        # Prepare data for 12-note roll over many octaves (map to midi 21-108 typical piano range)
        midi_min, midi_max = 21, 108
        notes = list(range(midi_min, midi_max + 1))
        values = [counts.get(n, 0) for n in notes]

        fig, ax = plt.subplots(figsize=(10,2))
        ax.bar(range(len(notes)), values, color='#2b8cbe')
        ax.set_xticks([i for i in range(0, len(notes), 12)])
        ax.set_xticklabels([f'{((n)%12)}' for n in notes[::12]])
        ax.set_title(f'Note counts for {date}')
        ax.set_ylabel('Count')
        plt.tight_layout()

        img_bytes = io.BytesIO()
        fig.savefig(img_bytes, format='png')
        plt.close(fig)
        img_bytes.seek(0)
        return send_file(img_bytes, mimetype='image/png')

    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/event', methods=['POST'])
def api_event():
    """Receive live MIDI events (from your existing main app) as JSON and broadcast to connected browsers."""
    try:
        payload = request.get_json(force=True)
        # Example payload: {"type":"note_on","note":60,"velocity":100}
        # We accept more generic state updates too: {"active_notes": [60,64,67]}
        if not payload:
            return jsonify({'ok': False, 'error': 'empty payload'}), 400

        # Update in-memory state with allowed keys
        for k in ('active_notes', 'sustained_notes', 'pedal_pressed', 'throughput', 'debug_messages'):
            if k in payload:
                current_state[k] = payload[k]

        # If the caller supplies debug_messages, accept them; do not auto-append raw note_on lines here
        if 'debug_messages' in payload:
            # keep only the last 200
            current_state['debug_messages'] = (payload.get('debug_messages') or [])[-200:]

        # Broadcast updated state to all connected clients
        print(f"[web_app] api_event received: {list(payload.keys())}")
        socketio.emit('state_update', current_state, broadcast=True)

        # If there are active notes, compute chord and send
        if current_state.get('active_notes'):
            midi_nums = sorted(set(current_state['active_notes']))
            if len(midi_nums) >= 2:
                sym, det = chord_symbol_from_midi(midi_nums)
            else:
                sym, det = None, None
            socketio.emit('chord_update', {'symbol': sym, 'details': det, 'notes': midi_nums}, broadcast=True)

        return jsonify({'ok': True})

    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@socketio.on('connect')
def on_connect():
    # Send initial state and a small stats snapshot
    print('[web_app] client connected')
    emit_data = current_state.copy()
    # small stats snapshot
    try:
        cur = db.conn.cursor()
        cur.execute('SELECT total_notes, total_energy FROM daily_stats WHERE date=?', (datetime.now().strftime('%Y-%m-%d'),))
        r = cur.fetchone()
        emit_data['today'] = {'total_notes': r[0] if r else 0, 'total_energy': r[1] if r else 0}
    except Exception:
        emit_data['today'] = {}

    # Use emit to send only to the newly connected client
    emit('state_update', emit_data)


@app.route('/api/state')
def api_state():
    """Return current in-memory live state snapshot (useful for polling fallback)."""
    try:
        return jsonify({'ok': True, 'state': current_state})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# LED Strip Control API Endpoints (proxy to main app on port 5001)
@app.route('/api/led/status')
def api_led_status():
    """Get LED controller status (proxy to main app)"""
    try:
        resp = http_requests.get(f'{MAIN_APP_URL}/api/led/status', timeout=2)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Cannot connect to main app: {str(e)}'}), 500


@app.route('/api/led/enable', methods=['POST'])
def api_led_enable():
    """Enable LED visualization (proxy to main app)"""
    try:
        resp = http_requests.post(f'{MAIN_APP_URL}/api/led/enable', timeout=2)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Cannot connect to main app: {str(e)}'}), 500


@app.route('/api/led/disable', methods=['POST'])
def api_led_disable():
    """Disable LED visualization (proxy to main app)"""
    try:
        resp = http_requests.post(f'{MAIN_APP_URL}/api/led/disable', timeout=2)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Cannot connect to main app: {str(e)}'}), 500


@app.route('/api/led/test', methods=['POST'])
def api_led_test():
    """Run LED test pattern (proxy to main app)"""
    try:
        resp = http_requests.post(f'{MAIN_APP_URL}/api/led/test', timeout=5)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Cannot connect to main app: {str(e)}'}), 500


@app.route('/api/led/brightness', methods=['POST'])
def api_led_brightness():
    """Set LED brightness (proxy to main app)"""
    try:
        resp = http_requests.post(f'{MAIN_APP_URL}/api/led/brightness',
                                 json=request.get_json(), timeout=2)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Cannot connect to main app: {str(e)}'}), 500


@app.route('/api/led/status_leds/toggle', methods=['POST'])
def api_led_status_leds_toggle():
    """Toggle status LEDs (proxy to main app)"""
    try:
        resp = http_requests.post(f'{MAIN_APP_URL}/api/led/status_leds/toggle', timeout=2)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Cannot connect to main app: {str(e)}'}), 500


@app.route('/api/led/preset', methods=['POST'])
def api_led_preset():
    """Set LED color preset (proxy to main app)"""
    try:
        resp = http_requests.post(f'{MAIN_APP_URL}/api/led/preset',
                                 json=request.get_json(), timeout=2)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Cannot connect to main app: {str(e)}'}), 500


@app.route('/api/led/preset/save', methods=['POST'])
def api_led_preset_save():
    """Save LED preset (proxy to main app)"""
    try:
        resp = http_requests.post(f'{MAIN_APP_URL}/api/led/preset/save', timeout=2)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Cannot connect to main app: {str(e)}'}), 500


@app.route('/api/led/preset/load', methods=['POST'])
def api_led_preset_load():
    """Load LED preset (proxy to main app)"""
    try:
        resp = http_requests.post(f'{MAIN_APP_URL}/api/led/preset/load', timeout=2)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Cannot connect to main app: {str(e)}'}), 500


def background_stats_broadcaster():
    """Periodically query DB for lightweight stats and broadcast to clients."""
    while True:
        try:
            cur = db.conn.cursor()
            cur.execute('SELECT date, total_notes, total_energy FROM daily_stats ORDER BY date DESC LIMIT 7')
            rows = cur.fetchall()
            socketio.emit('daily_snapshot', [{'date': r[0], 'total_notes': r[1], 'total_energy': r[2]} for r in rows])
        except Exception:
            pass
        time.sleep(5)


if __name__ == '__main__':
    # Start background broadcaster thread
    t = threading.Thread(target=background_stats_broadcaster, daemon=True)
    t.start()
    # Run server visible on LAN
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
