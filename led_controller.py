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

try:
    from rpi_ws281x import PixelStrip, Color
    WS281X_AVAILABLE = True
except ImportError:
    print("Warning: rpi_ws281x not available. Install with: sudo pip3 install rpi_ws281x")
    WS281X_AVAILABLE = False


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

        if WS281X_AVAILABLE:
            try:
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
                print(f"LED Controller initialized: {self.LED_COUNT} LEDs on GPIO {self.LED_PIN}")
                self.clear_all()
            except Exception as e:
                print(f"Error initializing LED strip: {e}")
                print("Make sure to run with sudo for GPIO access")
                self.strip = None
        else:
            print("LED Controller: rpi_ws281x not available (simulation mode)")

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

    def note_on(self, midi_note, velocity):
        """Light up LED when note is pressed"""
        if not self.enabled or not self.strip:
            return

        led_index = self.midi_note_to_led(midi_note)
        if led_index is None:
            return

        with self.lock:
            self.active_notes.add(midi_note)
            # Blue color
            self.strip.setPixelColor(led_index, Color(0, 0, 255))
            self.strip.show()

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
            self.strip.setPixelColor(led_index, Color(0, 0, 0))
            self.strip.show()

    def update_status_leds(self):
        """Keep LEDs 0-4 lit to show program is running"""
        if not self.strip:
            return

        # Green indicator LEDs
        for i in range(5):
            self.strip.setPixelColor(i, Color(0, 50, 0))
        self.strip.show()

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
                self.strip.setPixelColor(i, Color(0, 0, 0))
            self.strip.show()

    def test_pattern(self):
        """Display a test pattern"""
        if not self.strip:
            print("Cannot run test: hardware not available")
            return

        print("Running LED test pattern...")

        # Light up status LEDs
        for i in range(5):
            self.strip.setPixelColor(i, Color(0, 50, 0))
        self.strip.show()
        time.sleep(0.5)

        # Light up piano range bottom to top
        for midi_note in range(self.PIANO_LOWEST_NOTE, self.PIANO_HIGHEST_NOTE + 1):
            led_index = self.midi_note_to_led(midi_note)
            self.strip.setPixelColor(led_index, Color(0, 0, 255))
            self.strip.show()
            time.sleep(0.005)

        time.sleep(0.5)

        # Clear piano range
        for midi_note in range(self.PIANO_LOWEST_NOTE, self.PIANO_HIGHEST_NOTE + 1):
            led_index = self.midi_note_to_led(midi_note)
            self.strip.setPixelColor(led_index, Color(0, 0, 0))
            self.strip.show()
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
