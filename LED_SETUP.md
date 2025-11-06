# LED Strip Setup Guide

## Hardware Requirements

- **LED Strip**: WS2812B (NeoPixel) strip with 144 LEDs
- **Raspberry Pi 5**
- **5V Power Supply**: For the LED strip (separate from Pi power)
  - Calculate: 144 LEDs × 60mA (max per LED) = 8.64A at 5V
  - Recommended: 5V 10A power supply
- **Logic Level Shifter** (recommended): 3.3V to 5V
- **Wires**: For connections

## Wiring Diagram

```
Raspberry Pi 5                    WS2812B LED Strip
┌─────────────┐                  ┌──────────────┐
│             │                  │              │
│  GPIO 18 ───┼──────[330Ω]─────┤ DIN (Data)   │
│  (PWM0)     │                  │              │
│             │                  │              │
│  GND     ───┼──────────────────┤ GND          │
│             │                  │              │
└─────────────┘                  │              │
                                 │ 5V        ───┤  5V Power Supply (+)
                                 └──────────────┘
                                       GND    ───   5V Power Supply (-)
```

### Connections

1. **Data Line (DIN)**:
   - Pi GPIO 18 → 330Ω resistor → LED Strip DIN
   - The resistor protects the first LED

2. **Ground**:
   - Pi GND → LED Strip GND
   - LED Strip GND → 5V Power Supply GND
   - **Important**: Common ground between Pi and LED strip power supply

3. **Power (5V)**:
   - **DO NOT** power the strip from the Pi!
   - Use a separate 5V power supply connected to the LED strip's 5V and GND lines
   - Connect power supply ground to Pi ground (common ground)

### Optional: Logic Level Shifter

For better signal reliability, add a 3.3V to 5V logic level shifter between GPIO 18 and the LED strip:

```
Pi GPIO 18 (3.3V) → Level Shifter LV → HV → LED Strip DIN (5V)
```

## Software Installation

### 1. Install Required Library

The LED controller uses the `rpi_ws281x` library:

```bash
sudo pip3 install rpi_ws281x
```

### 2. Enable PWM on GPIO 18

GPIO 18 supports hardware PWM, which is required for WS2812B strips.

Edit `/boot/firmware/config.txt`:
```bash
sudo nano /boot/firmware/config.txt
```

Add or ensure these lines are present:
```
# Enable PWM audio (enables PWM on GPIO 18)
dtparam=audio=on
```

Reboot:
```bash
sudo reboot
```

### 3. Run with Sudo

The LED controller requires sudo for GPIO access:

```bash
sudo systemctl restart midi-main.service
sudo systemctl restart midi-web.service
```

## LED Mapping

- **Total LEDs**: 144
- **Piano Keys**: 88
- **LED Range**: LEDs 56-143 (88 LEDs)
- **Status LEDs**: LEDs 0-4 (green when program is running)

### Note-to-LED Mapping

| Piano Key | MIDI Note | LED Index |
|-----------|-----------|-----------|
| A0 (lowest) | 21 | 143 |
| C4 (middle C) | 60 | 104 |
| C8 (highest) | 108 | 56 |

**Formula**: `LED_Index = 143 - (MIDI_Note - 21)`

## Web Interface Usage

1. Navigate to the "Heatmap" tab (now renamed to "LED Strip Control")
2. Click **"Enable LED Visualization"** to start
3. Play piano keys - they will light up blue on the LED strip
4. Click **"Disable LED Visualization"** to stop
5. Click **"Run Test Pattern"** to verify wiring

## Troubleshooting

### LEDs don't light up

1. **Check power**: Ensure 5V power supply is connected and sufficient (10A recommended)
2. **Check wiring**: Verify DIN, GND, and 5V connections
3. **Check permissions**: Make sure the service is running with sudo
4. **Check library**: Run `sudo pip3 show rpi_ws281x`

### LEDs flicker or show wrong colors

1. **Add capacitor**: 1000µF capacitor across 5V and GND near the LED strip
2. **Check ground**: Ensure common ground between Pi and power supply
3. **Check data line**: Add 330Ω resistor if not present
4. **Try level shifter**: Use 3.3V to 5V logic level shifter

### Permission errors

```bash
# Make sure services run as root
sudo systemctl restart midi-main.service
sudo systemctl restart midi-web.service
```

### Test the LED strip independently

```bash
cd /home/sachin/git/midiTrackerApp
sudo python3 led_controller.py
```

This will run a test pattern showing if the hardware is working.

## Configuration

To change GPIO pin or LED count, edit `led_controller.py`:

```python
LED_COUNT = 144          # Total number of LEDs
LED_PIN = 18             # GPIO pin (must support PWM!)
LED_BRIGHTNESS = 128     # 0-255 (128 = 50%)
```

## Safety Notes

- Never connect 5V directly to Pi GPIO pins
- Use appropriate gauge wire for LED strip power (18-20 AWG for 10A)
- Keep power supply well-ventilated
- Double-check polarity before powering on
- Start with low brightness and increase gradually

## References

- [rpi_ws281x Library](https://github.com/jgarff/rpi_ws281x)
- [Adafruit NeoPixel Guide](https://learn.adafruit.com/adafruit-neopixel-uberguide)
- [Raspberry Pi GPIO Pinout](https://pinout.xyz/pinout/pin12_gpio18)
