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

    def midi_note_to_led(self, midi_note):
        """
        Convert MIDI note to LED index
        MIDI 21 (A0) -> LED 143
        MIDI 108 (C8) -> LED 56
        """
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

        led_index = self.midi_note_to_led(midi_note)
        if led_index is None:
            print(f"LED note_on: note {midi_note} out of range")
            return

        print(f"LED note_on: note={midi_note} -> LED {led_index}, setting blue")
        with self.lock:
            self.active_notes.add(midi_note)
            # Blue color (R=0, G=0, B=255)
            self._set_pixel(led_index, 0, 0, 255)
            self._show()
        print(f"LED note_on: complete for LED {led_index}")

    def note_off(self, midi_note):
        """Turn off LED when note is released"""
        if not self.enabled or not self.strip:
            return

        led_index = self.midi_note_to_led(midi_note)
        if led_index is None:
            return

        with self.lock:
            if midi_note in self.active_notes:
                self.active_notes.discard(midi_note)
            # Turn off (black)
            self._set_pixel(led_index, 0, 0, 0)
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
