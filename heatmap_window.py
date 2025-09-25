import tkinter as tk
from tkinter import ttk, messagebox

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

class HeatmapWindow:
    def __init__(self, main_app):
        self.main_app = main_app
        self.heatmap_window = None
        self.heatmap_figure = None
        self.heatmap_canvas = None
        self.heatmap_ax = None
        self.octave_var = None
    
    def show_heatmap(self):
        """Show keyboard heatmap using current session data"""
        if not MATPLOTLIB_AVAILABLE:
            messagebox.showerror("Missing Dependency", 
                               "matplotlib is required for heatmap!\n\nInstall with:\npip install matplotlib")
            return
        
        if self.heatmap_window is None or not self.heatmap_window.winfo_exists():
            self.create_heatmap_window()
        else:
            self.heatmap_window.lift()
            self.update_heatmap()
    
    def create_heatmap_window(self):
        """Create the heatmap visualization window"""
        self.heatmap_window = tk.Toplevel(self.main_app.root)
        self.heatmap_window.title("MIDI Keyboard Heatmap")
        self.heatmap_window.geometry("900x400")
        
        # Create matplotlib figure
        self.heatmap_figure, self.heatmap_ax = plt.subplots(figsize=(12, 5))
        self.heatmap_figure.patch.set_facecolor('white')
        
        # Embed in tkinter
        self.heatmap_canvas = FigureCanvasTkAgg(self.heatmap_figure, self.heatmap_window)
        self.heatmap_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Control frame
        control_frame = ttk.Frame(self.heatmap_window)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(control_frame, text="Refresh", command=self.update_heatmap).pack(side=tk.LEFT, padx=5)
        
        # Range selector
        ttk.Label(control_frame, text="Range:").pack(side=tk.LEFT, padx=(20, 5))
        self.octave_var = tk.StringVar(value="C2-C7")
        octave_combo = ttk.Combobox(control_frame, textvariable=self.octave_var, 
                                   values=["C-1-C4", "C1-C6", "C2-C7", "C3-C8", "C4-C9", "Full Range"], 
                                   state="readonly", width=10)
        octave_combo.pack(side=tk.LEFT, padx=5)
        octave_combo.bind("<<ComboboxSelected>>", lambda e: self.update_heatmap())
        
        self.update_heatmap()
    
    def get_key_info(self, midi_note):
        """Get key information for a MIDI note"""
        note_in_octave = midi_note % 12
        octave = midi_note // 12 - 1
        
        black_keys = [1, 3, 6, 8, 10]
        is_black = note_in_octave in black_keys
        
        white_key_notes = [0, 2, 4, 5, 7, 9, 11]
        
        if is_black:
            black_key_offsets = {1: 0.7, 3: 1.7, 6: 3.7, 8: 4.7, 10: 5.7}
            white_pos = black_key_offsets[note_in_octave]
        else:
            white_pos = white_key_notes.index(note_in_octave)
        
        return {
            'is_black': is_black,
            'octave': octave,
            'position_in_octave': white_pos,
            'note_name': self.main_app.get_note_name(midi_note)
        }
    
    def update_heatmap(self):
        """Update the keyboard heatmap visualization with energy display"""
        # Full implementation goes here - copy from original
        pass