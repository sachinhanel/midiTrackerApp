#!/usr/bin/env python3
"""
Simple LED Strip Controller for MIDI Piano Visualization
- 144 LED WS2812B strip
- Last 88 LEDs map to the 88 piano keys
- LED 143 = MIDI note 21 (A0, lowest)
- LED 56 = MIDI note 108 (C8, highest)
- LEDs 0-4 stay lit to show program is running
"""

import time
import threading
import json
import os

WS281X_AVAILABLE = False
PixelStrip = None
Color = None

# Try Adafruit NeoPixel first (Pi 5 compatible)
try:
    import board
    import neopixel
    WS281X_AVAILABLE = True
    USING_NEOPIXEL = True
    print("LED library loaded successfully (using Adafruit NeoPixel for Pi 5)")
except ImportError:
    # Fall back to rpi_ws281x for older Pi models
    try:
        from rpi_ws281x import PixelStrip, Color
        WS281X_AVAILABLE = True
        USING_NEOPIXEL = False
        print("LED library loaded successfully (using rpi_ws281x)")
    except ImportError as e:
        print(f"Warning: LED library not available: {e}")
        print("For Raspberry Pi 5, install with: pip install adafruit-circuitpython-neopixel")
        print("For older Pi models, install with: sudo pip install rpi-ws281x")
        USING_NEOPIXEL = False


class LEDController:
    # LED strip configuration
    LED_COUNT = 144
    LED_PIN = 18             # GPIO 18 (PWM0)
    LED_FREQ_HZ = 800000
    LED_DMA = 10
    LED_BRIGHTNESS = 128     # 0-255
    LED_INVERT = False
    LED_CHANNEL = 0

    # Piano mapping
    PIANO_LOWEST_NOTE = 21   # A0
    PIANO_HIGHEST_NOTE = 108 # C8

    def __init__(self):
        self.enabled = False
        self.strip = None
        self.active_notes = set()
        self.lock = threading.Lock()
        self.using_neopixel = USING_NEOPIXEL
        self.status_leds_enabled = True
        self.brightness = self.LED_BRIGHTNESS

        # Double LED mode settings
        # With 144 LEDs and 2 LEDs per key, we can cover 72 keys (144/2=72)
        # Skipping 8 keys on each end (16 total) leaves us with middle 72 keys
        self.double_led_mode = False
        self.double_led_start_note = 29  # Skip 8 lowest keys: 21-28, start at F#1 (note 29)
        self.double_led_end_note = 100   # Skip 8 highest keys: 101-108, end at E7 (note 100)

        # Color preset settings
        self.note_color = (0, 0, 255)  # Default blue
        self.background_color = None   # No background by default
        self.background_color_full = None  # Store the full brightness background color
        self.background_brightness = 100  # Background brightness percentage (0-100)
        self.sustain_pedal_hold = False
        self.sustain_pedal_active = False

        if WS281X_AVAILABLE:
            try:
                if USING_NEOPIXEL:
                    # Adafruit NeoPixel for Pi 5
                    import board
                    import neopixel
                    # GPIO 18 = board.D18
                    self.strip = neopixel.NeoPixel(
                        board.D18,
                        self.LED_COUNT,
                        brightness=self.LED_BRIGHTNESS / 255.0,
                        auto_write=False,
                        pixel_order=neopixel.GRB
                    )
                    print(f"LED Controller initialized (NeoPixel): {self.LED_COUNT} LEDs on GPIO 18")
                else:
                    # rpi_ws281x for older Pi models
                    self.strip = PixelStrip(
                        self.LED_COUNT,
                        self.LED_PIN,
                        self.LED_FREQ_HZ,
                        self.LED_DMA,
                        self.LED_INVERT,
                        self.LED_BRIGHTNESS,
                        self.LED_CHANNEL
                    )
                    self.strip.begin()
                    print(f"LED Controller initialized (rpi_ws281x): {self.LED_COUNT} LEDs on GPIO {self.LED_PIN}")
                self.clear_all()
            except Exception as e:
                print(f"Error initializing LED strip: {e}")
                print("Make sure to run with sudo for GPIO access")
                if not USING_NEOPIXEL:
                    print("For Raspberry Pi 5, try: pip install adafruit-circuitpython-neopixel")
                self.strip = None
        else:
            print("LED Controller: LED library not available (simulation mode)")

        # Auto-load saved preset if it exists
        if os.path.exists('led_preset.json'):
            print("Found saved preset, loading...")
            self.load_preset()

    def midi_note_to_led(self, midi_note):
        """
        Convert MIDI note to LED index (or indices in double LED mode)

        Single LED mode (default):
            MIDI 21 (A0) -> LED 143
            MIDI 108 (C8) -> LED 56
            Returns single LED index

        Double LED mode:
            Uses 2 LEDs per key for 72 keys (notes 29-100)
            Notes outside this range return None
            Returns tuple of (led_index1, led_index2)
        """
        if self.double_led_mode:
            # Double LED mode: 2 LEDs per key, covering notes 29-100 (72 keys)
            if midi_note < self.double_led_start_note or midi_note > self.double_led_end_note:
                return None  # Note is outside the covered range

            # Calculate offset from start note
            offset = midi_note - self.double_led_start_note
            # Each key uses 2 LEDs, starting from LED 143 going down
            led_index1 = self.LED_COUNT - 1 - (offset * 2)
            led_index2 = led_index1 - 1
            return (led_index1, led_index2)
        else:
            # Single LED mode (original behavior)
            if midi_note < self.PIANO_LOWEST_NOTE or midi_note > self.PIANO_HIGHEST_NOTE:
                return None

            offset = midi_note - self.PIANO_LOWEST_NOTE
            led_index = self.LED_COUNT - 1 - offset
            return led_index

    def _set_pixel(self, index, r, g, b):
        """Set a pixel color (handles both APIs)"""
        if self.using_neopixel:
            # NeoPixel API: strip[index] = (r, g, b)
            self.strip[index] = (r, g, b)
        else:
            # rpi_ws281x API: setPixelColor(index, Color(g, r, b))
            # Note: Color() takes GRB not RGB
            self.strip.setPixelColor(index, Color(g, r, b))

    def _show(self):
        """Update the strip (handles both APIs)"""
        if self.using_neopixel:
            self.strip.show()
        else:
            self.strip.show()

    def note_on(self, midi_note, velocity):
        """Light up LED when note is pressed"""
        if not self.enabled:
            print(f"LED note_on: disabled (note={midi_note})")
            return
        if not self.strip:
            print(f"LED note_on: no strip (note={midi_note})")
            return

        led_result = self.midi_note_to_led(midi_note)
        if led_result is None:
            print(f"LED note_on: note {midi_note} out of range")
            return

        print(f"LED note_on: note={midi_note} -> LED {led_result}, setting color {self.note_color}")
        with self.lock:
            self.active_notes.add(midi_note)
            # Use configured note color
            if self.note_color:
                if isinstance(led_result, tuple):
                    # Double LED mode
                    for led_index in led_result:
                        self._set_pixel(led_index, self.note_color[0], self.note_color[1], self.note_color[2])
                else:
                    # Single LED mode
                    self._set_pixel(led_result, self.note_color[0], self.note_color[1], self.note_color[2])
            self._show()
        print(f"LED note_on: complete for LED {led_result}")

    def note_off(self, midi_note):
        """Turn off LED when note is released"""
        if not self.enabled or not self.strip:
            return

        # If sustain pedal is held and sustain_pedal_hold is enabled, don't turn off
        if self.sustain_pedal_hold and self.sustain_pedal_active:
            return

        led_result = self.midi_note_to_led(midi_note)
        if led_result is None:
            return

        with self.lock:
            if midi_note in self.active_notes:
                self.active_notes.discard(midi_note)
            # Turn off or set to background color
            if isinstance(led_result, tuple):
                # Double LED mode
                for led_index in led_result:
                    if self.background_color:
                        self._set_pixel(led_index, self.background_color[0], self.background_color[1], self.background_color[2])
                    else:
                        self._set_pixel(led_index, 0, 0, 0)
            else:
                # Single LED mode
                if self.background_color:
                    self._set_pixel(led_result, self.background_color[0], self.background_color[1], self.background_color[2])
                else:
                    self._set_pixel(led_result, 0, 0, 0)
            self._show()

    def update_status_leds(self):
        """Keep LEDs 0-4 lit to show program is running"""
        if not self.strip:
            return

        if self.status_leds_enabled:
            # Green indicator LEDs (R=0, G=50, B=0)
            for i in range(5):
                self._set_pixel(i, 0, 50, 0)
        else:
            # Turn off status LEDs
            for i in range(5):
                self._set_pixel(i, 0, 0, 0)
        self._show()

    def toggle_status_leds(self):
        """Toggle status LEDs on/off"""
        self.status_leds_enabled = not self.status_leds_enabled
        self.update_status_leds()
        return self.status_leds_enabled

    def set_double_led_mode(self, enabled):
        """
        Enable or disable double LED mode.

        In double LED mode:
        - Each piano key lights up 2 LEDs for better visibility
        - Covers 72 keys (notes 29-100), skipping 8 on each end
        - Uses all 144 LEDs for piano visualization
        """
        self.double_led_mode = enabled

        # Clear all LEDs and reapply background if enabled
        if self.enabled and self.strip:
            with self.lock:
                # Clear all LEDs first
                for i in range(self.LED_COUNT):
                    self._set_pixel(i, 0, 0, 0)

                # Reapply background color to new note range
                if self.double_led_mode:
                    note_range = range(self.double_led_start_note, self.double_led_end_note + 1)
                else:
                    note_range = range(self.PIANO_LOWEST_NOTE, self.PIANO_HIGHEST_NOTE + 1)

                for midi_note in note_range:
                    led_result = self.midi_note_to_led(midi_note)
                    if led_result is not None and self.background_color:
                        if isinstance(led_result, tuple):
                            for led_index in led_result:
                                self._set_pixel(led_index, self.background_color[0], self.background_color[1], self.background_color[2])
                        else:
                            self._set_pixel(led_result, self.background_color[0], self.background_color[1], self.background_color[2])

                self._show()

            # Update status LEDs
            self.update_status_leds()

        mode_str = "Double LED (2 LEDs per key, 72 keys)" if enabled else "Single LED (1 LED per key, 88 keys)"
        print(f"LED mode set to: {mode_str}")
        return self.double_led_mode

    def get_double_led_mode(self):
        """Get current double LED mode status"""
        return self.double_led_mode

    def set_brightness(self, brightness):
        """Set LED strip brightness (0-255)"""
        if not self.strip:
            return False

        self.brightness = max(0, min(255, brightness))

        if self.using_neopixel:
            # NeoPixel uses 0.0-1.0 brightness
            self.strip.brightness = self.brightness / 255.0
            self.strip.show()
        else:
            # rpi_ws281x brightness is set at initialization
            # Would need to reinitialize or manually scale colors
            print(f"Warning: Brightness change requires restart for rpi_ws281x")

        print(f"Brightness set to {self.brightness}/255 ({int(self.brightness/255*100)}%)")
        return True

    def set_color_preset(self, note_color=None, background_color=None, background_color_full=None, background_brightness=100, sustain_pedal_hold=False):
        """
        Set color preset for LED visualization

        Args:
            note_color: RGB tuple (r, g, b) or None to disable note color
            background_color: RGB tuple (r, g, b) with brightness applied, or None for black background
            background_color_full: RGB tuple (r, g, b) at full brightness (for saving/loading)
            background_brightness: Background brightness percentage (0-100)
            sustain_pedal_hold: bool, whether to keep notes lit while sustain pedal is held
        """
        self.note_color = note_color
        self.background_color = background_color
        self.background_color_full = background_color_full if background_color_full else background_color
        self.background_brightness = background_brightness
        self.sustain_pedal_hold = sustain_pedal_hold

        # Apply background color to all piano keys immediately
        if self.enabled and self.strip:
            with self.lock:
                # Determine note range based on LED mode
                if self.double_led_mode:
                    note_range = range(self.double_led_start_note, self.double_led_end_note + 1)
                else:
                    note_range = range(self.PIANO_LOWEST_NOTE, self.PIANO_HIGHEST_NOTE + 1)

                for midi_note in note_range:
                    led_result = self.midi_note_to_led(midi_note)
                    if led_result is not None:
                        # Skip active notes
                        if midi_note not in self.active_notes:
                            if isinstance(led_result, tuple):
                                # Double LED mode
                                for led_index in led_result:
                                    if background_color:
                                        self._set_pixel(led_index, background_color[0], background_color[1], background_color[2])
                                    else:
                                        self._set_pixel(led_index, 0, 0, 0)
                            else:
                                # Single LED mode
                                if background_color:
                                    self._set_pixel(led_result, background_color[0], background_color[1], background_color[2])
                                else:
                                    self._set_pixel(led_result, 0, 0, 0)
                self._show()

        print(f"Color preset updated: note={note_color}, bg={background_color}, sustain_hold={sustain_pedal_hold}")
        return True

    def save_preset(self, preset_file='led_preset.json'):
        """
        Save current color preset to a JSON file

        Args:
            preset_file: filename to save preset to (relative to current directory)
        """
        preset_data = {
            'note_color': self.note_color,
            'background_color_full': self.background_color_full,  # Save full brightness version
            'background_brightness': self.background_brightness,
            'sustain_pedal_hold': self.sustain_pedal_hold,
            'brightness': self.brightness,
            'double_led_mode': self.double_led_mode
        }

        try:
            with open(preset_file, 'w') as f:
                json.dump(preset_data, f, indent=2)
            print(f"Preset saved to {preset_file}")
            return True
        except Exception as e:
            print(f"Error saving preset: {e}")
            return False

    def load_preset(self, preset_file='led_preset.json'):
        """
        Load color preset from a JSON file

        Args:
            preset_file: filename to load preset from (relative to current directory)
        """
        if not os.path.exists(preset_file):
            print(f"Preset file {preset_file} not found")
            return False

        try:
            with open(preset_file, 'r') as f:
                preset_data = json.load(f)

            # Convert lists back to tuples if needed
            note_color = tuple(preset_data['note_color']) if preset_data.get('note_color') else None
            background_color_full = tuple(preset_data['background_color_full']) if preset_data.get('background_color_full') else None
            background_brightness = preset_data.get('background_brightness', 100)

            # Apply background brightness to get actual background color
            background_color = None
            if background_color_full:
                brightness_factor = background_brightness / 100.0
                background_color = (
                    int(background_color_full[0] * brightness_factor),
                    int(background_color_full[1] * brightness_factor),
                    int(background_color_full[2] * brightness_factor)
                )

            # Apply the preset
            self.set_color_preset(
                note_color=note_color,
                background_color=background_color,
                background_color_full=background_color_full,
                background_brightness=background_brightness,
                sustain_pedal_hold=preset_data.get('sustain_pedal_hold', False)
            )

            # Apply overall brightness if saved
            if 'brightness' in preset_data:
                self.set_brightness(preset_data['brightness'])

            # Apply double LED mode if saved
            if 'double_led_mode' in preset_data:
                self.set_double_led_mode(preset_data['double_led_mode'])

            print(f"Preset loaded from {preset_file}")
            return True
        except Exception as e:
            print(f"Error loading preset: {e}")
            return False

    def sustain_pedal_on(self):
        """Called when sustain pedal is pressed"""
        self.sustain_pedal_active = True
        print("Sustain pedal ON")

    def sustain_pedal_off(self, currently_held_notes=None):
        """
        Called when sustain pedal is released

        Args:
            currently_held_notes: set of MIDI notes that are currently being physically held down
        """
        self.sustain_pedal_active = False
        print("Sustain pedal OFF")

        # If sustain_pedal_hold is enabled, turn off notes that are NOT currently being held
        if self.sustain_pedal_hold and self.enabled and self.strip:
            if currently_held_notes is None:
                currently_held_notes = set()

            with self.lock:
                notes_to_clear = list(self.active_notes)
                for midi_note in notes_to_clear:
                    # Only turn off LEDs for notes that are NOT currently being held
                    if midi_note not in currently_held_notes:
                        led_result = self.midi_note_to_led(midi_note)
                        if led_result is not None:
                            if isinstance(led_result, tuple):
                                # Double LED mode
                                for led_index in led_result:
                                    if self.background_color:
                                        self._set_pixel(led_index, self.background_color[0], self.background_color[1], self.background_color[2])
                                    else:
                                        self._set_pixel(led_index, 0, 0, 0)
                            else:
                                # Single LED mode
                                if self.background_color:
                                    self._set_pixel(led_result, self.background_color[0], self.background_color[1], self.background_color[2])
                                else:
                                    self._set_pixel(led_result, 0, 0, 0)
                        self.active_notes.discard(midi_note)
                self._show()
                print(f"Sustain release: cleared {len(notes_to_clear) - len(currently_held_notes)} notes, kept {len(currently_held_notes)} held notes")

    def enable(self):
        """Enable LED visualization"""
        if not self.strip:
            print("Cannot enable LED controller: hardware not available")
            return False

        self.enabled = True
        self.clear_all()
        self.update_status_leds()
        print("LED visualization enabled")
        return True

    def disable(self):
        """Disable LED visualization"""
        self.enabled = False
        self.clear_all()
        print("LED visualization disabled")

    def clear_all(self):
        """Turn off all LEDs"""
        if not self.strip:
            return

        with self.lock:
            self.active_notes.clear()
            for i in range(self.LED_COUNT):
                self._set_pixel(i, 0, 0, 0)
            self._show()

    def test_pattern(self):
        """Display a test pattern"""
        if not self.strip:
            print("Cannot run test: hardware not available")
            return

        print("Running LED test pattern...")

        # Light up status LEDs (green)
        for i in range(5):
            self._set_pixel(i, 0, 50, 0)
        self._show()
        time.sleep(0.5)

        # Light up piano range bottom to top (blue)
        for midi_note in range(self.PIANO_LOWEST_NOTE, self.PIANO_HIGHEST_NOTE + 1):
            led_index = self.midi_note_to_led(midi_note)
            self._set_pixel(led_index, 0, 0, 255)
            self._show()
            time.sleep(0.005)

        time.sleep(0.5)

        # Clear piano range
        for midi_note in range(self.PIANO_LOWEST_NOTE, self.PIANO_HIGHEST_NOTE + 1):
            led_index = self.midi_note_to_led(midi_note)
            self._set_pixel(led_index, 0, 0, 0)
            self._show()
            time.sleep(0.005)

        print("Test pattern complete")

    def cleanup(self):
        """Clean up resources"""
        self.clear_all()


# Singleton instance
_led_controller = None

def get_led_controller():
    """Get or create the global LED controller instance"""
    global _led_controller
    if _led_controller is None:
        _led_controller = LEDController()
    return _led_controller


if __name__ == "__main__":
    print("LED Controller Test Mode")
    controller = LEDController()

    if controller.strip:
        print("Running test pattern...")
        controller.test_pattern()

        print("\nSimulating piano notes...")
        controller.enable()

        # Simulate middle C and friends
        test_notes = [60, 62, 64, 65, 67]  # C D E F G
        for note in test_notes:
            print(f"Note ON: {note}")
            controller.note_on(note, 100)
            time.sleep(0.3)

        time.sleep(0.5)

        for note in test_notes:
            print(f"Note OFF: {note}")
            controller.note_off(note)
            time.sleep(0.2)

        time.sleep(1.0)
        controller.cleanup()
    else:
        print("No LED hardware available for testing")
