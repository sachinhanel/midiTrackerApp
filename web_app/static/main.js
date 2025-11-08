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

  // Update live piano visualization - combine active_notes and sustained_notes
  const allNotes = [...(data.active_notes || []), ...(data.sustained_notes || [])];
  renderLivePiano(allNotes);
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
      // Update live piano visualization - combine active_notes and sustained_notes
      const allNotes = [...(data.active_notes || []), ...(data.sustained_notes || [])];
      renderLivePiano(allNotes);
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

// Live piano heatmap rendering
function renderLivePiano(activeNotes){
  const canvas = document.getElementById('live_piano_canvas');
  if(!canvas) return;
  const ctx = canvas.getContext('2d');
  const midiMin = 21, midiMax = 108;
  const totalKeys = midiMax - midiMin + 1;
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0,0,width,height);

  // Parse active notes if they're strings (e.g., "C4", "D#5")
  const activeSet = new Set();
  if(activeNotes && activeNotes.length){
    activeNotes.forEach(note => {
      // If note is already a MIDI number, use it directly
      if(typeof note === 'number'){
        activeSet.add(note);
      } else {
        // Convert note name to MIDI number
        const midiNum = noteNameToMidi(note);
        if(midiNum !== null) activeSet.add(midiNum);
      }
    });
  }

  // Helper to check if a MIDI note is a black key
  function isBlackKey(midi){
    const noteInOctave = midi % 12;
    // Black keys: C#(1), D#(3), F#(6), G#(8), A#(10)
    return [1,3,6,8,10].includes(noteInOctave);
  }

  // Count white keys to calculate proper spacing
  let whiteKeyCount = 0;
  for(let i=0;i<totalKeys;i++){
    if(!isBlackKey(midiMin + i)) whiteKeyCount++;
  }
  const whiteKeyWidth = width / whiteKeyCount;

  // Draw all white keys first
  let whiteKeyIndex = 0;
  for(let i=0;i<totalKeys;i++){
    const midi = midiMin + i;
    const isActive = activeSet.has(midi);

    // Only draw white keys in this pass
    if(!isBlackKey(midi)){
      if(isActive){
        ctx.fillStyle = 'rgba(255,215,0,0.9)'; // Bright gold for active notes
      } else {
        ctx.fillStyle = 'rgba(240,240,240,0.5)'; // Light gray for inactive
      }
      ctx.fillRect(whiteKeyIndex * whiteKeyWidth, 0, Math.ceil(whiteKeyWidth), height * 0.7);

      // Draw key border
      ctx.strokeStyle = '#999';
      ctx.strokeRect(whiteKeyIndex * whiteKeyWidth, 0, Math.ceil(whiteKeyWidth), height * 0.7);

      whiteKeyIndex++;
    }
  }

  // Draw black keys on top, positioned between white keys
  whiteKeyIndex = 0;
  for(let i=0;i<totalKeys;i++){
    const midi = midiMin + i;

    if(!isBlackKey(midi)){
      whiteKeyIndex++;
    } else {
      // Black key positioned at the boundary between white keys
      const isActive = activeSet.has(midi);
      const blackKeyWidth = whiteKeyWidth * 0.6;
      const xPos = whiteKeyIndex * whiteKeyWidth - blackKeyWidth / 2;

      if(isActive){
        ctx.fillStyle = 'rgba(255,140,0,0.95)'; // Bright orange for active black keys
      } else {
        ctx.fillStyle = 'rgba(30,30,30,0.8)'; // Dark gray for inactive black keys
      }
      ctx.fillRect(xPos, 0, blackKeyWidth, height * 0.45);

      // Draw border for black keys
      ctx.strokeStyle = '#000';
      ctx.strokeRect(xPos, 0, blackKeyWidth, height * 0.45);
    }
  }

  // Tooltip handling
  const tooltip = document.getElementById('live_piano_tooltip');
  if(tooltip){
    canvas.onmousemove = function(ev){
      const rect = canvas.getBoundingClientRect();
      const px = ev.clientX - rect.left;

      // Find which key is under the mouse (check black keys first, then white keys)
      let hoveredMidi = null;
      let tooltipX = px;

      // Check black keys first (they're on top)
      let whiteIdx = 0;
      for(let i=0;i<totalKeys;i++){
        const midi = midiMin + i;
        if(!isBlackKey(midi)){
          whiteIdx++;
        } else {
          const blackKeyWidth = whiteKeyWidth * 0.6;
          const xPos = whiteIdx * whiteKeyWidth - blackKeyWidth / 2;
          if(px >= xPos && px < xPos + blackKeyWidth){
            hoveredMidi = midi;
            tooltipX = xPos + blackKeyWidth / 2;
            break;
          }
        }
      }

      // If no black key, check white keys
      if(hoveredMidi === null){
        const whiteKeyIdx = Math.floor(px / whiteKeyWidth);
        if(whiteKeyIdx >= 0 && whiteKeyIdx < whiteKeyCount){
          // Find the corresponding MIDI note for this white key
          let whiteCount = 0;
          for(let i=0;i<totalKeys;i++){
            const midi = midiMin + i;
            if(!isBlackKey(midi)){
              if(whiteCount === whiteKeyIdx){
                hoveredMidi = midi;
                tooltipX = whiteKeyIdx * whiteKeyWidth + whiteKeyWidth / 2;
                break;
              }
              whiteCount++;
            }
          }
        }
      }

      if(hoveredMidi !== null){
        const noteNames = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
        const name = noteNames[hoveredMidi % 12] + (Math.floor(hoveredMidi/12)-1);
        const isActive = activeSet.has(hoveredMidi);
        tooltip.style.display = 'block';
        tooltip.textContent = `${name}${isActive ? ' (ACTIVE)' : ''}`;
        tooltip.style.left = `${rect.left + tooltipX}px`;
        tooltip.style.top = `${rect.top + height * 0.65}px`;
      } else {
        tooltip.style.display = 'none';
      }
    };
    canvas.onmouseout = function(){ if(tooltip) tooltip.style.display = 'none'; };
  }
}

// Helper function to convert note name (e.g., "C4", "D#5") to MIDI number
function noteNameToMidi(noteName){
  if(!noteName || typeof noteName !== 'string') return null;
  const noteMap = {C:0, 'C#':1, D:2, 'D#':3, E:4, F:5, 'F#':6, G:7, 'G#':8, A:9, 'A#':10, B:11};
  // Parse note name (e.g., "C4", "D#5", "Bb3")
  const match = noteName.match(/^([A-G][#b]?)(-?\d+)$/);
  if(!match) return null;
  let note = match[1];
  const octave = parseInt(match[2]);
  // Handle flats (convert to sharps)
  if(note.includes('b')){
    const flatMap = {Db:'C#', Eb:'D#', Gb:'F#', Ab:'G#', Bb:'A#'};
    note = flatMap[note] || note;
  }
  if(!(note in noteMap)) return null;
  return (octave + 1) * 12 + noteMap[note];
}

// Initialize live piano with empty state on page load
document.addEventListener('DOMContentLoaded', () => {
  renderLivePiano([]);
});

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
