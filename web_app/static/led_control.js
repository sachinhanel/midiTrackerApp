// LED Strip Control Interface

document.addEventListener('DOMContentLoaded', () => {
  const enableBtn = document.getElementById('led_enable_btn');
  const disableBtn = document.getElementById('led_disable_btn');
  const testBtn = document.getElementById('led_test_btn');
  const statusText = document.getElementById('led_status_text');
  const brightnessSlider = document.getElementById('brightness_slider');
  const brightnessValue = document.getElementById('brightness_value');
  const backgroundBrightnessSlider = document.getElementById('background_brightness_slider');
  const backgroundBrightnessValue = document.getElementById('background_brightness_value');
  const statusLedsToggle = document.getElementById('status_leds_toggle');

  // Color preset elements
  const noteColorEnabled = document.getElementById('note_color_enabled');
  const noteColorPicker = document.getElementById('note_color_picker');
  const noteColorValue = document.getElementById('note_color_value');
  const backgroundColorEnabled = document.getElementById('background_color_enabled');
  const backgroundColorPicker = document.getElementById('background_color_picker');
  const backgroundColorValue = document.getElementById('background_color_value');
  const sustainPedalHold = document.getElementById('sustain_pedal_hold');
  const doubleLedMode = document.getElementById('double_led_mode');
  const applyPresetBtn = document.getElementById('apply_preset_btn');
  const savePresetBtn = document.getElementById('save_preset_btn');
  const loadPresetBtn = document.getElementById('load_preset_btn');

  // Effect controls
  const effectModeSelect = document.getElementById('effect_mode');
  const velocityBrightnessCheckbox = document.getElementById('velocity_brightness');
  const fadeDurationSlider = document.getElementById('fade_duration_slider');
  const fadeDurationValue = document.getElementById('fade_duration_value');
  const sustainThresholdSlider = document.getElementById('sustain_threshold_slider');
  const sustainThresholdValue = document.getElementById('sustain_threshold_value');
  const sparkleIntensitySlider = document.getElementById('sparkle_intensity_slider');
  const sparkleIntensityValue = document.getElementById('sparkle_intensity_value');
  const applyEffectsBtn = document.getElementById('apply_effects_btn');

  // Get initial effect settings
  fetch('/api/led/effects')
    .then(r => r.json())
    .then(data => {
      if (data.ok) {
        if (effectModeSelect) effectModeSelect.value = data.effect_mode || 'static';
        if (velocityBrightnessCheckbox) velocityBrightnessCheckbox.checked = data.velocity_brightness || false;
        if (fadeDurationSlider) {
          fadeDurationSlider.value = data.fade_duration_ms || 1000;
          fadeDurationValue.textContent = `${data.fade_duration_ms || 1000}ms`;
        }
        if (sustainThresholdSlider) {
          const thresholdPct = Math.round((data.sustain_fade_threshold || 0.3) * 100);
          sustainThresholdSlider.value = thresholdPct;
          sustainThresholdValue.textContent = `${thresholdPct}%`;
        }
        if (sparkleIntensitySlider) {
          const sparklePct = Math.round((data.sparkle_intensity || 0.2) * 100);
          sparkleIntensitySlider.value = sparklePct;
          sparkleIntensityValue.textContent = `${sparklePct}%`;
        }
      }
    })
    .catch(e => {
      console.error('Error getting effect settings:', e);
    });

  // Get initial double LED mode status
  fetch('/api/led/double_mode')
    .then(r => r.json())
    .then(data => {
      if (data.ok && doubleLedMode) {
        doubleLedMode.checked = data.double_led_mode;
      }
    })
    .catch(e => {
      console.error('Error getting double LED mode status:', e);
    });

  // Get initial status
  fetch('/api/led/status')
    .then(r => r.json())
    .then(data => {
      updateStatus(data.enabled);
    })
    .catch(e => {
      console.error('Error getting LED status:', e);
      statusText.textContent = 'Error';
      statusText.style.color = 'red';
    });

  // Enable button
  enableBtn.addEventListener('click', async () => {
    try {
      const response = await fetch('/api/led/enable', { method: 'POST' });
      const data = await response.json();
      if (data.ok) {
        updateStatus(true);
        alert('LED visualization enabled!');
      } else {
        alert('Failed to enable LED: ' + (data.error || 'Unknown error'));
      }
    } catch (e) {
      console.error('Error enabling LED:', e);
      alert('Error enabling LED visualization');
    }
  });

  // Disable button
  disableBtn.addEventListener('click', async () => {
    try {
      const response = await fetch('/api/led/disable', { method: 'POST' });
      const data = await response.json();
      if (data.ok) {
        updateStatus(false);
        alert('LED visualization disabled');
      } else {
        alert('Failed to disable LED: ' + (data.error || 'Unknown error'));
      }
    } catch (e) {
      console.error('Error disabling LED:', e);
      alert('Error disabling LED visualization');
    }
  });

  // Test button
  testBtn.addEventListener('click', async () => {
    try {
      statusText.textContent = 'Running test...';
      statusText.style.color = 'orange';

      const response = await fetch('/api/led/test', { method: 'POST' });
      const data = await response.json();

      if (data.ok) {
        alert('Test pattern completed!');
        // Refresh status
        const statusResponse = await fetch('/api/led/status');
        const statusData = await statusResponse.json();
        updateStatus(statusData.enabled);
      } else {
        alert('Failed to run test: ' + (data.error || 'Unknown error'));
        updateStatus(false);
      }
    } catch (e) {
      console.error('Error running test:', e);
      alert('Error running test pattern');
      statusText.textContent = 'Error';
      statusText.style.color = 'red';
    }
  });

  // Brightness slider
  brightnessSlider.addEventListener('input', async () => {
    const value = brightnessSlider.value;
    const percentage = Math.round((value / 255) * 100);
    brightnessValue.textContent = `${percentage}%`;

    try {
      await fetch('/api/led/brightness', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ brightness: parseInt(value) })
      });
    } catch (e) {
      console.error('Error setting brightness:', e);
    }
  });

  // Background brightness slider
  backgroundBrightnessSlider.addEventListener('input', () => {
    const value = backgroundBrightnessSlider.value;
    backgroundBrightnessValue.textContent = `${value}%`;
    // Background brightness is applied when preset is applied, not immediately
  });

  // Status LEDs toggle
  statusLedsToggle.addEventListener('click', async () => {
    try {
      const response = await fetch('/api/led/status_leds/toggle', { method: 'POST' });
      const data = await response.json();
      if (!data.ok) {
        alert('Failed to toggle status LEDs: ' + (data.error || 'Unknown error'));
      }
    } catch (e) {
      console.error('Error toggling status LEDs:', e);
      alert('Error toggling status LEDs');
    }
  });

  // Double LED mode toggle
  doubleLedMode.addEventListener('change', async () => {
    try {
      const response = await fetch('/api/led/double_mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: doubleLedMode.checked })
      });
      const data = await response.json();
      if (data.ok) {
        const modeText = doubleLedMode.checked ?
          'Double LED Mode (2 LEDs per key, 72 keys)' :
          'Single LED Mode (1 LED per key, 88 keys)';
        console.log('LED mode changed to:', modeText);
      } else {
        alert('Failed to set double LED mode: ' + (data.error || 'Unknown error'));
        // Revert checkbox on failure
        doubleLedMode.checked = !doubleLedMode.checked;
      }
    } catch (e) {
      console.error('Error setting double LED mode:', e);
      alert('Error setting double LED mode');
      // Revert checkbox on error
      doubleLedMode.checked = !doubleLedMode.checked;
    }
  });

  // Effect slider live updates
  fadeDurationSlider.addEventListener('input', () => {
    fadeDurationValue.textContent = `${fadeDurationSlider.value}ms`;
  });

  sustainThresholdSlider.addEventListener('input', () => {
    sustainThresholdValue.textContent = `${sustainThresholdSlider.value}%`;
  });

  sparkleIntensitySlider.addEventListener('input', () => {
    sparkleIntensityValue.textContent = `${sparkleIntensitySlider.value}%`;
  });

  // Apply effects button
  applyEffectsBtn.addEventListener('click', async () => {
    try {
      const effectSettings = {
        effect_mode: effectModeSelect.value,
        velocity_brightness: velocityBrightnessCheckbox.checked,
        fade_duration_ms: parseInt(fadeDurationSlider.value),
        sustain_fade_threshold: parseInt(sustainThresholdSlider.value) / 100.0,
        sparkle_intensity: parseInt(sparkleIntensitySlider.value) / 100.0
      };

      const response = await fetch('/api/led/effects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(effectSettings)
      });

      const data = await response.json();
      if (data.ok) {
        console.log('Effect settings applied:', data);
        alert('Effect settings applied successfully!');
      } else {
        alert('Failed to apply effects: ' + (data.error || 'Unknown error'));
      }
    } catch (e) {
      console.error('Error applying effects:', e);
      alert('Error applying effect settings');
    }
  });

  // Helper function to convert hex color to RGB
  function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
      r: parseInt(result[1], 16),
      g: parseInt(result[2], 16),
      b: parseInt(result[3], 16)
    } : null;
  }

  // Helper function to update color value display
  function updateColorDisplay(colorPicker, colorValue) {
    const hex = colorPicker.value.toUpperCase();
    const rgb = hexToRgb(hex);
    if (rgb) {
      colorValue.textContent = `${hex} (R:${rgb.r} G:${rgb.g} B:${rgb.b})`;
    }
  }

  // Note color picker change
  noteColorPicker.addEventListener('input', () => {
    updateColorDisplay(noteColorPicker, noteColorValue);
  });

  // Background color picker change
  backgroundColorPicker.addEventListener('input', () => {
    updateColorDisplay(backgroundColorPicker, backgroundColorValue);
  });

  // Apply preset button
  applyPresetBtn.addEventListener('click', async () => {
    try {
      const noteColor = noteColorEnabled.checked ? hexToRgb(noteColorPicker.value) : null;
      const backgroundColorFull = backgroundColorEnabled.checked ? hexToRgb(backgroundColorPicker.value) : null;
      const backgroundBrightnessPct = parseInt(backgroundBrightnessSlider.value);

      // Apply background brightness scaling if background color is enabled
      let backgroundColor = null;
      if (backgroundColorFull && backgroundColorEnabled.checked) {
        const bgBrightness = backgroundBrightnessPct / 100;
        backgroundColor = {
          r: Math.round(backgroundColorFull.r * bgBrightness),
          g: Math.round(backgroundColorFull.g * bgBrightness),
          b: Math.round(backgroundColorFull.b * bgBrightness)
        };
      }

      const preset = {
        note_color: noteColor,
        background_color: backgroundColor,
        background_color_full: backgroundColorFull,
        background_brightness: backgroundBrightnessPct,
        sustain_pedal_hold: sustainPedalHold.checked
      };

      const response = await fetch('/api/led/preset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(preset)
      });

      const data = await response.json();
      if (data.ok) {
        alert('Color preset applied successfully!');
      } else {
        alert('Failed to apply preset: ' + (data.error || 'Unknown error'));
      }
    } catch (e) {
      console.error('Error applying preset:', e);
      alert('Error applying color preset');
    }
  });

  // Save preset button
  savePresetBtn.addEventListener('click', async () => {
    try {
      const response = await fetch('/api/led/preset/save', {
        method: 'POST'
      });

      const data = await response.json();
      if (data.ok) {
        alert('Preset saved successfully! It will be loaded automatically on next boot.');
      } else {
        alert('Failed to save preset: ' + (data.error || 'Unknown error'));
      }
    } catch (e) {
      console.error('Error saving preset:', e);
      alert('Error saving preset');
    }
  });

  // Load preset button
  loadPresetBtn.addEventListener('click', async () => {
    try {
      const response = await fetch('/api/led/preset/load', {
        method: 'POST'
      });

      const data = await response.json();
      if (data.ok) {
        alert('Preset loaded successfully!');
        // Optionally reload the page to show updated values
        setTimeout(() => window.location.reload(), 500);
      } else {
        alert('Failed to load preset: ' + (data.error || 'Preset file not found'));
      }
    } catch (e) {
      console.error('Error loading preset:', e);
      alert('Error loading preset');
    }
  });

  function updateStatus(enabled) {
    if (enabled) {
      statusText.textContent = 'Enabled (Active)';
      statusText.style.color = 'green';
      enableBtn.disabled = true;
      disableBtn.disabled = false;
    } else {
      statusText.textContent = 'Disabled';
      statusText.style.color = 'gray';
      enableBtn.disabled = false;
      disableBtn.disabled = true;
    }
  }
});
