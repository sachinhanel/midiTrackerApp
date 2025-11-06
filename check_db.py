#!/usr/bin/env python3
"""
Database verification script - checks if data is being written correctly
Run this on the Raspberry Pi to diagnose database write issues
"""

import sqlite3
from datetime import datetime

conn = sqlite3.connect('/home/sachin/git/midiTrackerApp/midi_tracker.db')
cursor = conn.cursor()

# Check current time
print(f"Current local time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Check WAL mode
cursor.execute("PRAGMA journal_mode;")
print(f"Journal mode: {cursor.fetchone()[0]}")
print()

# Check today's hourly stats
today = datetime.now().strftime('%Y-%m-%d')
current_hour = datetime.now().hour
print(f"=== Hourly stats for today ({today}) ===")
cursor.execute("""
    SELECT date, hour, total_notes, session_time_seconds, total_energy
    FROM hourly_stats
    WHERE date = ?
    ORDER BY hour DESC
    LIMIT 10
""", (today,))
rows = cursor.fetchall()
if rows:
    for row in rows:
        print(f"Date: {row[0]}, Hour: {row[1]}, Notes: {row[2]}, Session: {row[3]}s, Energy: {row[4]:.2f}J")
else:
    print(f"No hourly stats found for today ({today})")
print()

# Check today's daily stats
print(f"=== Daily stats for today ({today}) ===")
cursor.execute("""
    SELECT date, total_notes, session_time_seconds, total_energy
    FROM daily_stats
    WHERE date = ?
""", (today,))
row = cursor.fetchone()
if row:
    print(f"Date: {row[0]}, Notes: {row[1]}, Session: {row[2]}s, Energy: {row[3]:.2f}J")
else:
    print(f"No daily stats found for today ({today})")
print()

# Check most recent note distribution entry
print("=== Most recent note distribution entries ===")
cursor.execute("""
    SELECT date, COUNT(*) as num_notes, SUM(count) as total_count
    FROM note_distribution
    GROUP BY date
    ORDER BY date DESC
    LIMIT 5
""")
for row in cursor.fetchall():
    print(f"Date: {row[0]}, Unique notes: {row[1]}, Total count: {row[2]}")

conn.close()
