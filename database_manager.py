import sqlite3
import queue
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path="midi_tracker.db"):
        self.db_path = db_path
        self.conn = None
        self.db_queue = queue.Queue()
        self.session_id = None
        self.session_start = datetime.now()
        self.setup_database()
    
    def setup_database(self):
        """Initialize SQLite database with aggregated data structure"""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = self.conn.cursor()
            
            # Daily statistics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE UNIQUE,
                    total_notes INTEGER DEFAULT 0,
                    total_duration_ms REAL DEFAULT 0,
                    session_time_seconds REAL DEFAULT 0,
                    avg_velocity REAL DEFAULT 0,
                    total_velocity INTEGER DEFAULT 0,
                    total_energy REAL DEFAULT 0,
                    pedal_presses INTEGER DEFAULT 0,
                    note_bytes INTEGER DEFAULT 0,
                    other_bytes INTEGER DEFAULT 0,
                    total_bytes INTEGER DEFAULT 0,
                    sessions INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT (datetime('now', 'localtime')),
                    updated_at DATETIME DEFAULT (datetime('now', 'localtime'))
                )
            ''')
            
            # Add total_energy column if it doesn't exist (for existing databases)
            cursor.execute("PRAGMA table_info(daily_stats)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'total_energy' not in columns:
                cursor.execute("ALTER TABLE daily_stats ADD COLUMN total_energy REAL DEFAULT 0")
            
            # Hourly statistics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS hourly_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE,
                    hour INTEGER,
                    total_notes INTEGER DEFAULT 0,
                    total_duration_ms REAL DEFAULT 0,
                    session_time_seconds REAL DEFAULT 0,
                    avg_velocity REAL DEFAULT 0,
                    total_velocity INTEGER DEFAULT 0,
                    total_energy REAL DEFAULT 0,
                    pedal_presses INTEGER DEFAULT 0,
                    note_bytes INTEGER DEFAULT 0,
                    other_bytes INTEGER DEFAULT 0,
                    total_bytes INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT (datetime('now', 'localtime')),
                    updated_at DATETIME DEFAULT (datetime('now', 'localtime')),
                    UNIQUE(date, hour)
                )
            ''')
            
            # Add total_energy column to hourly_stats if it doesn't exist
            cursor.execute("PRAGMA table_info(hourly_stats)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'total_energy' not in columns:
                cursor.execute("ALTER TABLE hourly_stats ADD COLUMN total_energy REAL DEFAULT 0")
            
            # Sessions table (simplified)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE,
                    start_time DATETIME,
                    end_time DATETIME,
                    date DATE,
                    duration_minutes INTEGER DEFAULT 0
                )
            ''')
            
            # Note distribution table (for heatmap data)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS note_distribution (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE,
                    midi_note INTEGER,
                    note_name TEXT,
                    count INTEGER DEFAULT 0,
                    total_velocity INTEGER DEFAULT 0,
                    total_energy REAL DEFAULT 0,
                    note_bytes INTEGER DEFAULT 0,
                    total_duration_ms REAL DEFAULT 0,
                    created_at DATETIME DEFAULT (datetime('now', 'localtime')),
                    updated_at DATETIME DEFAULT (datetime('now', 'localtime')),
                    UNIQUE(date, midi_note)
                )
            ''')
            
            # Add total_energy column to note_distribution if it doesn't exist
            cursor.execute("PRAGMA table_info(note_distribution)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'total_energy' not in columns:
                cursor.execute("ALTER TABLE note_distribution ADD COLUMN total_energy REAL DEFAULT 0")
            
            self.conn.commit()
            
            # Create session ID and initialize today's data
            self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.initialize_todays_data()
            
        except Exception as e:
            print(f"Database setup error: {e}")
            self.conn = None
    
    def initialize_todays_data(self):
        """Initialize or load today's statistics"""
        if not self.conn:
            return
            
        try:
            cursor = self.conn.cursor()
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Insert today's record if it doesn't exist
            cursor.execute('''
                INSERT OR IGNORE INTO daily_stats (date) VALUES (?)
            ''', (today,))
            
            # Create session record
            cursor.execute('''
                INSERT INTO sessions (session_id, start_time, date) VALUES (?, ?, ?)
            ''', (self.session_id, self.session_start, today))
            
            self.conn.commit()
            
        except Exception as e:
            print(f"Error initializing today's data: {e}")
    
    def update_database_stats(self, data):
        """Update database with aggregated statistics"""
        if not self.conn:
            return
            
        try:
            cursor = self.conn.cursor()
            date, hour, stats = data
            
            if hour is not None:  # Hourly stats
                # Use INSERT OR IGNORE then UPDATE to properly aggregate
                cursor.execute('''
                    INSERT OR IGNORE INTO hourly_stats 
                    (date, hour, total_notes, total_duration_ms, total_velocity, total_energy,
                    pedal_presses, note_bytes, other_bytes, total_bytes, 
                    avg_velocity, updated_at)
                    VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, datetime('now', 'localtime'))
                ''', (date, hour))
                
                # Now update with accumulated values
                cursor.execute('''
                    UPDATE hourly_stats SET
                        total_notes = total_notes + ?,
                        total_duration_ms = total_duration_ms + ?,
                        total_velocity = total_velocity + ?,
                        total_energy = total_energy + ?,
                        pedal_presses = pedal_presses + ?,
                        note_bytes = note_bytes + ?,
                        other_bytes = other_bytes + ?,
                        total_bytes = total_bytes + ?,
                        session_time_seconds = session_time_seconds + ?,
                        avg_velocity = CASE 
                            WHEN total_notes > 0 
                            THEN CAST(total_velocity AS REAL) / total_notes
                            ELSE 0 
                        END,
                        updated_at = datetime('now', 'localtime')
                    WHERE date = ? AND hour = ?
                ''', (stats['total_notes'], stats['total_duration_ms'],
                    stats['total_velocity'], stats.get('total_energy', 0),
                    stats['pedal_presses'], stats['note_bytes'], stats['other_bytes'],
                    stats['note_bytes'] + stats['other_bytes'],
                    stats.get('session_time_seconds', 0),
                    date, hour))
            
            self.conn.commit()
            
        except Exception as e:
            print(f"Error updating database stats: {e}")
    
    def update_note_distribution(self, data):
        """Update note distribution for heatmap"""
        if not self.conn:
            return
            
        try:
            cursor = self.conn.cursor()
            date, midi_note, note_name, count, velocity, energy, bytes_count, duration = data
            
            cursor.execute('''
                INSERT OR REPLACE INTO note_distribution
                (date, midi_note, note_name, count, total_velocity, total_energy, note_bytes, total_duration_ms, updated_at)
                VALUES (?, ?, ?, 
                        COALESCE((SELECT count FROM note_distribution WHERE date=? AND midi_note=?), 0) + ?,
                        COALESCE((SELECT total_velocity FROM note_distribution WHERE date=? AND midi_note=?), 0) + ?,
                        COALESCE((SELECT total_energy FROM note_distribution WHERE date=? AND midi_note=?), 0) + ?,
                        COALESCE((SELECT note_bytes FROM note_distribution WHERE date=? AND midi_note=?), 0) + ?,
                        COALESCE((SELECT total_duration_ms FROM note_distribution WHERE date=? AND midi_note=?), 0) + ?,
                        datetime('now', 'localtime'))
            ''', (date, midi_note, note_name, date, midi_note, count, date, midi_note, velocity,
                date, midi_note, energy, date, midi_note, bytes_count, date, midi_note, duration))
            
            self.conn.commit()
            
        except Exception as e:
            print(f"Error updating note distribution: {e}")
    
    def close_session(self, session_duration):
        """Close the current session"""
        if not self.conn:
            return
            
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE sessions 
                SET end_time = datetime('now', 'localtime'), duration_minutes = ?
                WHERE session_id = ?
            ''', (session_duration, self.session_id))
            self.conn.commit()
        except Exception as e:
            print(f"Error closing session: {e}")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()