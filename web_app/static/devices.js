async function fetchDevices() {
  try {
  const r = await fetch('/api/control/devices');
    const j = await r.json();
    const list = document.getElementById('device_list');
    const sel = document.getElementById('device_select');
    list.innerHTML = '';
    sel.innerHTML = '';
    if (j.ok) {
      j.devices.forEach((d, i) => {
        const li = document.createElement('li');
        li.textContent = `${i}: ${d}`;
        list.appendChild(li);
        const opt = document.createElement('option');
        opt.value = i;
        opt.textContent = d;
        sel.appendChild(opt);
      });
    } else {
      list.innerHTML = '<li>Error fetching devices</li>';
    }
  } catch (e) {
    console.error(e);
    const list = document.getElementById('device_list');
    list.innerHTML = '<li>Control API unreachable (is the main app running?)</li>';
  }
}

async function selectDevice() {
  const sel = document.getElementById('device_select');
  const idx = sel.value;
  try {
    const r = await fetch('/api/control/select', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({index: parseInt(idx)})
    });
    const j = await r.json();
    const status = document.getElementById('device_status');
    if (j.ok) status.textContent = 'Select request submitted'; else status.textContent = 'Error: '+(j.error||'unknown');
  } catch (e) {
    console.error(e);
    document.getElementById('device_status').textContent = 'Error contacting control API';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('refresh_devices').addEventListener('click', fetchDevices);
  document.getElementById('select_btn').addEventListener('click', selectDevice);
  fetchDevices();
});
