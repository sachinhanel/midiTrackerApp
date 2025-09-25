import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import csv

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

class StatisticsWindow:
    def __init__(self, main_app):
        self.main_app = main_app
        self.stats_window = None
        
    
    def _metric_value(self, metric, notes, energy, session_time, duration_ms, pedal, bytes_total, avg_vel):
        if metric == "Total Notes":
            return notes or 0
        if metric == "Energy (J)":
            return energy or 0
        if metric == "Session Time (min)":
            return (session_time or 0) / 60
        if metric == "Note Duration (min)":
            return (duration_ms or 0) / 1000 / 60
        if metric == "Pedal Presses":
            return pedal or 0
        if metric == "Data (KB)":
            return (bytes_total or 0) / 1024
        if metric == "Average Velocity":
            return avg_vel or 0
        return 0

    def _add_months(self, dt, n):
        # move dt by n months, clamping day
        y = dt.year + (dt.month - 1 + n)//12
        m = (dt.month - 1 + n) % 12 + 1
        d = min(dt.day, [31,29 if y%4==0 and (y%100!=0 or y%400==0) else 28,31,30,31,30,31,31,30,31,30,31][m-1])
        return dt.replace(year=y, month=m, day=d)

    def show_statistics(self):
        """Show or update the statistics window"""
        if self.stats_window is None or not self.stats_window.winfo_exists():
            self.create_statistics_window()
        else:
            self.stats_window.lift()
            self.update_statistics()
    
    def create_statistics_window(self):
        """Create the statistics viewing window"""
        self.stats_window = tk.Toplevel(self.main_app.root)
        self.stats_window.title("MIDI Playing Statistics")
        self.stats_window.geometry("1000x700")
        
        # Create notebook for different views
        notebook = ttk.Notebook(self.stats_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Daily Overview tab
        daily_frame = ttk.Frame(notebook)
        notebook.add(daily_frame, text="Daily Overview")
        self.create_stats_tab(daily_frame, "daily")
        
        # Hourly Breakdown tab
        hourly_frame = ttk.Frame(notebook)
        notebook.add(hourly_frame, text="Hourly Breakdown")  
        self.create_stats_tab(hourly_frame, "hourly")

        # Weekly tab  
        weekly_frame = ttk.Frame(notebook)
        notebook.add(weekly_frame, text="Weekly")
        self.create_stats_tab(weekly_frame, "weekly")

        # Monthly tab
        monthly_frame = ttk.Frame(notebook)  
        notebook.add(monthly_frame, text="Monthly")
        self.create_stats_tab(monthly_frame, "monthly")
        
        # Trends tab
        trends_frame = ttk.Frame(notebook)
        notebook.add(trends_frame, text="Trends")
        self.create_stats_tab(trends_frame, "trends")
        
        # Control buttons
        button_frame = ttk.Frame(self.stats_window)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(button_frame, text="Refresh", command=self.update_statistics).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export Data", command=self.export_statistics).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Reset Database", command=self.reset_database).pack(side=tk.LEFT, padx=5)
        
        self.update_statistics()
    
    def create_stats_tab(self, parent, tab_type):
        """Create a statistics tab with table and graph"""
        # Create main container
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True)
        
        # Create graph frame at top
        self.create_graph_frame(container, tab_type)


        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        setattr(self, f'{tab_type}_stats_frame', scrollable_frame)
    
    def update_statistics(self):
        """Update all statistics displays"""
        self.update_daily_stats()
        self.update_hourly_stats()
        self.update_weekly_stats()
        self.update_monthly_stats()
        self.update_trends_stats()
    
    # All the update_daily_stats, update_hourly_stats, etc. methods go here
    # Copy them exactly as they are from the original file
    # They reference self.main_app.conn, self.main_app.energy_calculator, etc.

    def update_daily_stats(self):
        """Update daily statistics display with energy"""
        if not self.main_app.conn:
            return
            
        frame = getattr(self, 'daily_stats_frame', None)
        if not frame:
            return
        
        # Clear existing widgets
        for widget in frame.winfo_children():
            widget.destroy()
        
        try:
            cursor = self.main_app.conn.cursor()
            
            # Title
            ttk.Label(frame, text="Daily Practice Statistics", 
                    font=("Arial", 16, "bold")).grid(row=0, column=0, columnspan=7, pady=10)
            
            # Get recent daily data with energy
            cursor.execute('''
                SELECT date, total_notes, total_duration_ms, session_time_seconds, 
                       total_energy, pedal_presses, total_bytes
                FROM daily_stats 
                ORDER BY date DESC 
                LIMIT 30
            ''')
            
            daily_data = cursor.fetchall()
            
            if daily_data:
                # Create table headers
                headers = ["Date", "Notes", "Note Duration", "Session Time", "Energy", "Pedal", "Data"]
                
                for col, text in enumerate(headers):
                    ttk.Label(frame, text=text, font=("Arial", 10, "bold")).grid(
                        row=1, column=col, padx=5, pady=5, sticky="w")
                
                # Process the data rows
                for row, (date, notes, duration_ms, session_seconds, total_energy, pedal, bytes_total) in enumerate(daily_data, 2):
                    note_duration_min = (duration_ms or 0) / 1000 / 60
                    session_time_min = (session_seconds or 0) / 60
                    energy_display = self.main_app.energy_calculator.format_energy(total_energy or 0)
                    
                    ttk.Label(frame, text=date).grid(row=row, column=0, padx=5, sticky="w")
                    ttk.Label(frame, text=f"{notes or 0:,}").grid(row=row, column=1, padx=5, sticky="w")
                    ttk.Label(frame, text=f"{note_duration_min:.1f}m").grid(row=row, column=2, padx=5, sticky="w")
                    ttk.Label(frame, text=f"{session_time_min:.1f}m").grid(row=row, column=3, padx=5, sticky="w")
                    ttk.Label(frame, text=energy_display).grid(row=row, column=4, padx=5, sticky="w")
                    ttk.Label(frame, text=f"{pedal or 0}").grid(row=row, column=5, padx=5, sticky="w")
                    ttk.Label(frame, text=f"{(bytes_total or 0)/1024:.1f}KB").grid(row=row, column=6, padx=5, sticky="w")
            else:
                ttk.Label(frame, text="No data available yet", 
                        font=("Arial", 12)).grid(row=1, column=0, pady=20)
                
        except Exception as e:
            ttk.Label(frame, text=f"Error: {e}").grid(row=1, column=0, pady=20)
            print(f"Daily stats error: {e}")
    
    def update_hourly_stats(self):
        """Update hourly statistics display with energy"""
        if not self.main_app.conn:
            return
            
        frame = getattr(self, 'hourly_stats_frame', None)
        if not frame:
            return
        
        # Clear existing widgets
        for widget in frame.winfo_children():
            widget.destroy()
        
        try:
            cursor = self.main_app.conn.cursor()
            
            # Title
            ttk.Label(frame, text="Hourly Practice Patterns", 
                     font=("Arial", 16, "bold")).grid(row=0, column=0, columnspan=4, pady=10)
            
            # Get today's hourly data with energy
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT hour, total_notes, total_duration_ms, session_time_seconds, 
                       total_energy, pedal_presses, total_bytes
                FROM hourly_stats 
                WHERE date = ?
                ORDER BY hour
            ''', (today,))
            
            hourly_data = cursor.fetchall()
            
            if hourly_data:
                # Create hourly breakdown
                ttk.Label(frame, text=f"Today's Hourly Breakdown ({today})", 
                         font=("Arial", 12, "bold")).grid(row=1, column=0, columnspan=4, pady=10)
                
                columns = ["Hour", "Notes", "Note Duration", "Session Time", "Energy", "Pedal", "Data"]
                for col, text in enumerate(columns):
                    ttk.Label(frame, text=text, font=("Arial", 10, "bold")).grid(
                        row=2, column=col, padx=5, sticky="w")
                
                for row, (hour, notes, duration_ms, session_seconds, total_energy, pedal, bytes_total) in enumerate(hourly_data, 3):
                    duration_min = (duration_ms or 0) / 1000 / 60
                    session_min = (session_seconds or 0) / 60
                    energy_display = self.main_app.energy_calculator.format_energy(total_energy or 0)
                    safe_hour = hour or 0
                    
                    time_str = f"{safe_hour:02d}:00-{safe_hour:02d}:59"
                    
                    if bytes_total and bytes_total > 1024:
                        data_display = f"{(bytes_total/1024):.1f}KB"
                    else:
                        data_display = f"{bytes_total or 0}B"
                    
                    ttk.Label(frame, text=time_str).grid(row=row, column=0, padx=5, sticky="w")
                    ttk.Label(frame, text=f"{notes or 0:,}").grid(row=row, column=1, padx=5, sticky="w")
                    ttk.Label(frame, text=f"{duration_min:.1f}m").grid(row=row, column=2, padx=5, sticky="w")
                    ttk.Label(frame, text=f"{session_min:.1f}m").grid(row=row, column=3, padx=5, sticky="w")
                    ttk.Label(frame, text=energy_display).grid(row=row, column=4, padx=5, sticky="w")
                    ttk.Label(frame, text=f"{pedal or 0}").grid(row=row, column=5, padx=5, sticky="w")
                    ttk.Label(frame, text=data_display).grid(row=row, column=6, padx=5, sticky="w")
            else:
                ttk.Label(frame, text="No hourly data for today yet", 
                         font=("Arial", 12)).grid(row=1, column=0, pady=20)
                
        except Exception as e:
            ttk.Label(frame, text=f"Error: {e}").grid(row=1, column=0, pady=20)
            print(f"Hourly stats error: {e}")
    
    def update_weekly_stats(self):
        """Update weekly statistics display with energy"""
        if not self.main_app.conn:
            return
            
        frame = getattr(self, 'weekly_stats_frame', None)
        if not frame:
            return
        
        # Clear existing widgets
        for widget in frame.winfo_children():
            widget.destroy()
        
        try:
            cursor = self.main_app.conn.cursor()
            
            # Title
            ttk.Label(frame, text="Weekly Practice Statistics", 
                    font=("Arial", 16, "bold")).grid(row=0, column=0, columnspan=4, pady=10)
            
            # Get past 8 weeks of data with energy
            cursor.execute('''
                SELECT 
                    strftime('%Y-W%W', date) as week,
                    SUM(total_notes) as total_notes,
                    SUM(total_duration_ms) as total_duration,
                    SUM(session_time_seconds) as total_session_time,
                    SUM(total_energy) as total_energy,
                    SUM(pedal_presses) as pedal_presses,
                    SUM(total_bytes) as total_bytes,
                    COUNT(*) as active_days
                FROM daily_stats 
                WHERE date >= date('now', '-56 days')
                AND total_notes > 0
                GROUP BY strftime('%Y-W%W', date)
                ORDER BY week DESC
            ''')
            
            weekly_data = cursor.fetchall()
            
            if weekly_data:
                headers = ["Week", "Notes", "Note Duration", "Session Time", "Energy", "Pedal", "Data", "Days"]
                
                for col, text in enumerate(headers):
                    ttk.Label(frame, text=text, font=("Arial", 10, "bold")).grid(
                        row=1, column=col, padx=5, pady=5, sticky="w")
                
                for row, (week, notes, duration_ms, session_seconds, total_energy, pedal, bytes_total, days) in enumerate(weekly_data, 2):
                    duration_min = (duration_ms or 0) / 1000 / 60
                    session_min = (session_seconds or 0) / 60
                    energy_display = self.main_app.energy_calculator.format_energy(total_energy or 0)
                    
                    if bytes_total and bytes_total > 1024*1024:
                        data_display = f"{(bytes_total/(1024*1024)):.1f}MB"
                    elif bytes_total and bytes_total > 1024:
                        data_display = f"{(bytes_total/1024):.1f}KB"
                    else:
                        data_display = f"{bytes_total or 0}B"
                    
                    ttk.Label(frame, text=week).grid(row=row, column=0, padx=5, sticky="w")
                    ttk.Label(frame, text=f"{notes or 0:,}").grid(row=row, column=1, padx=5, sticky="w")
                    ttk.Label(frame, text=f"{duration_min:.0f}m").grid(row=row, column=2, padx=5, sticky="w")
                    ttk.Label(frame, text=f"{session_min:.0f}m").grid(row=row, column=3, padx=5, sticky="w")
                    ttk.Label(frame, text=energy_display).grid(row=row, column=4, padx=5, sticky="w")
                    ttk.Label(frame, text=f"{pedal or 0}").grid(row=row, column=5, padx=5, sticky="w")
                    ttk.Label(frame, text=data_display).grid(row=row, column=6, padx=5, sticky="w")
                    ttk.Label(frame, text=f"{days}").grid(row=row, column=7, padx=5, sticky="w")
            else:
                ttk.Label(frame, text="No weekly data available yet", 
                        font=("Arial", 12)).grid(row=1, column=0, pady=20)
                
        except Exception as e:
            ttk.Label(frame, text=f"Error: {e}").grid(row=1, column=0, pady=20)
            print(f"Weekly stats error: {e}")

    def update_monthly_stats(self):
        """Update monthly statistics display with energy"""
        if not self.main_app.conn:
            return
            
        frame = getattr(self, 'monthly_stats_frame', None)
        if not frame:
            return
        
        # Clear existing widgets
        for widget in frame.winfo_children():
            widget.destroy()
        
        try:
            cursor = self.main_app.conn.cursor()
            
            # Title
            ttk.Label(frame, text="Monthly Practice Statistics", 
                    font=("Arial", 16, "bold")).grid(row=0, column=0, columnspan=4, pady=10)
            
            # Get past 12 months of data with energy
            cursor.execute('''
                SELECT 
                    strftime('%Y-%m', date) as month,
                    SUM(total_notes) as total_notes,
                    SUM(total_duration_ms) as total_duration,
                    SUM(session_time_seconds) as total_session_time,
                    SUM(total_energy) as total_energy,
                    SUM(pedal_presses) as pedal_presses,
                    SUM(total_bytes) as total_bytes,
                    COUNT(*) as active_days
                FROM daily_stats 
                WHERE date >= date('now', '-365 days')
                AND total_notes > 0
                GROUP BY strftime('%Y-%m', date)
                ORDER BY month DESC
            ''')
            
            monthly_data = cursor.fetchall()
            
            if monthly_data:
                headers = ["Month", "Notes", "Note Duration", "Session Time", "Energy", "Pedal", "Data", "Days"]
                
                for col, text in enumerate(headers):
                    ttk.Label(frame, text=text, font=("Arial", 10, "bold")).grid(
                        row=1, column=col, padx=5, pady=5, sticky="w")
                
                for row, (month, notes, duration_ms, session_seconds, total_energy, pedal, bytes_total, days) in enumerate(monthly_data, 2):
                    duration_hours = (duration_ms or 0) / 1000 / 60 / 60
                    session_hours = (session_seconds or 0) / 60 / 60
                    energy_display = self.main_app.energy_calculator.format_energy(total_energy or 0)
                    
                    if bytes_total and bytes_total > 1024*1024:
                        data_display = f"{(bytes_total/(1024*1024)):.1f}MB"
                    elif bytes_total and bytes_total > 1024:
                        data_display = f"{(bytes_total/1024):.1f}KB"
                    else:
                        data_display = f"{bytes_total or 0}B"
                    
                    ttk.Label(frame, text=month).grid(row=row, column=0, padx=5, sticky="w")
                    ttk.Label(frame, text=f"{notes or 0:,}").grid(row=row, column=1, padx=5, sticky="w")
                    ttk.Label(frame, text=f"{duration_hours:.1f}h").grid(row=row, column=2, padx=5, sticky="w")
                    ttk.Label(frame, text=f"{session_hours:.1f}h").grid(row=row, column=3, padx=5, sticky="w")
                    ttk.Label(frame, text=energy_display).grid(row=row, column=4, padx=5, sticky="w")
                    ttk.Label(frame, text=f"{pedal or 0}").grid(row=row, column=5, padx=5, sticky="w")
                    ttk.Label(frame, text=data_display).grid(row=row, column=6, padx=5, sticky="w")
                    ttk.Label(frame, text=f"{days}").grid(row=row, column=7, padx=5, sticky="w")
            else:
                ttk.Label(frame, text="No monthly data available yet", 
                        font=("Arial", 12)).grid(row=1, column=0, pady=20)
                
        except Exception as e:
            ttk.Label(frame, text=f"Error: {e}").grid(row=1, column=0, pady=20)
            print(f"Monthly stats error: {e}")
    
    def update_trends_stats(self):
        """Update trends statistics display with all-time totals including energy"""
        if not self.main_app.conn:
            return
            
        frame = getattr(self, 'trends_stats_frame', None)
        if not frame:
            return
        
        # Clear existing widgets
        for widget in frame.winfo_children():
            widget.destroy()
        
        try:
            cursor = self.main_app.conn.cursor()
            
            # Title
            ttk.Label(frame, text="All Time Statistics", 
                    font=("Arial", 18, "bold")).grid(row=0, column=0, columnspan=4, pady=15)
            
            # Get all-time totals with energy
            cursor.execute('''
                SELECT 
                    SUM(total_notes) as total_notes,
                    SUM(total_duration_ms) as total_duration,
                    SUM(session_time_seconds) as total_session_time,
                    SUM(total_energy) as total_energy,
                    AVG(avg_velocity) as avg_velocity,
                    SUM(pedal_presses) as total_pedal,
                    SUM(total_bytes) as total_bytes,
                    COUNT(*) as total_days,
                    SUM(CASE WHEN total_notes > 0 THEN 1 ELSE 0 END) as active_days
                FROM daily_stats
            ''')
            
            result = cursor.fetchone()
            
            if result and result[0]:
                total_notes, total_duration, total_session_time, total_energy, avg_velocity, total_pedal, total_bytes, total_days, active_days = result
                
                # Convert durations
                total_note_hours = (total_duration or 0) / 1000 / 60 / 60
                total_session_hours = (total_session_time or 0) / 60 / 60
                energy_display = self.main_app.energy_calculator.format_energy(total_energy or 0)
                
                # Format data size
                if total_bytes and total_bytes > 1024*1024*1024:  # GB
                    data_display = f"{(total_bytes/(1024*1024*1024)):.2f} GB"
                elif total_bytes and total_bytes > 1024*1024:  # MB
                    data_display = f"{(total_bytes/(1024*1024)):.1f} MB"
                elif total_bytes and total_bytes > 1024:  # KB
                    data_display = f"{(total_bytes/1024):.1f} KB"
                else:
                    data_display = f"{total_bytes or 0} bytes"
                
                # Create summary with large font
                summary_frame = ttk.LabelFrame(frame, text="Lifetime Totals", padding=20)
                summary_frame.grid(row=1, column=0, columnspan=4, sticky="ew", padx=20, pady=10)
                
                # Row 1
                ttk.Label(summary_frame, text=f"{total_notes or 0:,}", 
                        font=("Arial", 24, "bold"), foreground="blue").grid(row=0, column=0, padx=20, pady=10)
                ttk.Label(summary_frame, text="Total Notes Played", 
                        font=("Arial", 12)).grid(row=1, column=0, padx=20)
                
                ttk.Label(summary_frame, text=f"{total_session_hours:.1f}", 
                        font=("Arial", 24, "bold"), foreground="green").grid(row=0, column=1, padx=20, pady=10)
                ttk.Label(summary_frame, text="Practice Session Hours", 
                        font=("Arial", 12)).grid(row=1, column=1, padx=20)
                
                ttk.Label(summary_frame, text=energy_display, 
                        font=("Arial", 24, "bold"), foreground="red").grid(row=0, column=2, padx=20, pady=10)
                ttk.Label(summary_frame, text="Total Energy", 
                        font=("Arial", 12)).grid(row=1, column=2, padx=20)
                
                # Row 2  
                ttk.Label(summary_frame, text=f"{total_note_hours:.1f}", 
                        font=("Arial", 24, "bold"), foreground="darkgreen").grid(row=2, column=0, padx=20, pady=10)
                ttk.Label(summary_frame, text="Note Duration Hours", 
                        font=("Arial", 12)).grid(row=3, column=0, padx=20)
                
                ttk.Label(summary_frame, text=f"{total_pedal or 0:,}", 
                        font=("Arial", 24, "bold"), foreground="purple").grid(row=2, column=1, padx=20, pady=10)
                ttk.Label(summary_frame, text="Pedal Presses", 
                        font=("Arial", 12)).grid(row=3, column=1, padx=20)
                
                # Row 3
                ttk.Label(summary_frame, text=f"{avg_velocity or 0:.1f}", 
                        font=("Arial", 24, "bold"), foreground="brown").grid(row=4, column=0, padx=20, pady=10)
                ttk.Label(summary_frame, text="Average Velocity", 
                        font=("Arial", 12)).grid(row=5, column=0, padx=20)
                
                ttk.Label(summary_frame, text=data_display, 
                        font=("Arial", 20, "bold"), foreground="orange").grid(row=4, column=1, padx=20, pady=10)
                ttk.Label(summary_frame, text="Total MIDI Data", 
                        font=("Arial", 12)).grid(row=5, column=1, padx=20)
                
                # Row 4
                ttk.Label(summary_frame, text=f"{active_days}/{total_days}", 
                        font=("Arial", 20, "bold"), foreground="darkblue").grid(row=6, column=0, padx=20, pady=10)
                ttk.Label(summary_frame, text="Active Days", 
                        font=("Arial", 12)).grid(row=7, column=0, padx=20)
                
                # Additional stats
                if active_days > 0:
                    avg_notes_per_day = (total_notes or 0) / active_days
                    avg_session_hours_per_day = total_session_hours / active_days
                    avg_energy_per_day = (total_energy or 0) / active_days
                    
                    additional_frame = ttk.LabelFrame(frame, text="Daily Averages", padding=15)
                    additional_frame.grid(row=2, column=0, columnspan=4, sticky="ew", padx=20, pady=10)
                    
                    ttk.Label(additional_frame, text=f"{avg_notes_per_day:.0f} notes/day", 
                            font=("Arial", 16, "bold")).grid(row=0, column=0, padx=20)
                    ttk.Label(additional_frame, text=f"{avg_session_hours_per_day:.1f} hours/day", 
                            font=("Arial", 16, "bold")).grid(row=0, column=1, padx=20)
                    
                    avg_energy_display = self.main_app.energy_calculator.format_energy(avg_energy_per_day)
                    ttk.Label(additional_frame, text=f"{avg_energy_display}/day", 
                            font=("Arial", 16, "bold")).grid(row=0, column=2, padx=20)


                # Most Used Notes Table - Scrollable
                if result and result[0]:  # If we have data
                    # Create frame for scrollable notes table
                    notes_outer_frame = ttk.LabelFrame(frame, text="Note Statistics (All Time)", padding=10)
                    notes_outer_frame.grid(row=3, column=0, columnspan=4, sticky="nsew", padx=20, pady=10)
                    
                    # Configure grid weight for expansion
                    frame.rowconfigure(3, weight=1)
                    notes_outer_frame.columnconfigure(0, weight=1)
                    notes_outer_frame.rowconfigure(0, weight=1)
                    
                    # Create canvas and scrollbar for scrollable content
                    notes_canvas = tk.Canvas(notes_outer_frame, height=300)
                    notes_scrollbar = ttk.Scrollbar(notes_outer_frame, orient="vertical", command=notes_canvas.yview)
                    notes_scrollable_frame = ttk.Frame(notes_canvas)
                    
                    notes_scrollable_frame.bind(
                        "<Configure>",
                        lambda e: notes_canvas.configure(scrollregion=notes_canvas.bbox("all"))
                    )
                    
                    notes_canvas.create_window((0, 0), window=notes_scrollable_frame, anchor="nw")
                    notes_canvas.configure(yscrollcommand=notes_scrollbar.set)
                    
                    notes_canvas.grid(row=0, column=0, sticky="nsew")
                    notes_scrollbar.grid(row=0, column=1, sticky="ns")
                    
                    # Get ALL notes from note_distribution
                    cursor.execute('''
                        SELECT 
                            midi_note,
                            note_name,
                            SUM(count) as total_count,
                            SUM(total_energy) as total_energy,
                            SUM(note_bytes) as total_bytes,
                            SUM(total_duration_ms) as total_duration
                        FROM note_distribution
                        WHERE midi_note >= 0  -- Exclude pedal (-1) and pitch bend (-2)
                        GROUP BY midi_note
                        ORDER BY total_count DESC
                    ''')
                    
                    all_notes = cursor.fetchall()
                    
                    if all_notes:
                        # Create headers
                        headers = ["Rank", "Note", "Count", "Energy", "Duration", "Data", "Avg Energy/Note"]
                        for col, header in enumerate(headers):
                            ttk.Label(notes_scrollable_frame, text=header, font=("Arial", 10, "bold")).grid(
                                row=0, column=col, padx=8, pady=5, sticky="w")
                        
                        # Display all notes
                        for rank, (midi_note, note_name, count, energy, bytes_total, duration_ms) in enumerate(all_notes, 1):
                            # Format values
                            energy_display = self.main_app.energy_calculator.format_energy(energy or 0)
                            avg_energy_per_note = (energy or 0) / max(1, count)
                            avg_energy_display = self.main_app.energy_calculator.format_energy(avg_energy_per_note)
                            duration_min = (duration_ms or 0) / 1000 / 60
                            
                            if bytes_total and bytes_total > 1024*1024:
                                data_display = f"{(bytes_total/(1024*1024)):.1f}MB"
                            elif bytes_total and bytes_total > 1024:
                                data_display = f"{(bytes_total/1024):.1f}KB"
                            else:
                                data_display = f"{bytes_total or 0}B"
                            
                            # Color code by rank
                            if rank == 1:
                                bg_color = "#FFD700"  # Gold
                                fg_color = "black"
                                font_weight = "bold"
                            elif rank == 2:
                                bg_color = "#C0C0C0"  # Silver
                                fg_color = "black"
                                font_weight = "bold"
                            elif rank == 3:
                                bg_color = "#CD7F32"  # Bronze
                                fg_color = "white"
                                font_weight = "bold"
                            elif rank <= 10:
                                bg_color = None
                                fg_color = "darkblue"
                                font_weight = "normal"
                            else:
                                bg_color = None
                                fg_color = "black"
                                font_weight = "normal"
                            
                            # Create row with background color if top 3
                            row_frame = ttk.Frame(notes_scrollable_frame)
                            if bg_color:
                                row_frame.configure(style='Colored.TFrame')
                                # Note: You'd need to configure the style, or just use Label backgrounds
                            
                            ttk.Label(notes_scrollable_frame, text=f"#{rank}", 
                                    font=("Arial", 9, font_weight), foreground=fg_color).grid(
                                    row=rank, column=0, padx=8, sticky="w")
                            ttk.Label(notes_scrollable_frame, text=note_name or f"Note {midi_note}", 
                                    font=("Arial", 9, font_weight), foreground=fg_color).grid(
                                    row=rank, column=1, padx=8, sticky="w")
                            ttk.Label(notes_scrollable_frame, text=f"{count:,}", 
                                    font=("Arial", 9)).grid(row=rank, column=2, padx=8, sticky="w")
                            ttk.Label(notes_scrollable_frame, text=energy_display, 
                                    font=("Arial", 9)).grid(row=rank, column=3, padx=8, sticky="w")
                            ttk.Label(notes_scrollable_frame, text=f"{duration_min:.1f}m", 
                                    font=("Arial", 9)).grid(row=rank, column=4, padx=8, sticky="w")
                            ttk.Label(notes_scrollable_frame, text=data_display, 
                                    font=("Arial", 9)).grid(row=rank, column=5, padx=8, sticky="w")
                            ttk.Label(notes_scrollable_frame, text=avg_energy_display, 
                                    font=("Arial", 9)).grid(row=rank, column=6, padx=8, sticky="w")
                        
                        # Add separator for pedal
                        separator_row = len(all_notes) + 1
                        ttk.Separator(notes_scrollable_frame, orient='horizontal').grid(
                            row=separator_row, column=0, columnspan=7, sticky="ew", pady=5)
                        
                        # Get pedal statistics
                        cursor.execute('''
                            SELECT 
                                SUM(count) as pedal_count,
                                SUM(note_bytes) as pedal_bytes
                            FROM note_distribution
                            WHERE midi_note = -1  -- Pedal events
                        ''')
                        
                        pedal_result = cursor.fetchone()
                        if pedal_result and pedal_result[0]:
                            pedal_count, pedal_bytes = pedal_result
                            
                            # Show pedal stats
                            pedal_row = separator_row + 1
                            ttk.Label(notes_scrollable_frame, text="", 
                                    font=("Arial", 9, "bold")).grid(
                                    row=pedal_row, column=0, padx=8, sticky="w")
                            ttk.Label(notes_scrollable_frame, text="🦶 PEDAL", 
                                    font=("Arial", 9, "bold"), foreground="purple").grid(
                                    row=pedal_row, column=1, padx=8, sticky="w")
                            ttk.Label(notes_scrollable_frame, text=f"{pedal_count or 0:,}", 
                                    font=("Arial", 9, "bold")).grid(
                                    row=pedal_row, column=2, padx=8, sticky="w")
                            
                            if pedal_bytes and pedal_bytes > 1024:
                                pedal_data = f"{(pedal_bytes/1024):.1f}KB"
                            else:
                                pedal_data = f"{pedal_bytes or 0}B"
                            
                            ttk.Label(notes_scrollable_frame, text=pedal_data, 
                                    font=("Arial", 9)).grid(
                                    row=pedal_row, column=5, padx=8, sticky="w")
                        
                        # Add summary at bottom
                        summary_row = separator_row + 3
                        ttk.Separator(notes_scrollable_frame, orient='horizontal').grid(
                            row=summary_row-1, column=0, columnspan=7, sticky="ew", pady=5)
                        
                        total_unique_notes = len(all_notes)
                        ttk.Label(notes_scrollable_frame, 
                                text=f"Total unique notes played: {total_unique_notes}", 
                                font=("Arial", 10, "italic")).grid(
                                row=summary_row, column=0, columnspan=7, padx=8, pady=5)
            
            else:
                ttk.Label(frame, text="No practice data available yet", 
                        font=("Arial", 16)).grid(row=1, column=0, pady=50)
                
        except Exception as e:
            ttk.Label(frame, text=f"Error: {e}").grid(row=1, column=0, pady=20)
            print(f"All-time stats error: {e}")


    def create_graph_frame(self, parent, graph_type):
        """Create a frame with graph and metric selector"""
        graph_frame = ttk.LabelFrame(parent, text="Data Visualization", padding=10)
        graph_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Control frame for metric selection
        control_frame = ttk.Frame(graph_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(control_frame, text="Select Metric:").pack(side=tk.LEFT, padx=5)
        
        # Metric selector dropdown
        metric_var = tk.StringVar()
        metrics = [
            "Total Notes",
            "Energy (J)", 
            "Session Time (min)",
            "Note Duration (min)",
            "Pedal Presses",
            "Data (KB)",
            "Average Velocity"
        ]
        
        metric_combo = ttk.Combobox(control_frame, textvariable=metric_var, 
                                    values=metrics, state="readonly", width=20)
        metric_combo.pack(side=tk.LEFT, padx=5)
        metric_combo.current(0)  # Default to Total Notes
        
        # Update button
        update_btn = ttk.Button(control_frame, text="Update Graph", 
                               command=lambda: self.update_graph(graph_type, metric_var.get()))
        update_btn.pack(side=tk.LEFT, padx=5)
        
        # Create matplotlib figure
        fig = Figure(figsize=(10, 4), dpi=80)
        ax = fig.add_subplot(111)
        
        # Embed in tkinter
        canvas = FigureCanvasTkAgg(fig, graph_frame)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Store references
        setattr(self, f'{graph_type}_figure', fig)
        setattr(self, f'{graph_type}_ax', ax)
        setattr(self, f'{graph_type}_canvas', canvas)
        setattr(self, f'{graph_type}_metric', metric_var)
        
        # Initial graph
        self.update_graph(graph_type, metric_var.get())
        
        return graph_frame
    
    def update_graph(self, graph_type, metric):
        """Update the graph with selected metric"""
        if not self.main_app.conn:
            return
            
        try:
            cursor = self.main_app.conn.cursor()
            ax = getattr(self, f'{graph_type}_ax')
            canvas = getattr(self, f'{graph_type}_canvas')
            
            ax.clear()
            
            # Get data based on graph type
            if graph_type == 'hourly':
                self.plot_hourly_data(ax, metric, cursor)
            elif graph_type == 'daily':
                self.plot_daily_data(ax, metric, cursor)
            elif graph_type == 'weekly':
                self.plot_weekly_data(ax, metric, cursor)
            elif graph_type == 'monthly':
                self.plot_monthly_data(ax, metric, cursor)
            elif graph_type == 'trends':
                self.plot_trends_data(ax, metric, cursor)
            
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # Rotate x-axis labels for better readability
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
            
            # Tight layout to prevent label cutoff
            ax.figure.tight_layout()
            
            canvas.draw()
            
        except Exception as e:
            print(f"Graph update error: {e}")
    
    def plot_hourly_data(self, ax, metric, cursor):
        """Plot hourly data for today with zero-filled missing hours"""
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT hour, total_notes, total_energy, session_time_seconds, 
                total_duration_ms, pedal_presses, total_bytes, avg_velocity
            FROM hourly_stats 
            WHERE date = ?
            ORDER BY hour
        ''', (today,))
        rows = cursor.fetchall()

        # Map existing rows by hour
        by_hour = {h: (notes, energy, sess, dur, ped, byt, vel)
                for (h, notes, energy, sess, dur, ped, byt, vel) in rows}

        hours = [f"{h:02d}:00" for h in range(24)]
        values = []
        for h in range(24):
            notes, energy, sess, dur, ped, byt, vel = by_hour.get(h, (0,0,0,0,0,0,0))
            values.append(self._metric_value(metric, notes, energy, sess, dur, ped, byt, vel))

        ax.bar(hours, values, alpha=0.7, label=metric)
        ax.set_xlabel('Hour')
        ax.set_ylabel(metric)
        ax.set_title(f'Hourly {metric} - {today}')

    
    def plot_daily_data(self, ax, metric, cursor):
        """Plot daily data for last 30 days with zero-filled missing days"""
        # Grab the last 30 days’ worth of raw rows
        cursor.execute('''
            SELECT date, total_notes, total_energy, session_time_seconds, 
                total_duration_ms, pedal_presses, total_bytes, avg_velocity
            FROM daily_stats 
            WHERE date >= date('now', '-30 days')
            ORDER BY date
        ''')
        rows = cursor.fetchall()

        if not rows:
            ax.text(0.5, 0.5, 'No data available', ha='center', va='center', 
                    transform=ax.transAxes, fontsize=14)
            return

        # Map DB rows by date
        by_date = {
            d: (notes, energy, sess, dur, ped, byt, vel)
            for (d, notes, energy, sess, dur, ped, byt, vel) in rows
        }

        # Build contiguous last 30 calendar days
        today = datetime.now().date()
        start = today - timedelta(days=29)
        dates = []
        values = []

        cur = start
        while cur <= today:
            key = cur.strftime('%Y-%m-%d')
            notes, energy, sess, dur, ped, byt, vel = by_date.get(key, (0,0,0,0,0,0,0))
            dates.append(key[-5:])  # show MM-DD
            values.append(self._metric_value(metric, notes, energy, sess, dur, ped, byt, vel))
            cur += timedelta(days=1)

        # Plot line + fill
        ax.plot(dates, values, marker='o', linestyle='-', color='green',
                markersize=4, label=metric)
        ax.fill_between(range(len(dates)), values, alpha=0.3, color='green')
        ax.set_xlabel('Date')
        ax.set_ylabel(metric)
        ax.set_title(f'Daily {metric} - Last 30 Days')
    
    def plot_weekly_data(self, ax, metric, cursor):
        """Plot weekly aggregated data with zero-filled missing weeks (last 12 weeks)"""
        cursor.execute('''
            SELECT 
                strftime('%Y-W%W', date) as week,
                SUM(total_notes) as total_notes,
                SUM(total_energy) as total_energy,
                SUM(session_time_seconds) as session_time,
                SUM(total_duration_ms) as duration_ms,
                SUM(pedal_presses) as pedal,
                SUM(total_bytes) as bytes_total,
                AVG(avg_velocity) as avg_vel
            FROM daily_stats 
            WHERE date >= date('now', '-84 days')
            AND total_notes > 0
            GROUP BY strftime('%Y-W%W', date)
            ORDER BY week
        ''')
        rows = cursor.fetchall()
        rowmap = {wk: (notes, energy, sess, dur, ped, byt, vel)
                for (wk, notes, energy, sess, dur, ped, byt, vel) in rows}

        # Build continuous list of last 12 calendar weeks using %W (Monday-based)
        today = datetime.now()
        # Go back to the Monday of this week:
        start_of_this_week = today - timedelta(days=today.weekday())
        weeks_labels = []
        values = []
        for i in range(12, 0, -1):
            week_start = start_of_this_week - timedelta(weeks=i-1)
            key = week_start.strftime('%Y-W%W')
            notes, energy, sess, dur, ped, byt, vel = rowmap.get(key, (0,0,0,0,0,0,0))
            weeks_labels.append(key[5:])  # show week number only
            values.append(self._metric_value(metric, notes, energy, sess, dur, ped, byt, vel))

        ax.bar(weeks_labels, values, alpha=0.7, label=metric)
        ax.set_xlabel('Week')
        ax.set_ylabel(metric)
        ax.set_title(f'Weekly {metric} - Last 12 Weeks')

    
    def plot_monthly_data(self, ax, metric, cursor):
        """Plot monthly aggregated data with zero-filled missing months (last 12 months)"""
        cursor.execute('''
            SELECT 
                strftime('%Y-%m', date) as month,
                SUM(total_notes) as total_notes,
                SUM(total_energy) as total_energy,
                SUM(session_time_seconds) as session_time,
                SUM(total_duration_ms) as duration_ms,
                SUM(pedal_presses) as pedal,
                SUM(total_bytes) as bytes_total,
                AVG(avg_velocity) as avg_vel
            FROM daily_stats 
            WHERE date >= date('now', '-365 days')
            AND total_notes > 0
            GROUP BY strftime('%Y-%m', date)
            ORDER BY month
        ''')
        rows = cursor.fetchall()
        rowmap = {m: (notes, energy, sess, dur, ped, byt, vel)
                for (m, notes, energy, sess, dur, ped, byt, vel) in rows}

        # Build contiguous last 12 months list (YYYY-MM)
        today = datetime.now().replace(day=1)
        months_keys = []
        months_labels = []
        for i in range(11, -1, -1):
            mdate = self._add_months(today, -i)
            key = mdate.strftime('%Y-%m')
            months_keys.append(key)
            months_labels.append(key[5:])  # show MM only

        values = []
        for key in months_keys:
            notes, energy, sess, dur, ped, byt, vel = rowmap.get(key, (0,0,0,0,0,0,0))
            values.append(self._metric_value(metric, notes, energy, sess, dur, ped, byt, vel))

        ax.plot(months_labels, values, marker='s', linestyle='-', linewidth=2, label=metric)
        ax.fill_between(range(len(months_labels)), values, alpha=0.3)
        ax.set_xlabel('Month')
        ax.set_ylabel(metric)
        ax.set_title(f'Monthly {metric} - Last 12 Months')

    
    def plot_trends_data(self, ax, metric, cursor):
        """Plot long-term trends with gaps zero-filled per day between min and max date"""
        cursor.execute('''
            SELECT date, total_notes, total_energy, session_time_seconds, 
                total_duration_ms, pedal_presses, total_bytes, avg_velocity
            FROM daily_stats 
            ORDER BY date
        ''')
        rows = cursor.fetchall()
        if not rows:
            ax.text(0.5, 0.5, 'No data available', ha='center', va='center', 
                    transform=ax.transAxes, fontsize=14)
            return

        # Map by date -> row tuple
        by_date = {d: (notes, energy, sess, dur, ped, byt, vel)
                for (d, notes, energy, sess, dur, ped, byt, vel) in rows}

        # Build contiguous date range from first to last date
        first_date = datetime.strptime(rows[0][0], '%Y-%m-%d').date()
        last_date  = datetime.strptime(rows[-1][0], '%Y-%m-%d').date()

        dates = []
        values = []
        cur = first_date
        while cur <= last_date:
            key = cur.strftime('%Y-%m-%d')
            notes, energy, sess, dur, ped, byt, vel = by_date.get(key, (0,0,0,0,0,0,0))
            dates.append(key)
            values.append(self._metric_value(metric, notes, energy, sess, dur, ped, byt, vel))
            cur += timedelta(days=1)

        # Raw series (light)
        ax.plot(range(len(dates)), values, alpha=0.3, label='Daily')

        # 7-day moving average (only if enough points)
        if len(values) >= 7:
            kernel = np.ones(7)/7
            moving = np.convolve(values, kernel, mode='valid')
            # align x positions center-ish
            start = 3  # (7-1)//2
            xs = range(start, start+len(moving))
            ax.plot(xs, moving, linewidth=2, label='7-day Average')

        ax.set_xlabel('Days')
        ax.set_ylabel(metric)
        ax.set_title(f'Long-term Trend: {metric}')

        # Show about 10 evenly-spaced date labels
        step = max(1, len(dates)//10)
        ax.set_xticks(range(0, len(dates), step))
        ax.set_xticklabels([dates[i][-5:] for i in range(0, len(dates), step)])

    
    def export_statistics(self):
        """Export aggregated statistics to CSV"""
        if not self.main_app.conn:
            messagebox.showerror("Error", "No database connection")
            return
            
        try:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Export Statistics"
            )
                
            if filename:
                cursor = self.main_app.conn.cursor()
                cursor.execute('''
                    SELECT date, total_notes, total_duration_ms, total_energy, avg_velocity, 
                           pedal_presses, total_bytes
                    FROM daily_stats 
                    ORDER BY date DESC
                ''')
                    
                with open(filename, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Date', 'Total Notes', 'Duration (ms)', 'Energy (J)', 'Avg Velocity', 'Pedal Presses', 'Total Bytes'])
                    writer.writerows(cursor.fetchall())
                    
                messagebox.showinfo("Export Complete", f"Statistics exported to {filename}")
                    
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export: {e}")
    
    def reset_database(self):
        """Reset/clear the entire database"""
        result = messagebox.askyesnocancel(
            "Reset Database", 
            "⚠️  WARNING: This will permanently delete ALL your MIDI data!\n\n" +
            "This includes:\n" +
            "• All daily statistics\n" +
            "• All hourly breakdowns\n" +
            "• All session data\n" +
            "• All practice history\n\n" +
            "This action CANNOT be undone!\n\n" +
            "Are you absolutely sure you want to reset the database?"
        )
        
        if result:
            try:
                if self.main_app.conn:
                    cursor = self.main_app.conn.cursor()
                    
                    # Delete all data
                    cursor.execute("DELETE FROM daily_stats")
                    cursor.execute("DELETE FROM hourly_stats") 
                    cursor.execute("DELETE FROM sessions")
                    cursor.execute("DELETE FROM note_distribution")
                    
                    # Reset sequences
                    cursor.execute("DELETE FROM sqlite_sequence")
                    
                    self.main_app.conn.commit()
                    
                    # Reset session counters in main app
                    self.main_app.reset_session_counters()
                    
                    messagebox.showinfo("Database Reset", "Database has been completely reset.\nAll historical data has been deleted.")
                    self.main_app.add_debug_message("💣 Database reset - all data cleared")
                    
            except Exception as e:
                messagebox.showerror("Reset Error", f"Failed to reset database:\n{e}")