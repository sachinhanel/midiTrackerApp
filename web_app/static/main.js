// Prefer websocket transport for lower latency when server supports it (eventlet). Polling remains as fallback.
const socket = io({transports: ['websocket', 'polling']});

let socketConnected = false;
socket.on('connect', () => {
  socketConnected = true;
  console.log('Socket.IO connected');
});
socket.on('disconnect', (reason) => {
  socketConnected = false;
  console.warn('Socket.IO disconnected:', reason);
});
socket.on('connect_error', (err) => {
  socketConnected = false;
  console.warn('Socket.IO connect_error', err);
});

socket.on('state_update', (data) => {
  console.debug('socket state_update', data);
  // Dashboard updates
  const an = document.getElementById('active_notes');
  if (an) an.textContent = data.active_notes && data.active_notes.length ? data.active_notes.join(' ') : '—';

  const tp = document.getElementById('throughput');
  if (tp) tp.textContent = (data.throughput || 0) + ' B/s';

  const pd = document.getElementById('pedal');
  if (pd) pd.textContent = data.pedal_pressed ? 'Down' : 'Up';

  const dbg = document.getElementById('debug');
  if (dbg) dbg.textContent = (data.debug_messages || []).slice(-100).join('\n');
  // update last-update indicator
  const lu = document.getElementById('last_update');
  if (lu) lu.textContent = new Date().toLocaleTimeString();
  const live = document.getElementById('live_status');
  if (live) { live.textContent = 'LIVE'; live.style.color = 'green'; }
  // auto-scroll debug to bottom
  if (dbg) { dbg.scrollTop = dbg.scrollHeight; }
});

socket.on('chord_update', (data) => {
  console.debug('socket chord_update', data);
  const cs = document.getElementById('chord_symbol');
  const notes = document.getElementById('chord_notes');
  const det = document.getElementById('chord_detail');
  if (cs && notes && det) {
    cs.textContent = data.symbol || '—';
    notes.textContent = data.notes && data.notes.length ? 'Notes: ' + data.notes.join(' ') : 'Notes: —';
    if (data.details) {
      det.textContent = `Root: ${data.details.root||'—'}  Bass: ${data.details.bass||'—'}  Quality: ${data.details.quality||'—'}  Inv: ${data.details.inversion||'—'}`;
    }
  }
});

// Polling fallback: if socket is not connected, fetch /api/state every 800ms
async function pollingFallback() {
  // Always poll as a robust fallback so pages update even if socket events are missed.
  try {
    const r = await fetch('/api/state');
    const j = await r.json();
    if (j.ok && j.state) {
      console.debug('polled state', j.state);
      // render directly
      const data = j.state;
      const an = document.getElementById('active_notes');
      if (an) an.textContent = data.active_notes && data.active_notes.length ? data.active_notes.join(' ') : '—';
      const tp = document.getElementById('throughput');
      if (tp) tp.textContent = (data.throughput || 0) + ' B/s';
      const pd = document.getElementById('pedal');
      if (pd) pd.textContent = data.pedal_pressed ? 'Down' : 'Up';
      const dbg = document.getElementById('debug');
      if (dbg) dbg.textContent = (data.debug_messages || []).slice(-100).join('\n');
      const lu = document.getElementById('last_update');
      if (lu) lu.textContent = new Date().toLocaleTimeString();
      const live = document.getElementById('live_status');
      if (live) { live.textContent = 'LIVE (poll)'; live.style.color = 'orange'; }
    }
  } catch (e) {
    // ignore
  }
}

// When we receive polled state, render it via same UI code
window.addEventListener('state_update_poll', (ev) => {
  const data = ev.data;
  const an = document.getElementById('active_notes');
  if (an) an.textContent = data.active_notes && data.active_notes.length ? data.active_notes.join(' ') : '—';
  const tp = document.getElementById('throughput');
  if (tp) tp.textContent = (data.throughput || 0) + ' B/s';
  const pd = document.getElementById('pedal');
  if (pd) pd.textContent = data.pedal_pressed ? 'Down' : 'Up';
  const dbg = document.getElementById('debug');
  if (dbg) dbg.textContent = (data.debug_messages || []).slice(-100).join('\n');
});

setInterval(pollingFallback, 250);

// Fetch daily stats on the statistics page
async function fetchDailyStats() {
  try {
    const res = await fetch('/api/stats/daily');
    const j = await res.json();
    if (!j.ok) return;
    const list = document.getElementById('daily_list');
    if (list) {
      list.innerHTML = '';
      j.data.forEach(d => {
        const el = document.createElement('div');
        el.className = 'stat_row';
        el.textContent = `${d.date}: notes=${d.total_notes} energy=${d.total_energy}`;
        list.appendChild(el);
      });
    }
    // simple chart render (canvas)
    const canvas = document.getElementById('energy_chart');
    if (canvas && j.data.length) {
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0,0,canvas.width, canvas.height);
      ctx.fillStyle = '#2b8cbe';
      const max = Math.max(...j.data.map(x => x.total_energy||0), 1);
      const w = canvas.width / j.data.length;
      j.data.reverse().forEach((d, i) => {
        const h = ((d.total_energy||0)/max) * canvas.height;
        ctx.fillRect(i*w, canvas.height-h, w*0.8, h);
      });
    }
  } catch (e) {
    console.error(e);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  fetchDailyStats();
});
