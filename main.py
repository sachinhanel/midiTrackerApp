import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import time
import threading
from collections import defaultdict, deque
import requests
import sys
import os
import queue
from datetime import datetime, timedelta

# Import our modules
from energy_calculator import PianoEnergyCalculator
from sleep_preventer import SleepPreventer
from database_manager import DatabaseManager
from statistics_window import StatisticsWindow
from heatmap_window import HeatmapWindow

from chord_window_m21 import Music21ChordWindow
from led_controller import get_led_controller

try:
    import rtmidi
    RTMIDI_AVAILABLE = True
except ImportError:
    RTMIDI_AVAILABLE = False

try:
    import matplotlib
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class MidiTrackerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MIDI Piano Keyboard Tracker")
        self.root.geometry("800x600")
        
        # Initialize components
        self.energy_calculator = PianoEnergyCalculator()
        self.sleep_preventer = SleepPreventer()
        self.sleep_prevention_enabled = tk.BooleanVar(value=True)
        
        # Initialize database with script-relative path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(script_dir, "midi_tracker.db")
        self.db_manager = DatabaseManager(db_path)
        self.conn = self.db_manager.conn  # For compatibility
        self.db_queue = self.db_manager.db_queue
        self.session_id = self.db_manager.session_id
        self.session_start = self.db_manager.session_start
        
        # Initialize window handlers
        self.statistics_window = StatisticsWindow(self)
        self.heatmap_window = HeatmapWindow(self)

        # Initialize LED controller
        self.led_controller = get_led_controller()

        # Session timing (practice time tracking)
        self.session_timer_start = None
        self.session_timer_total = 0
        self.last_activity_time = None
        self.session_pause_threshold = 40
        self.session_is_active = False

        # MIDI tracking data (current session only)
        self.note_counts = defaultdict(int)
        self.note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        self.bytes_received = 0
        self.start_time = None
        self.throughput_history = deque(maxlen=60)
        self.debug_messages = deque(maxlen=100)
        self.total_messages = 0
        
        # Per-note tracking for accurate statistics
        self.per_note_bytes = defaultdict(int)
        self.per_note_durations = defaultdict(float)
        self.per_note_energy = defaultdict(float)

        #sustained notes for chord detection
        self.sustained_notes = set()
                
        # Aggregated statistics (for database storage)
        self.current_day = datetime.now().strftime('%Y-%m-%d')
        self.current_hour = datetime.now().hour
        self.daily_stats = {
            'total_notes': 0,
            'total_duration_ms': 0,
            'total_velocity': 0,
            'total_energy': 0.0,
            'pedal_presses': 0,
            'note_bytes': 0,
            'other_bytes': 0,
            'session_time_seconds': 0
        }
        self.hourly_stats = defaultdict(lambda: {
            'total_notes': 0,
            'total_duration_ms': 0,
            'total_velocity': 0,
            'total_energy': 0.0,
            'pedal_presses': 0,
            'note_bytes': 0,
            'other_bytes': 0,
            'session_time_seconds': 0
        })
        
        # MIDI setup
        self.midi_input = None
        self.midi_output = None
        self.running = False
        self.passthrough_enabled = False
        
        # Session byte tracking
        self.note_bytes = 0
        self.other_bytes = 0
        
        # Auto-connection preferences
        self.auto_input_keyword = "XPIANO"
        self.auto_output_keyword = "loopmidi"
        self.auto_connect_enabled = True
        
        self.active_notes = {}
        
        # Pedal state tracking
        self.pedal_pressed = False
        
        # Throughput tracking
        self.bytes_in_last_second = 0
        self.last_second_reset = time.time()
        
        # Auto-save timer
        self.last_save_time = time.time()
        self.save_interval = 20
        
        self.chord_window = Music21ChordWindow(self)

        
        self.setup_gui()
        self.update_displays()
        self.process_db_queue()
        # Start control API (local only) for device selection and rescan
        try:
            self._start_control_server()
        except Exception:
            # non-fatal if Flask not available here; UI will still work
            self.add_debug_message_direct("Control API not started (Flask missing or error)")
    
    def post_event(self, payload):
        """Send a lightweight payload to the web UI server at /api/event.

        Non-blocking and tolerant: exceptions are swallowed to avoid disrupting MIDI handling.
        Logs failures to the debug message list so you can see connection issues.
        """
        try:
            requests.post('http://127.0.0.1:5000/api/event', json=payload, timeout=0.3)
        except Exception as e:
            # Add a debug message so you can see if posting to web UI failed
            try:
                self.add_debug_message_direct(f"🔗 Web UI post failed: {e}")
            except Exception:
                pass

    def _start_control_server(self):
        """Start a small Flask server on localhost to allow the web server to request device lists and selection.

        Runs in a daemon thread and schedules GUI actions via root.after for thread safety.
        """
        try:
            from flask import Flask, jsonify, request
        except Exception as e:
            raise

        app = Flask('midi_control')

        @app.route('/midi/devices')
        def midi_devices():
            # return a JSON list of available input ports
            try:
                if not RTMIDI_AVAILABLE:
                    return jsonify({'ok': False, 'error': 'rtmidi not available'})
                midiin = rtmidi.MidiIn()
                ports = midiin.get_ports()
                midiin.close_port()
                return jsonify({'ok': True, 'devices': ports})
            except Exception as e:
                return jsonify({'ok': False, 'error': str(e)})

        @app.route('/midi/rescan', methods=['POST'])
        def midi_rescan():
            try:
                # schedule refresh_devices on main thread
                self.root.after(0, self.refresh_devices)
                return jsonify({'ok': True})
            except Exception as e:
                return jsonify({'ok': False, 'error': str(e)})

        @app.route('/midi/select', methods=['POST'])
        def midi_select():
            try:
                data = request.get_json(force=True)
                if not data:
                    return jsonify({'ok': False, 'error': 'empty payload'})

                # Accept either index or name
                index = data.get('index')
                name = data.get('name')

                def _do_select():
                    try:
                        # Refresh device list first
                        self.refresh_devices()
                        values = list(self.device_combo['values'])
                        chosen_index = None
                        if index is not None and 0 <= int(index) < len(values):
                            chosen_index = int(index)
                        elif name is not None:
                            for i, v in enumerate(values):
                                if name.lower() in v.lower():
                                    chosen_index = i
                                    break

                        if chosen_index is None:
                            return

                        # select and connect
                        self.device_combo.current(chosen_index)
                        self.connect_device()
                    except Exception as e:
                        self.add_debug_message_direct(f"Device select error: {e}")

                # schedule on main thread
                self.root.after(0, _do_select)
                return jsonify({'ok': True})
            except Exception as e:
                return jsonify({'ok': False, 'error': str(e)})

        @app.route('/midi/status')
        def midi_status():
            try:
                return jsonify({'ok': True, 'connected': self.running, 'device': self.device_combo.get() if hasattr(self, 'device_combo') else None})
            except Exception as e:
                return jsonify({'ok': False, 'error': str(e)})

        # LED control endpoints
        @app.route('/api/led/status')
        def api_led_status():
            try:
                return jsonify({
                    'ok': True,
                    'enabled': self.led_controller.enabled,
                    'hardware_available': self.led_controller.strip is not None
                })
            except Exception as e:
                return jsonify({'ok': False, 'error': str(e)})

        @app.route('/api/led/enable', methods=['POST'])
        def api_led_enable():
            try:
                success = self.led_controller.enable()
                if success:
                    return jsonify({'ok': True, 'message': 'LED visualization enabled'})
                else:
                    return jsonify({'ok': False, 'error': 'Hardware not available'}), 400
            except Exception as e:
                return jsonify({'ok': False, 'error': str(e)}), 500

        @app.route('/api/led/disable', methods=['POST'])
        def api_led_disable():
            try:
                self.led_controller.disable()
                return jsonify({'ok': True, 'message': 'LED visualization disabled'})
            except Exception as e:
                return jsonify({'ok': False, 'error': str(e)}), 500

        @app.route('/api/led/test', methods=['POST'])
        def api_led_test():
            try:
                if not self.led_controller.strip:
                    return jsonify({'ok': False, 'error': 'Hardware not available'}), 400
                self.led_controller.test_pattern()
                return jsonify({'ok': True, 'message': 'Test pattern completed'})
            except Exception as e:
                return jsonify({'ok': False, 'error': str(e)}), 500

        def run_server():
            # bind only to localhost for security
            app.run(host='127.0.0.1', port=5001, threaded=True, use_reloader=False)

        t = threading.Thread(target=run_server, daemon=True)
        t.start()

    # All the GUI setup, MIDI handling, and other methods remain here
    # Just reference the statistics and heatmap windows through their handlers
    def setup_gui(self):
        """Set up the GUI layout"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="MIDI Piano Keyboard Tracker", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10))
        
        # Device selection frame
        device_frame = ttk.LabelFrame(main_frame, text="MIDI Device", padding="5")
        device_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        device_frame.columnconfigure(1, weight=1)
        
        ttk.Label(device_frame, text="Device:").grid(row=0, column=0, padx=(0, 5))
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(device_frame, textvariable=self.device_var, 
                                        state="readonly", width=50)
        self.device_combo.grid(row=0, column=1, padx=(0, 10), sticky=(tk.W, tk.E))
        
        self.refresh_btn = ttk.Button(device_frame, text="Refresh", command=self.refresh_devices)
        self.refresh_btn.grid(row=0, column=2, padx=(5, 0))
        
        self.connect_btn = ttk.Button(device_frame, text="Connect", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=3, padx=(5, 0))

        # Sleep prevention checkbox
        self.sleep_check = ttk.Checkbutton(device_frame, 
                                        text="Prevent sleep while playing", 
                                        variable=self.sleep_prevention_enabled,
                                        command=self.toggle_sleep_prevention)
        self.sleep_check.grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))
        
        sleep_help = ttk.Label(device_frame, 
                            text="Keeps laptop awake during practice sessions (auto-disables after 5 min of inactivity)",
                            font=("Arial", 8), foreground="gray")
        sleep_help.grid(row=1, column=2, columnspan=2, sticky="w", pady=(5, 0), padx=(10, 0))

        # Passthrough frame
        passthrough_frame = ttk.LabelFrame(main_frame, text="MIDI Passthrough", padding="5")
        passthrough_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        passthrough_frame.columnconfigure(1, weight=1)
        
        self.passthrough_var = tk.BooleanVar()
        self.passthrough_check = ttk.Checkbutton(passthrough_frame, text="Enable MIDI Passthrough", 
                                                variable=self.passthrough_var, command=self.toggle_passthrough)
        self.passthrough_check.grid(row=0, column=0, padx=(0, 10))
        
        self.virtual_port_label = ttk.Label(passthrough_frame, text="Select output port below", 
                                          foreground="gray")
        self.virtual_port_label.grid(row=0, column=1, sticky=(tk.W,))
        
        # Output device selection
        ttk.Label(passthrough_frame, text="Output to:").grid(row=1, column=0, sticky=(tk.W,), pady=(5, 0))
        self.output_var = tk.StringVar()
        self.output_combo = ttk.Combobox(passthrough_frame, textvariable=self.output_var, 
                                        state="readonly", width=40)
        self.output_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(5, 0))
        
        self.refresh_outputs_btn = ttk.Button(passthrough_frame, text="Refresh Outputs", 
                                            command=self.refresh_output_devices)
        self.refresh_outputs_btn.grid(row=1, column=2, padx=(5, 0), pady=(5, 0))
        
        # Help text
        help_frame = ttk.Frame(passthrough_frame)
        help_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0))
        
        help_text = "💡 On Windows: Install loopMIDI to create virtual ports, or use hardware MIDI ports"
        ttk.Label(help_frame, text=help_text, font=("Arial", 8), foreground="blue").pack(anchor="w")
        
        import platform
        if platform.system() == "Windows":
            link_text = "📥 Download loopMIDI: https://www.tobias-erichsen.de/software/loopmidi.html"
            ttk.Label(help_frame, text=link_text, font=("Arial", 8), foreground="purple").pack(anchor="w")
        
        # Status frame
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="5")
        status_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        status_frame.columnconfigure(0, weight=1)
        status_frame.columnconfigure(1, weight=1)
        status_frame.columnconfigure(2, weight=1)
        
        self.status_label = ttk.Label(status_frame, text="Disconnected", foreground="red")
        self.status_label.grid(row=0, column=0)
        
        self.stats_label = ttk.Label(status_frame, text="Notes: 0 | Energy: 0 J | Pedal: 0")
        self.stats_label.grid(row=0, column=1)
        
        self.throughput_label = ttk.Label(status_frame, text="Rate: 0 B/s")
        self.throughput_label.grid(row=0, column=2)
        
        # Main content frame
        content_frame = ttk.Frame(main_frame)
        content_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        content_frame.columnconfigure(0, weight=1)
        content_frame.columnconfigure(1, weight=1)
        content_frame.rowconfigure(0, weight=1)
        
        # MIDI Activity frame
        activity_frame = ttk.LabelFrame(content_frame, text="Recent MIDI Activity", padding="5")
        activity_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        activity_frame.columnconfigure(0, weight=1)
        activity_frame.rowconfigure(0, weight=1)
        
        self.activity_text = scrolledtext.ScrolledText(activity_frame, width=40, height=20,
                                                      font=("Courier", 9))
        self.activity_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Note counts frame
        notes_frame = ttk.LabelFrame(content_frame, text="Note Counts", padding="5")
        notes_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        notes_frame.columnconfigure(0, weight=1)
        notes_frame.rowconfigure(0, weight=1)

        # Treeview for note counts
        columns = ("Note", "Count", "Energy")
        self.notes_tree = ttk.Treeview(notes_frame, columns=columns, show="headings", height=15)
        self.notes_tree.heading("Note", text="Note")
        self.notes_tree.heading("Count", text="Count")
        self.notes_tree.heading("Energy", text="Energy")
        self.notes_tree.column("Note", width=60)
        self.notes_tree.column("Count", width=60)
        self.notes_tree.column("Energy", width=80)

        notes_scrollbar = ttk.Scrollbar(notes_frame, orient="vertical", command=self.notes_tree.yview)
        self.notes_tree.configure(yscrollcommand=notes_scrollbar.set)

        self.notes_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        notes_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Control buttons
        button_frame = ttk.Frame(notes_frame)
        button_frame.grid(row=1, column=0, pady=(5, 0), sticky="ew")
        
        ttk.Button(button_frame, text="Clear Session", command=self.clear_counts).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Statistics", command=self.show_statistics).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Chord Finder", command=self.show_chords).pack(side=tk.LEFT, padx=5)

        if MATPLOTLIB_AVAILABLE:
            ttk.Button(button_frame, text="Show Heatmap", command=self.show_heatmap).pack(side=tk.LEFT, padx=5)
        
        # Initialize device lists and try auto-connect
        self.refresh_devices()
        self.refresh_output_devices()
        self.auto_connect_on_startup()

    
    def show_chords(self):
        self.chord_window.show()

    def update_displays(self):
        """Update status displays periodically with energy information"""
        # Update session timer
        self.update_session_timer()
        
        if self.running:
            throughput = self.calculate_throughput()
            self.throughput_label.config(text=f"Rate: {throughput:.0f} B/s")
        else:
            self.throughput_label.config(text="Rate: 0 B/s")
        
        # Calculate current session time
        current_session_time = self.get_current_session_time()
        
        # Update status display with energy
        total_notes = sum(self.note_counts.values())
        total_energy = self.daily_stats['total_energy']
        energy_display = self.energy_calculator.format_energy(total_energy)
        pedal_presses = self.daily_stats['pedal_presses']
        total_session_bytes = self.bytes_received
        
        if total_session_bytes > 1024 * 1024:
            size_display = f"{total_session_bytes/(1024*1024):.2f}MB"
        elif total_session_bytes > 1024:
            size_display = f"{total_session_bytes/1024:.1f}KB"
        else:
            size_display = f"{total_session_bytes}B"
        
        # Show session time and energy in status
        session_minutes = current_session_time / 60
        bytes_text = (f"Session: {session_minutes:.1f}m | Notes: {total_notes} | "
                     f"Energy: {energy_display} | Pedal: {pedal_presses} | Data: {size_display}")
        self.stats_label.config(text=bytes_text)
        
        self.root.after(1000, self.update_displays)

    def process_db_queue(self):
        """Process database operations from the queue"""
        try:
            while True:
                try:
                    operation = self.db_queue.get_nowait()
                    
                    if operation['type'] == 'update_stats':
                        self.db_manager.update_database_stats(operation['data'])
                    
                    elif operation['type'] == 'pedal_event':
                        #handled in main stats update now 
                        pass
                    elif operation['type'] == 'note_distribution':
                        self.db_manager.update_note_distribution(operation['data'])
                    
                    self.db_queue.task_done()
                    
                except queue.Empty:
                    break
                    
        except Exception as e:
            print(f"Database queue processing error: {e}")
        
        # Auto-save aggregated data periodically
        current_time = time.time()
        if current_time - self.last_save_time >= self.save_interval:
            self.save_aggregated_data()
            self.last_save_time = current_time
        
        # Schedule next queue processing
        self.root.after(50, self.process_db_queue)

    def save_aggregated_data(self):
        """Save current session's aggregated data to database"""
        if not self.conn:
            return
            
        try:
            current_time = datetime.now()
            date_str = current_time.strftime('%Y-%m-%d')
            hour = current_time.hour
            
            # Get current session time to save
            current_session_time = self.get_current_session_time()
            
            # Calculate what's new since last save
            if not hasattr(self, 'last_saved_daily_stats'):
                self.last_saved_daily_stats = {
                    'total_notes': 0,
                    'total_duration_ms': 0,
                    'total_velocity': 0,
                    'total_energy': 0.0,
                    'pedal_presses': 0,
                    'note_bytes': 0,
                    'other_bytes': 0,
                    'session_time_seconds': 0
                }
            
            # Calculate delta (what's new since last save)
            delta_daily_stats = {
                'total_notes': self.daily_stats['total_notes'] - self.last_saved_daily_stats['total_notes'],
                'total_duration_ms': self.daily_stats['total_duration_ms'] - self.last_saved_daily_stats['total_duration_ms'],
                'total_velocity': self.daily_stats['total_velocity'] - self.last_saved_daily_stats['total_velocity'],
                'total_energy': self.daily_stats['total_energy'] - self.last_saved_daily_stats.get('total_energy', 0),
                'pedal_presses': self.daily_stats['pedal_presses'] - self.last_saved_daily_stats['pedal_presses'],
                'note_bytes': self.daily_stats['note_bytes'] - self.last_saved_daily_stats['note_bytes'],
                'other_bytes': self.daily_stats['other_bytes'] - self.last_saved_daily_stats['other_bytes'],
                'session_time_seconds': current_session_time - self.last_saved_daily_stats['session_time_seconds']
            }
            
            # Only save if there's new data
            if delta_daily_stats['total_notes'] > 0 or delta_daily_stats['session_time_seconds'] > 0:
                # Use retry logic for database operations
                max_retries = 5
                for attempt in range(max_retries):
                    try:
                        cursor = self.conn.cursor()

                        cursor.execute('''
                            INSERT OR IGNORE INTO daily_stats (date) VALUES (?)
                        ''', (date_str,))

                        cursor.execute('''
                            UPDATE daily_stats SET
                                total_notes = COALESCE(total_notes, 0) + ?,
                                total_duration_ms = COALESCE(total_duration_ms, 0) + ?,
                                total_velocity = COALESCE(total_velocity, 0) + ?,
                                total_energy = COALESCE(total_energy, 0) + ?,
                                pedal_presses = COALESCE(pedal_presses, 0) + ?,
                                note_bytes = COALESCE(note_bytes, 0) + ?,
                                other_bytes = COALESCE(other_bytes, 0) + ?,
                                total_bytes = COALESCE(total_bytes, 0) + ?,
                                session_time_seconds = COALESCE(session_time_seconds, 0) + ?,
                                avg_velocity = CASE
                                    WHEN COALESCE(total_notes, 0) > 0
                                    THEN CAST(COALESCE(total_velocity, 0) AS REAL) / COALESCE(total_notes, 0)
                                    ELSE 0
                                END,
                                updated_at = datetime('now', 'localtime')
                            WHERE date = ?
                        ''', (
                            delta_daily_stats['total_notes'],
                            delta_daily_stats['total_duration_ms'],
                            delta_daily_stats['total_velocity'],
                            delta_daily_stats['total_energy'],
                            delta_daily_stats['pedal_presses'],
                            delta_daily_stats['note_bytes'],
                            delta_daily_stats['other_bytes'],
                            delta_daily_stats['note_bytes'] + delta_daily_stats['other_bytes'],
                            delta_daily_stats['session_time_seconds'],
                            date_str
                        ))

                        self.conn.commit()
                        break  # Success, exit retry loop
                    except sqlite3.OperationalError as e:
                        if "database is locked" in str(e) and attempt < max_retries - 1:
                            time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                            continue
                        raise
                
                # Update what we've saved so far
                self.last_saved_daily_stats = self.daily_stats.copy()
                self.last_saved_daily_stats['session_time_seconds'] = current_session_time
            
            # Queue hourly stats update and clear after queuing
            for hour_key, stats in list(self.hourly_stats.items()):
                if stats['total_notes'] > 0:
                    # Calculate session time for this hour
                    if 'session_start' in stats:
                        # Calculate how long we've been active in this hour
                        hour_session_time = time.time() - stats['session_start']
                        stats['session_time_seconds'] = stats.get('session_time_seconds', 0) + hour_session_time
                        # Reset the start time for next save
                        stats['session_start'] = time.time()

                    operation = {
                        'type': 'update_stats', 
                        'data': (date_str, hour_key, stats.copy())
                    }
                    self.db_queue.put(operation)

            # Clear hourly stats after saving to prevent duplicates
            self.hourly_stats.clear()
                
        except Exception as e:
            print(f"Error saving aggregated data: {e}")

    

    def process_midi_message(self, message, time_stamp):
        """Process incoming MIDI message with energy calculation"""
        try:
            if not message:
                return
                
            if self.sleep_prevention_enabled.get():
                self.sleep_preventer.register_activity()
            
            # Track session timing
            current_time = time.time()
            self.last_activity_time = current_time
            
            if not self.session_is_active:
                # Start/resume session timer
                self.session_timer_start = current_time
                self.session_is_active = True
                self.add_debug_message("⏱️ Practice session started")

            # Extract MIDI data
            if isinstance(message, tuple) and len(message) >= 2:
                midi_data = message[0]
            else:
                midi_data = message
            
            if isinstance(midi_data, tuple):
                midi_data = list(midi_data)
            
            if not midi_data:
                return
            
            # Count bytes and update throughput
            byte_count = len(midi_data)
            self.bytes_received += byte_count
            self.bytes_in_last_second += byte_count
            
            if self.throughput_history:
                self.throughput_history[-1] += byte_count
            else:
                self.throughput_history.append(byte_count)
            
            # Forward MIDI data if passthrough enabled
            if self.passthrough_enabled and self.midi_output:
                try:
                    self.midi_output.send_message(midi_data)
                except Exception as e:
                    self.add_debug_message(f"💥 Passthrough error: {e}")
            
            # Process MIDI message and update aggregated stats
            current_hour = datetime.now().hour

            # track session time for the hour
            if current_hour not in self.hourly_stats or 'session_start' not in self.hourly_stats[current_hour]:
                self.hourly_stats[current_hour]['session_start'] = time.time()

            is_note_event = False
            
            if len(midi_data) >= 3:
                status = midi_data[0]
                note = midi_data[1]
                velocity = midi_data[2]
                
                hex_msg = ' '.join([f'{b:02X}' for b in midi_data])
                
                # Note on: 0x90-0x9F with velocity > 0
                if 0x90 <= status <= 0x9F and velocity > 0:
                    is_note_event = True
                    self.note_counts[note] += 1
                    note_name = self.get_note_name(note)

                    #chord track check pedal
                    if self.pedal_pressed:
                        self.sustained_notes.add(note)

                    
                    # Calculate energy for this note press
                    note_energy = self.energy_calculator.calculate_note_energy(velocity)
                    self.per_note_energy[note] += note_energy
                    
                    # Track bytes for this specific note (3 bytes for note on)
                    self.per_note_bytes[note] += 3
                    
                    # Update aggregated statistics
                    self.daily_stats['total_notes'] += 1
                    self.daily_stats['total_velocity'] += velocity  # Keep for compatibility
                    self.daily_stats['total_energy'] += note_energy  # Add energy tracking
                    self.hourly_stats[current_hour]['total_notes'] += 1
                    self.hourly_stats[current_hour]['total_velocity'] += velocity
                    self.hourly_stats[current_hour]['total_energy'] += note_energy  # Add energy tracking
                    
                    # Track note timing for duration calculation
                    note_time = time.time()
                    self.active_notes[note] = {
                        'start_time': note_time,
                        'velocity': velocity,
                        'energy': note_energy  # Store energy for this note
                    }

                    energy_str = self.energy_calculator.format_energy(note_energy)
                    self.add_debug_message(f"🎵 NOTE ON: {note_name} (#{note}) vel={velocity}") #energy={energy_str} removed cos annoying

                    # LED visualization
                    self.led_controller.note_on(note, velocity)

                    # immediate push to web UI so debug appears live
                    try:
                        self.post_event({
                            'type': 'note_on', 'note': note, 'velocity': velocity,
                            'active_notes': list(self.active_notes.keys()),
                            'debug_messages': list(self.debug_messages)[-20:]
                        })
                    except Exception:
                        pass
                    
                    #update db
                    date_str = datetime.now().strftime('%Y-%m-%d')
                    operation = {
                        'type': 'note_distribution',
                        'data': (date_str, note, note_name, 1, velocity, note_energy, 3, 0)
                    }
                    self.db_queue.put(operation)


                    # Update displays
                    self.root.after(0, self.update_note_counts)
                    if self.heatmap_window.heatmap_window and self.heatmap_window.heatmap_window.winfo_exists():
                        self.root.after(0, self.heatmap_window.update_heatmap)
                    # Post lightweight state to web UI (non-blocking/optional)
                    try:
                        self.post_event({
                            'type': 'note_on', 'note': note, 'velocity': velocity,
                            'active_notes': list(self.active_notes.keys()),
                            'sustained_notes': list(self.sustained_notes),
                            'pedal_pressed': self.pedal_pressed,
                            'throughput': self.bytes_in_last_second,
                        })
                    except Exception:
                        pass
                    
                    
                elif 0x80 <= status <= 0x8F or (0x90 <= status <= 0x9F and velocity == 0):
                    # Note off
                    is_note_event = True
                    note_name = self.get_note_name(note)
                    
                    # Track bytes for this specific note (3 bytes for note off)
                    self.per_note_bytes[note] += 3
                    
                    #chord track check pedal remove notes from chord if pedal not pressed
                    if self.pedal_pressed:
                        self.sustained_notes.add(note)  # keep sounding
                    else:
                        if note in self.active_notes:
                            del self.active_notes[note]
                        if note in self.sustained_notes:
                            self.sustained_notes.discard(note)

                    # Calculate duration if note was being pressed
                    if note in self.active_notes:
                        duration_ms = (time.time() - self.active_notes[note]['start_time']) * 1000
                        
                        # Track duration for this specific note
                        self.per_note_durations[note] += duration_ms
                        
                        # Update duration statistics
                        self.daily_stats['total_duration_ms'] += duration_ms
                        self.hourly_stats[current_hour]['total_duration_ms'] += duration_ms
                        
                        #add to db
                        date_str = datetime.now().strftime('%Y-%m-%d')
                        operation = {
                            'type': 'note_distribution',
                            'data': (date_str, note, note_name, 0, 0, 0, 3, duration_ms)
                        }
                        self.db_queue.put(operation)

                        del self.active_notes[note]
                        self.add_debug_message(f"🎵 NOTE OFF: {note_name} duration={duration_ms:.1f}ms")

                    # LED visualization
                    self.led_controller.note_off(note)
                    # immediate push to web UI
                    try:
                        self.post_event({
                            'type': 'note_off', 'note': note,
                            'active_notes': list(self.active_notes.keys()),
                            'debug_messages': list(self.debug_messages)[-20:]
                        })
                    except Exception:
                        pass
                    else:
                        self.add_debug_message(f"🎵 NOTE OFF: {note_name}")
                    # Notify web UI of note off and current state
                    try:
                        self.post_event({
                            'type': 'note_off', 'note': note,
                            'active_notes': list(self.active_notes.keys()),
                            'sustained_notes': list(self.sustained_notes),
                            'pedal_pressed': self.pedal_pressed,
                            'throughput': self.bytes_in_last_second,
                        })
                    except Exception:
                        pass
                        
                elif (status & 0xF0) == 0xB0:  # Control Change
                    cc_number = note
                    cc_value = velocity
                    channel = status & 0x0F
                    
                    # Track sustain pedal (CC 64)
                    if cc_number == 64:
                        if cc_value >= 64 and not self.pedal_pressed:
                            # Pedal pressed
                            self.pedal_pressed = True
                            self.daily_stats['pedal_presses'] += 1
                            self.hourly_stats[current_hour]['pedal_presses'] += 1

                            # Save pedal press to note_distribution with midi_note = -1
                            date_str = datetime.now().strftime('%Y-%m-%d')
                            operation = {
                                'type': 'note_distribution',
                                'data': (date_str, -1, "PEDAL", 1, 0, 0, 3, 0)
                            }
                            self.db_queue.put(operation)

                            self.add_debug_message(f"🦶 PEDAL ON")
                            # Notify web UI about pedal on
                            try:
                                self.post_event({'type': 'pedal_on', 'pedal_pressed': True,
                                                 'active_notes': list(self.active_notes.keys()),
                                                 'sustained_notes': list(self.sustained_notes),
                                                 'throughput': self.bytes_in_last_second})
                            except Exception:
                                pass
                        elif cc_value < 64 and self.pedal_pressed:
                            # Pedal released
                            self.pedal_pressed = False

                            # If pedal is not pressed, clear sustained notes that are no longer active  
                            if self.sustained_notes:
                                for n in list(self.sustained_notes):
                                    if n not in self.active_notes:
                                        self.sustained_notes.discard(n)
                                        
                            self.add_debug_message(f"🦶 PEDAL OFF")
                            # Notify web UI about pedal off
                            try:
                                self.post_event({'type': 'pedal_off', 'pedal_pressed': False,
                                                 'active_notes': list(self.active_notes.keys()),
                                                 'sustained_notes': list(self.sustained_notes),
                                                 'throughput': self.bytes_in_last_second})
                            except Exception:
                                pass
                    else:
                        self.add_debug_message(f"📊 CC{cc_number}={cc_value} ch={channel}")


                        
                                        
                else:
                    # Other MIDI messages
                    channel = status & 0x0F
                    msg_type = (status & 0xF0) >> 4
                    
                    if msg_type == 12:  # Program Change
                        self.add_debug_message(f"📊 PROG_CHG={note} ch={channel}")
                    elif msg_type == 14:  # Pitch Bend
                        bend_value = (velocity << 7) | note
                        
                        # Track pitch bend in note distribution
                        date_str = datetime.now().strftime('%Y-%m-%d')
                        operation = {
                            'type': 'note_distribution',
                            'data': (date_str, -2, "PITCH_BEND", 1, 0, 0, byte_count, 0)  # -2 = pitch bend
                        }
                        self.db_queue.put(operation)
                        
                        self.add_debug_message(f"📊 PITCH_BEND={bend_value} ch={channel}")
                    else:
                        self.add_debug_message(f"📊 MIDI: {hex_msg}")
            
            elif len(midi_data) == 2:
                hex_msg = f"{midi_data[0]:02X} {midi_data[1]:02X}"
                self.add_debug_message(f"📝 2-BYTE: {hex_msg}")
                
                status = midi_data[0]
                if 0x80 <= status <= 0x9F:
                    is_note_event = True
            
            elif len(midi_data) == 1:
                self.add_debug_message(f"📝 1-BYTE: {midi_data[0]:02X}")
            
            # Update byte category counters
            if is_note_event:
                self.daily_stats['note_bytes'] += byte_count
                self.hourly_stats[current_hour]['note_bytes'] += byte_count
                self.note_bytes += byte_count  # Session tracking
            else:
                self.daily_stats['other_bytes'] += byte_count
                self.hourly_stats[current_hour]['other_bytes'] += byte_count
                self.other_bytes += byte_count  # Session tracking
                # send compact state update to web UI
                try:
                    self.post_event({
                        'active_notes': list(self.active_notes.keys()),
                        'sustained_notes': list(self.sustained_notes),
                        'pedal_pressed': self.pedal_pressed,
                        'throughput': self.bytes_in_last_second,
                        'debug_messages': list(self.debug_messages)[-50:]
                    })
                except Exception:
                    pass
        except Exception as e:
            self.add_debug_message(f"💥 ERROR: {str(e)}")


    def get_note_name(self, midi_note):
        """Convert MIDI note number to note name with octave"""
        octave = (midi_note // 12) - 1
        note = self.note_names[midi_note % 12]
        return f"{note}{octave}"
    
    def add_debug_message(self, message):
        """Add a debug message to the activity display (thread-safe)"""
        try:
            def update_gui():
                timestamp = time.strftime("%H:%M:%S")
                full_message = f"[{timestamp}] {message}"
                self.debug_messages.append(full_message)
                self.total_messages += 1
                self.update_activity_display()
            
            self.root.after_idle(update_gui)
        except Exception as e:
            print(f"Debug message error: {e}")
    
    def add_debug_message_direct(self, message):
        """Add a debug message directly (for main thread only)"""
        timestamp = time.strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}"
        self.debug_messages.append(full_message)
        self.total_messages += 1
        self.update_activity_display()
    
    def update_activity_display(self):
        """Update the activity text widget"""
        self.activity_text.delete(1.0, tk.END)
        
        recent_messages = list(self.debug_messages)[-50:]
        for msg in recent_messages:
            self.activity_text.insert(tk.END, msg + "\n")
        
        self.activity_text.see(tk.END)

    def update_note_counts(self):
        """Update the note counts treeview with energy display"""
        # Clear existing items
        for item in self.notes_tree.get_children():
            self.notes_tree.delete(item)
        
        # Add notes sorted by count (descending)
        if self.note_counts:
            sorted_notes = sorted(self.note_counts.items(), key=lambda x: x[1], reverse=True)
            
            for midi_note, count in sorted_notes:
                note_name = self.get_note_name(midi_note)
                note_energy = self.per_note_energy.get(midi_note, 0)
                energy_display = self.energy_calculator.format_energy(note_energy)
                self.notes_tree.insert("", "end", values=(note_name, count, energy_display))
    
    def refresh_devices(self):
        """Refresh the list of available MIDI devices"""
        if not RTMIDI_AVAILABLE:
            messagebox.showerror("Error", "python-rtmidi not found!\nInstall with: pip install python-rtmidi")
            return
        
        try:
            if hasattr(self, 'midi_input') and self.midi_input:
                try:
                    self.midi_input.close_port()
                except:
                    pass
                self.midi_input = None
            
            midiin = rtmidi.MidiIn()
            ports = midiin.get_ports()
            midiin.close_port()
            del midiin
            
            self.device_combo['values'] = ports
            if ports:
                self.device_combo.current(0)
                self.add_debug_message_direct(f"Found {len(ports)} MIDI device(s)")
                for i, port in enumerate(ports):
                    self.add_debug_message_direct(f"  Device {i}: {port}")
            else:
                messagebox.showwarning("No Devices", "No MIDI input devices found.\n\nMake sure your keyboard is:\n• Connected via USB\n• Powered on\n• Recognized by Windows")
                self.add_debug_message_direct("No MIDI devices found")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error listing MIDI devices: {e}")
            self.add_debug_message_direct(f"Error refreshing devices: {e}")
    
    def toggle_sleep_prevention(self):
        """Toggle sleep prevention on/off"""
        if self.sleep_prevention_enabled.get():
            if self.sleep_preventer.start_monitoring():
                self.add_debug_message("💤 Sleep prevention enabled - laptop will stay awake while playing")
            else:
                self.sleep_prevention_enabled.set(False)
                self.add_debug_message("⚠️ Sleep prevention not available on this system")
        else:
            self.sleep_preventer.stop_monitoring()
            self.add_debug_message("💤 Sleep prevention disabled")

    def auto_connect_on_startup(self):
        """Automatically connect to specified device and enable passthrough"""
        if not self.auto_connect_enabled:
            self.add_debug_message_direct("Auto-connection disabled")
            return
            
        try:
            self.add_debug_message_direct(f"🔍 Auto-connecting to device with '{self.auto_input_keyword}' in name...")
            
            target_index = None
            input_devices = self.device_combo['values']
            
            for i, device_name in enumerate(input_devices):
                if self.auto_input_keyword.lower() in device_name.lower():
                    target_index = i
                    self.add_debug_message_direct(f"✓ Found input device: {device_name}")
                    break
            
            output_index = None
            output_devices = self.output_combo['values']
            
            for i, device_name in enumerate(output_devices):
                if self.auto_output_keyword.lower() in device_name.lower():
                    output_index = i
                    self.add_debug_message_direct(f"✓ Found output device: {device_name}")
                    break
            
            if target_index is not None:
                self.device_combo.current(target_index)
                self.root.after(100, self.auto_connect_sequence, output_index)
            else:
                self.add_debug_message_direct(f"⚠️ No device with '{self.auto_input_keyword}' found - manual connection required")
                if input_devices:
                    self.add_debug_message_direct("Available input devices:")
                    for i, device in enumerate(input_devices):
                        self.add_debug_message_direct(f"  {i}: {device}")
        
        except Exception as e:
            self.add_debug_message_direct(f"Auto-connect error: {e}")
    
    def auto_connect_sequence(self, output_index):
        """Complete the auto-connection sequence"""
        try:
            self.connect_device()
            
            if output_index is not None and self.running:
                self.root.after(200, self.setup_auto_passthrough, output_index)
            else:
                self.add_debug_message_direct(f"⚠️ No device with '{self.auto_output_keyword}' found - passthrough not enabled")
                if self.output_combo['values']:
                    self.add_debug_message_direct("Available output devices:")
                    for i, device in enumerate(self.output_combo['values']):
                        self.add_debug_message_direct(f"  {i}: {device}")
                        
        except Exception as e:
            self.add_debug_message_direct(f"Auto-connection sequence error: {e}")
    
    def setup_auto_passthrough(self, output_index):
        """Setup automatic passthrough to specified output"""
        try:
            self.output_combo.current(output_index)
            self.passthrough_var.set(True)
            self.enable_passthrough()
            
            input_name = self.device_combo.get()
            output_name = self.output_combo.get()
            
            self.add_debug_message_direct(f"🎵 Auto-setup complete! {input_name} → Tracker → {output_name}")
            self.add_debug_message_direct("📊 Ready to track your playing...")
            
        except Exception as e:
            self.add_debug_message_direct(f"Auto-passthrough setup error: {e}")
    
    def toggle_connection(self):
        """Connect or disconnect from MIDI device"""
        if self.running:
            self.disconnect_device()
        else:
            self.connect_device()
    
    def connect_device(self):
        """Connect to the selected MIDI device"""
        if not self.device_combo.get():
            messagebox.showwarning("No Device", "Please select a MIDI device first.")
            return
        
        try:
            device_index = self.device_combo.current()
            self.midi_input = rtmidi.MidiIn()
            
            if self.sleep_prevention_enabled.get():
                self.sleep_preventer.start_monitoring()

            self.midi_input.open_port(device_index)
            self.midi_input.set_callback(self.process_midi_message)
            
            self.running = True
            self.start_time = time.time()
            self.throughput_history.clear()
            self.throughput_history.append(0)
            
            # Update GUI
            self.status_label.config(text="Connected", foreground="green")
            self.connect_btn.config(text="Disconnect")
            self.device_combo.config(state="disabled")
            self.refresh_btn.config(state="disabled")
            
            self.add_debug_message_direct(f"Connected to: {self.device_combo.get()}")
            self.add_debug_message_direct("Ready to receive MIDI data...")
            
        except Exception as e:
            error_msg = str(e)
            
            if "error creating windows MM MIDI input port" in error_msg:
                help_msg = (
                    "MIDI Device Connection Failed!\n\n"
                    "This usually means:\n"
                    "• Device is already in use by another program\n"
                    "• Device drivers need updating\n"
                    "• Device was disconnected\n\n"
                    "Try:\n"
                    "1. Close other MIDI software (DAWs, etc.)\n"
                    "2. Disconnect and reconnect your keyboard\n"
                    "3. Click 'Refresh' and try again\n"
                    "4. Restart this program\n"
                    "5. Try a different USB port\n\n"
                    f"Technical error: {error_msg}"
                )
            elif "invalid device" in error_msg.lower():
                help_msg = (
                    "MIDI Device Not Found!\n\n"
                    "The selected device is no longer available.\n\n"
                    "Try:\n"
                    "1. Click 'Refresh' to update device list\n"
                    "2. Check if your keyboard is still connected\n"
                    "3. Select a different device\n\n"
                    f"Technical error: {error_msg}"
                )
            else:
                help_msg = f"Failed to connect to MIDI device:\n\n{error_msg}"
            
            messagebox.showerror("MIDI Connection Error", help_msg)
            
            if hasattr(self, 'midi_input') and self.midi_input:
                try:
                    self.midi_input.close_port()
                except:
                    pass
                self.midi_input = None
    
    def disconnect_device(self):
        """Disconnect from MIDI device"""
        self.running = False
        
        # Save any pending data before disconnecting
        self.save_aggregated_data()
        
        self.sleep_preventer.stop_monitoring()

        if self.midi_input:
            self.midi_input.close_port()
            self.midi_input = None
        
        if self.passthrough_enabled:
            self.passthrough_var.set(False)
            self.disable_passthrough()
        
        # Update GUI
        self.status_label.config(text="Disconnected", foreground="red")
        self.connect_btn.config(text="Connect")
        self.device_combo.config(state="readonly")
        self.refresh_btn.config(state="normal")
        
        self.add_debug_message_direct("Disconnected from MIDI device")

    def clear_counts(self):
        """Clear current session data"""
        result = messagebox.askyesno("Clear Session Data", 
                                   "Clear current session data?\n\n" +
                                   "This will clear the current display but won't delete\n" +
                                   "historical data from the database.")
        if result:
            # Save current data before clearing
            self.save_aggregated_data()
            
            # Reset session counters
            self.note_counts.clear()
            self.active_notes.clear()
            self.per_note_bytes.clear()      # Clear per-note byte tracking
            self.per_note_durations.clear()  # Clear per-note duration tracking
            self.per_note_energy.clear()     # Clear per-note energy tracking
            self.bytes_received = 0
            self.total_messages = 0
            self.note_bytes = 0
            self.other_bytes = 0

            # Reset aggregated stats
            self.daily_stats = {
                'total_notes': 0,
                'total_duration_ms': 0,
                'total_velocity': 0,
                'total_energy': 0.0,
                'pedal_presses': 0,
                'note_bytes': 0,
                'other_bytes': 0
            }
            

            # IMPORTANT: Also reset the last saved stats to prevent negative deltas
            self.last_saved_daily_stats = {
                'total_notes': 0,
                'total_duration_ms': 0,
                'total_velocity': 0,
                'total_energy': 0.0,
                'pedal_presses': 0,
                'note_bytes': 0,
                'other_bytes': 0,
                'session_time_seconds': 0
            }

            self.hourly_stats.clear()
            
            # Reset throughput tracking
            self.bytes_in_last_second = 0
            self.last_second_reset = time.time()
            self.throughput_history.clear()
            self.throughput_history.append(0)
            
            self.update_note_counts()
            self.add_debug_message_direct("📊 Current session data cleared")
            
            if self.heatmap_window.heatmap_window and self.heatmap_window.heatmap_window.winfo_exists():
                self.heatmap_window.update_heatmap()
    

    def toggle_passthrough(self):
        """Toggle MIDI passthrough on/off"""
        if self.passthrough_var.get():
            self.enable_passthrough()
        else:
            self.disable_passthrough()
    
    def enable_passthrough(self):
        """Enable MIDI passthrough to selected output port"""
        if not self.output_combo.get():
            messagebox.showwarning("No Output", "Please select a MIDI output device first.")
            self.passthrough_var.set(False)
            return
        
        try:
            output_index = self.output_combo.current()
            self.midi_output = rtmidi.MidiOut()
            self.midi_output.open_port(output_index)
            
            self.passthrough_enabled = True
            self.virtual_port_label.config(text=f"Routing to: {self.output_combo.get()}", foreground="green")
            self.add_debug_message(f"🔄 MIDI Passthrough enabled to: {self.output_combo.get()}")
            
        except Exception as e:
            self.passthrough_var.set(False)
            messagebox.showerror("Passthrough Error", f"Failed to open MIDI output port:\n{e}")
            self.add_debug_message(f"💥 Passthrough error: {e}")
    
    def disable_passthrough(self):
        """Disable MIDI passthrough"""
        self.passthrough_enabled = False
        
        if self.midi_output:
            self.midi_output.close_port()
            self.midi_output = None
        
        self.virtual_port_label.config(text="Select output port below", foreground="gray")
        self.add_debug_message("🔄 MIDI Passthrough disabled")
    
    def refresh_output_devices(self):
        """Refresh the list of available MIDI output devices"""
        if not RTMIDI_AVAILABLE:
            return
        
        try:
            midiout = rtmidi.MidiOut()
            ports = midiout.get_ports()
            midiout.close_port()
            del midiout
            
            port_list = list(ports) if ports else ["No MIDI output devices found"]
            
            self.output_combo['values'] = port_list
            if port_list and port_list[0] != "No MIDI output devices found":
                self.output_combo.current(0)
                
        except Exception as e:
            self.add_debug_message(f"Error listing output devices: {e}")



    def calculate_throughput(self):
        """Calculate current data throughput (bytes per second)"""
        try:
            current_time = time.time()
            
            if current_time - self.last_second_reset >= 1.0:
                current_rate = self.bytes_in_last_second
                self.bytes_in_last_second = 0
                self.last_second_reset = current_time
                return current_rate
            else:
                return self.bytes_in_last_second
                
        except Exception as e:
            print(f"Throughput calculation error: {e}")
            return 0
        
    def update_session_timer(self):
        """Update session timer and check for pauses"""
        if not self.last_activity_time:
            return
            
        current_time = time.time()
        
        # Check if session should be paused due to inactivity
        if self.session_is_active and (current_time - self.last_activity_time > self.session_pause_threshold):
            # Add active time to total before pausing (up to when activity stopped)
            if self.session_timer_start:
                active_time = self.last_activity_time - self.session_timer_start
                self.session_timer_total += active_time
                
            self.session_is_active = False
            self.session_timer_start = None
            self.add_debug_message("⏸️ Practice session paused (inactivity)")


    def get_current_session_time(self):
        """Get current total session time in seconds"""
        total_time = self.session_timer_total
        
        # Add current active period if session is running
        if self.session_is_active and self.session_timer_start:
            total_time += time.time() - self.session_timer_start
        
        return total_time


    def on_closing(self):
        """Handle window closing"""
        if self.running:
            self.disconnect_device()

        self.sleep_preventer.stop_monitoring()
        
        if self.passthrough_enabled:
            self.disable_passthrough()
        
        # Save final data
        self.save_aggregated_data()
        
        # Close windows
        if self.heatmap_window.heatmap_window and self.heatmap_window.heatmap_window.winfo_exists():
            self.heatmap_window.heatmap_window.destroy()
        
        if self.statistics_window.stats_window and self.statistics_window.stats_window.winfo_exists():
            self.statistics_window.stats_window.destroy()
        
        # Close database
        if hasattr(self, 'conn') and self.conn:
            try:
                # Update session end time
                cursor = self.conn.cursor()
                session_duration = (datetime.now() - self.session_start).total_seconds() / 60
                cursor.execute('''
                    UPDATE sessions 
                    SET end_time = datetime('now', 'localtime'), duration_minutes = ?
                    WHERE session_id = ?
                ''', (session_duration, self.session_id))
                self.conn.commit()
                self.conn.close()
            except Exception as e:
                print(f"Error closing database: {e}")
            
        self.root.destroy()

    
    def show_statistics(self):
        """Delegate to statistics window handler"""
        self.statistics_window.show_statistics()
    
    def show_heatmap(self):
        """Delegate to heatmap window handler"""
        self.heatmap_window.show_heatmap()
    
    def reset_session_counters(self):
        """Reset all session counters - called by statistics window"""
        self.note_counts.clear()
        self.active_notes.clear()
        self.bytes_received = 0
        self.total_messages = 0
        self.note_bytes = 0
        self.other_bytes = 0
        self.per_note_energy.clear()
        
        self.daily_stats = {
            'total_notes': 0,
            'total_duration_ms': 0,
            'total_velocity': 0,
            'total_energy': 0.0,
            'pedal_presses': 0,
            'note_bytes': 0,
            'other_bytes': 0
        }
        self.hourly_stats.clear()
        
        # Reinitialize
        self.session_start = datetime.now()
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.db_manager.session_id = self.session_id
        self.db_manager.initialize_todays_data()
        
        # Update displays
        self.update_note_counts()
        if hasattr(self.statistics_window.stats_window, 'stats_window') and self.statistics_window.stats_window:
            if self.statistics_window.stats_window.winfo_exists():
                self.statistics_window.update_statistics()
        if hasattr(self.heatmap_window, 'heatmap_window') and self.heatmap_window.heatmap_window:
            if self.heatmap_window.heatmap_window.winfo_exists():
                self.heatmap_window.update_heatmap()
    
    # Rest of the main application code...
    # setup_gui, process_midi_message, etc. all remain in this file

def main():
    if not RTMIDI_AVAILABLE:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Missing Dependency", 
                           "python-rtmidi is required!\n\nInstall with:\npip install python-rtmidi")
        root.destroy()
        return
    
    if not MATPLOTLIB_AVAILABLE:
        print("Note: matplotlib not found. Heatmap feature will be disabled.")
        print("To enable heatmap: pip install matplotlib")
    
    print("MIDI Tracker with Energy Calculation - Starting...")
    print("Features: Physical energy measurement (Joules), Daily/Hourly stats, Pedal tracking, Heatmap")
    print("Using Numa X Piano specifications: 58.5g actuation force, 10mm key travel")
    
    root = tk.Tk()
    app = MidiTrackerGUI(root)
    
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    root.mainloop()

if __name__ == "__main__":
    main()



    #DINGUS BUGERGER