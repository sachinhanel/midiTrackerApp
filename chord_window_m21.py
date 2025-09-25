# chord_window_m21.py
import tkinter as tk
from tkinter import ttk

from music21 import chord as m21chord
from music21 import pitch as m21pitch
from music21 import harmony as m21harmony
# Optional (for Roman numerals if you supply a key):
# from music21 import key as m21key, roman as m21roman

NOTE_NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']

def note_name(n): return NOTE_NAMES[n % 12]

def midi_to_m21_pitches(midi_numbers):
    """Convert MIDI ints to music21 Pitches (keep actual octaves)."""
    return [m21pitch.Pitch(midi=int(n)) for n in midi_numbers]

def chord_symbol_from_midi(midi_numbers):
    """
    Returns (symbol, details) using music21’s chord + harmony.
    symbol: e.g. 'C7', 'Gm9/B', 'F#maj7', '(no match)'.
    details: dict with root, bass, quality, commonName, inversion, tones.
    """
    if len(midi_numbers) < 2:
        return None, None

    # Build a music21 chord; duplicates are fine — chord handles them.
    pitches = midi_to_m21_pitches(sorted(midi_numbers))
    ch = m21chord.Chord(pitches)

    # Try to get a ChordSymbol figure via harmony
    symbol = None
    try:
        cs = m21harmony.chordSymbolFromChord(ch)  # returns a ChordSymbol/Harmony
        # cs.figure is the human-readable jazz symbol (if recognized)
        symbol = cs.figure if hasattr(cs, "figure") else None
    except Exception:
        symbol = None

    # Fallbacks if figure can’t be constructed for an exotic voicing:
    if not symbol:
        # Try a simpler label using commonName (e.g., 'dominant seventh chord')
        symbol = ch.pitchedCommonName or ch.commonName or "(no match)"

    # Add inversion/bass slash if music21 didn’t include it but we have a clear bass
    try:
        root_name = ch.root().name  # e.g., 'C#'
    except Exception:
        root_name = None
    try:
        bass_name = ch.bass().name
    except Exception:
        bass_name = None

    if symbol and root_name and bass_name and '/' not in symbol:
        # If bass is not root, add slash
        if root_name != bass_name:
            symbol = f"{symbol}/{bass_name}"

    details = {
        "root": root_name or "—",
        "bass": bass_name or "—",
        "quality": getattr(ch, "quality", "—"),
        "commonName": ch.commonName,
        "pitchedCommonName": ch.pitchedCommonName,
        "inversion": ch.inversion() if hasattr(ch, "inversion") else None,
        "tones": [p.nameWithOctave for p in ch.pitches],
    }
    return symbol, details


class Music21ChordWindow:
    def __init__(self, app, poll_ms=100, use_sustain=True):
        """
        app: your MidiTrackerGUI instance (reads app.active_notes and optional app.sustained_notes/pedal)
        use_sustain: union sustained notes with currently held notes
        """
        self.app = app
        self.poll_ms = poll_ms
        self.use_sustain = use_sustain
        self.window = None
        self._job = None

    def show(self):
        if self.window and self.window.winfo_exists():
            self.window.deiconify(); self.window.lift(); return

        self.window = tk.Toplevel(self.app.root)
        self.window.title("Chord Finder (music21)")
        self.window.geometry("380x220")
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        frame = ttk.Frame(self.window, padding=10)
        frame.pack(fill="both", expand=True)

        self.chord_label = ttk.Label(frame, text="—", font=("Arial", 22, "bold"))
        self.chord_label.pack(anchor="w")

        self.notes_var = tk.StringVar(value="Notes: —")
        ttk.Label(frame, textvariable=self.notes_var).pack(anchor="w", pady=(10,0))

        self.detail_var = tk.StringVar(value="Root: —  Bass: —  Quality: —  Inv: —")
        ttk.Label(frame, textvariable=self.detail_var).pack(anchor="w", pady=(4,0))

        self.hint_var = tk.StringVar(value="Hold ≥2 notes to detect. Uses music21.")
        ttk.Label(frame, textvariable=self.hint_var, foreground="gray").pack(anchor="w", pady=(8,0))

        self._schedule()

    def _schedule(self):
        self._job = self.app.root.after(self.poll_ms, self._tick)

    def _current_notes(self):
        # Start with currently pressed notes
        held = set(self.app.active_notes.keys())
        if self.use_sustain and hasattr(self.app, "sustained_notes"):
            held |= set(self.app.sustained_notes)
        return sorted(held)

    def _tick(self):
        midi_nums = self._current_notes()
        if len(midi_nums) >= 2:
            sym, det = chord_symbol_from_midi(midi_nums)
            note_names = " ".join(self.app.get_note_name(n) for n in midi_nums)
            self.notes_var.set(f"Notes: {note_names}")
            if sym:
                self.chord_label.config(text=sym)
                inv = det.get("inversion")
                inv_txt = "—" if inv is None else str(inv)
                self.detail_var.set(
                    f"Root: {det.get('root','—')}  "
                    f"Bass: {det.get('bass','—')}  "
                    f"Quality: {det.get('quality','—')}  "
                    f"Inv: {inv_txt}"
                )
                self.hint_var.set(det.get("pitchedCommonName") or det.get("commonName") or "")
            else:
                self.chord_label.config(text="(no match)")
                self.detail_var.set("Root: —  Bass: —  Quality: —  Inv: —")
                self.hint_var.set("Try a simpler voicing or fewer tensions.")
        else:
            self.chord_label.config(text="—")
            self.notes_var.set("Notes: —")
            self.detail_var.set("Root: —  Bass: —  Quality: —  Inv: —")
            self.hint_var.set("Hold ≥2 notes to detect. Uses music21.")

        self._schedule()

    def _on_close(self):
        if self._job:
            self.app.root.after_cancel(self._job)
            self._job = None
        self.window.destroy()
        self.window = None
