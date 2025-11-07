// LED Strip Control Interface

document.addEventListener('DOMContentLoaded', () => {
  const enableBtn = document.getElementById('led_enable_btn');
  const disableBtn = document.getElementById('led_disable_btn');
  const testBtn = document.getElementById('led_test_btn');
  const statusText = document.getElementById('led_status_text');
  const brightnessSlider = document.getElementById('brightness_slider');
  const brightnessValue = document.getElementById('brightness_value');
  const statusLedsToggle = document.getElementById('status_leds_toggle');

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
