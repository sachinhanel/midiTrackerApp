// Chart.js-based stats renderer
async function fetchStats(range){
  try{
    let url = '/api/stats/daily';
    if(range==='hourly') url = '/api/stats/hourly';
    if(range==='weekly') url = '/api/stats/weekly';
    if(range==='monthly') url = '/api/stats/monthly';
    if(range==='trends') url = '/api/stats/trends';
    const r = await fetch(url);
    const j = await r.json();
    if(!j.ok){
      console.error('stats fetch failed', j);
      throw new Error(j.error || 'stats fetch failed');
    }
    return j.data || [];
  }catch(e){ console.error(e); return []; }
}

async function fetchNoteDistribution(date){
  try{
    const url = '/api/note_distribution?date=' + encodeURIComponent(date);
    const r = await fetch(url);
    const j = await r.json();
    if(!j.ok){
      console.error('note distribution fetch failed', j);
      throw new Error(j.error || 'note distribution fetch failed');
    }
    return j;
  }catch(e){ console.error(e); return null; }
}

let statsChart = null;

// buildChart: renders a time-based Chart.js bar chart. `range` influences time unit (hour/day/week/month).
function buildChart(canvas, labels, values, label, range = 'daily'){
  if(!canvas) return;
  if(statsChart){ try{ statsChart.destroy(); }catch(_){ } statsChart = null; }
  const ctx = canvas.getContext('2d');
  const points = labels.map((l,i)=>({ x: l, y: values[i] }));
  let timeUnit = 'day';
  if(range === 'hourly') timeUnit = 'hour';
  else if(range === 'monthly') timeUnit = 'month';
  else if(range === 'weekly') timeUnit = 'week';

  try{
    statsChart = new Chart(ctx, {
      type: 'bar',
      data: { datasets: [{ label: label || '', data: points, backgroundColor: '#2b8cbe' }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { type: 'time', time: { parser: 'yyyy-MM-dd HH:mm', tooltipFormat: 'LLL dd HH:mm', unit: timeUnit }, ticks: { autoSkip: true } },
          y: { beginAtZero: true }
        },
        plugins: { legend: { display: false } }
      }
    });
  }catch(chartErr){
    console.error('chart render error', chartErr);
    // fallback: clear canvas and display text message
    try{
      ctx.clearRect(0,0,canvas.width,canvas.height);
      ctx.fillStyle = '#666';
      ctx.font = '14px sans-serif';
      ctx.textBaseline = 'top';
      ctx.fillText('Chart unavailable', 10, 10);
    }catch(_){/* ignore */}
  }
}

function renderSimpleTable(container, data){
  const el = document.getElementById(container);
  el.innerHTML = '';
  if(!data.length){ el.textContent = 'No data'; return; }
  const table = document.createElement('table');
  table.className = 'compact_table';
  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  Object.keys(data[0]).forEach(k=>{ const th = document.createElement('th'); th.textContent = k; headerRow.appendChild(th);});
  thead.appendChild(headerRow);
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  data.forEach(row=>{
    const tr = document.createElement('tr');
    Object.keys(row).forEach(k=>{ const td = document.createElement('td'); td.textContent = row[k]; tr.appendChild(td)});
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  el.appendChild(table);
}

function renderNoteDistributionTable(targetId, notes){
  const el = document.getElementById(targetId);
  el.innerHTML = '';
  // notes may be sparse (only present notes). We'll render full piano range 21..108 and merge data.
  const pianoMin = 21, pianoMax = 108;
  const noteMap = {};
  (notes || []).forEach(n => { noteMap[Number(n.midi_note)] = n; });

  // Build full notes array
  const full = [];
  let total_notes = 0;
  for(let m=pianoMin; m<=pianoMax; m++){
    const src = noteMap[m];
    const count = src ? (Number(src.count) || 0) : 0;
    const total_velocity = src ? (Number(src.total_velocity) || 0) : 0;
    const total_energy = src ? (Number(src.total_energy) || 0) : 0;
    const total_duration_ms = src ? (Number(src.total_duration_ms) || 0) : 0;
    full.push({ midi_note: m, note_name: (src && src.note_name) || null, count, total_velocity, total_energy, total_duration_ms });
    total_notes += count;
  }

  // Pagination controls
  const pageSize = 25;
  let currentPage = 0;
  const pages = Math.max(1, Math.ceil(full.length / pageSize));

  const tableWrapper = document.createElement('div');
  tableWrapper.className = 'note_table_wrapper';

  const table = document.createElement('table');
  table.className = 'note_dist_table';
  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  ['midi_note','note_name','count','percent','avg_velocity','total_energy','total_duration_ms'].forEach(h=>{ const th = document.createElement('th'); th.textContent = h; headerRow.appendChild(th);});
  thead.appendChild(headerRow);
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  table.appendChild(tbody);

  function renderPage(page){
    tbody.innerHTML = '';
    const start = page * pageSize;
    const end = Math.min(full.length, start + pageSize);
    for(let i=start;i<end;i++){
      const n = full[i];
      const tr = document.createElement('tr');
      function midiToName(m){
        const names = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
        const octave = Math.floor(m/12) - 1;
        return names[m % 12] + octave;
      }
  const noteName = n.note_name || midiToName(n.midi_note);
  const durFmt = formatDuration(n.total_duration_ms || 0);
  const pct = total_notes ? (n.count / total_notes * 100.0) : 0.0;
  const avg_velocity = n.count ? (n.total_velocity / n.count) : 0.0;
  const cells = [n.midi_note, noteName, round2(n.count), pct.toFixed(2) + '%', avg_velocity ? round2(avg_velocity) : '0.00', (n.total_energy||0).toFixed(2), durFmt];
      cells.forEach(c=>{ const td = document.createElement('td'); td.textContent = c; tr.appendChild(td); });
      tbody.appendChild(tr);
    }
  }

  // Pager
  const pager = document.createElement('div');
  pager.className = 'pager';
  const prevBtn = document.createElement('button'); prevBtn.textContent = 'Prev';
  const nextBtn = document.createElement('button'); nextBtn.textContent = 'Next';
  const pageLabel = document.createElement('span'); pageLabel.textContent = `Page ${currentPage+1} / ${pages}`;
  prevBtn.disabled = currentPage === 0;
  nextBtn.disabled = currentPage >= pages-1;
  prevBtn.addEventListener('click', ()=>{ if(currentPage>0){ currentPage--; renderPage(currentPage); pageLabel.textContent = `Page ${currentPage+1} / ${pages}`; prevBtn.disabled = currentPage===0; nextBtn.disabled = false; }});
  nextBtn.addEventListener('click', ()=>{ if(currentPage<pages-1){ currentPage++; renderPage(currentPage); pageLabel.textContent = `Page ${currentPage+1} / ${pages}`; nextBtn.disabled = currentPage>=pages-1; prevBtn.disabled = false; }});

  pager.appendChild(prevBtn); pager.appendChild(pageLabel); pager.appendChild(nextBtn);
  tableWrapper.appendChild(pager);
  tableWrapper.appendChild(table);
  el.appendChild(tableWrapper);
  renderPage(currentPage);
}

function formatBigNumber(v){
  if(v === null || v === undefined) return '-';
  if(v >= 1e6) return (v/1e6).toFixed(1)+'M';
  if(v >= 1e3) return (v/1e3).toFixed(1)+'k';
  return String(v);
}

async function updateStats(){
  try{
    const range = document.getElementById('range_select').value;
    const yKey = document.getElementById('y_select').value;
    const data = await fetchStats(range);

  // We'll build a time-series x axis depending on the range
  let labels = [];
  let values = [];

  if(range === 'hourly'){
    // 24 bins for today (hour 0..23)
    const today = new Date().toISOString().slice(0,10);
    const hourMap = {};
    data.forEach(d=>{ if(d.date === today && d.hour !== undefined) hourMap[Number(d.hour)] = Number(d[yKey]||0); });
    for(let h=0; h<24; h++){
      const hourLabel = `${today} ${String(h).padStart(2,'0')}:00`;
      labels.push(hourLabel);
      values.push(round2(hourMap[h] || 0));
    }
  } else if(range === 'daily'){
    // last 20 days (including today)
    const days = 20;
    const dayMap = {};
    data.forEach(d=>{ dayMap[d.date] = Number(d[yKey]||0); });
    for(let i=days-1;i>=0;i--){
      const dt = new Date();
      dt.setDate(dt.getDate() - i);
      const key = dt.toISOString().slice(0,10);
      labels.push(key + ' 00:00');
      values.push(round2(dayMap[key] || 0));
    }
  } else if(range === 'monthly'){
    // Prefer server-side monthly aggregation if present
    if(data.length && (data[0].month_key || data[0].month_start)){
      // server returned month_key/month_start and totals
  data.reverse();
  data.forEach(d=>{ labels.push((d.month_key || d.month_start) + '-01 00:00'); values.push(round2(Number(d.total_notes||0))); });
    } else {
      // fallback: aggregate daily rows client-side by month
      const monthMap = {};
      data.forEach(d=>{
        const m = d.date ? d.date.slice(0,7) : '';
        monthMap[m] = (monthMap[m] || 0) + Number(d[yKey]||0);
      });
      const now = new Date();
      for(let i=11;i>=0;i--){
        const m = new Date(now.getFullYear(), now.getMonth() - i, 1);
        const key = m.toISOString().slice(0,7);
        labels.push(key);
        values.push(round2(monthMap[key] || 0));
      }
    }
  } else if(range === 'weekly'){
    // server returns week_start and totals
  data.reverse(); // oldest first
  data.forEach(d=>{ labels.push((d.week_start || d.week_key) + ' 00:00'); values.push(round2(Number(d.total_notes||0))); });
  } else { // trends
  data.reverse();
  data.forEach(d=>{ labels.push((d.date||'') + ' 00:00'); values.push(round2(Number(d[yKey]||0))); });
  }

  const canvas = document.getElementById('stats_chart');
  buildChart(canvas, labels, values, yKey, range);
  // prepare a simplified table where numbers are rounded
  const normalized = data.map(d=>{
    const copy = Object.assign({}, d);
    Object.keys(copy).forEach(k=>{ if(typeof copy[k] === 'number') copy[k] = round2(copy[k]); });
    return copy;
  });
  renderSimpleTable('stats_table', normalized);
  }catch(e){
    console.error('updateStats error', e);
    const el = document.getElementById('stats_table'); if(el) el.textContent = 'Error loading stats: ' + (e && e.message ? e.message : String(e));
  }
}

function round2(v){
  if(v === null || v === undefined) return 0;
  return Math.round(Number(v) * 100) / 100;
}

async function updateNoteDistribution(){
  try{
    const el = document.getElementById('dist_date');
    let date = el.value;
    if(!date){ date = new Date().toISOString().slice(0,10); el.value = date; }
    const resp = await fetchNoteDistribution(date);
    if(!resp){ document.getElementById('note_distribution_table').textContent = 'No data'; return; }
  // update big totals
  const totals = resp.totals || {};
  document.getElementById('total_notes').textContent = formatBigNumber(totals.total_notes || 0);
  document.getElementById('total_energy').textContent = (totals.total_energy || 0).toFixed(2);
  document.getElementById('avg_velocity').textContent = (totals.avg_velocity || 0).toFixed(1);
  // populate small top totals too
  if(document.getElementById('total_notes_top')) document.getElementById('total_notes_top').textContent = formatBigNumber(totals.total_notes || 0);
  if(document.getElementById('total_energy_top')) document.getElementById('total_energy_top').textContent = (totals.total_energy || 0).toFixed(2);
  if(document.getElementById('avg_velocity_top')) document.getElementById('avg_velocity_top').textContent = (totals.avg_velocity || 0).toFixed(1);

  // render a small chart (notes x axis)
  const notes = resp.notes || [];
  const labels = notes.map(n=>n.note_name || n.midi_note);
  const values = notes.map(n=>n.count || 0);
  const canvas = document.getElementById('note_dist_canvas');
  if(!canvas){
    const container = document.createElement('div');
    container.style.height = '180px';
    const c = document.createElement('canvas');
    c.id = 'note_dist_canvas';
    container.appendChild(c);
    document.getElementById('note_distribution_table').insertBefore(container, document.getElementById('note_distribution_table').firstChild);
  }
  const c2 = document.getElementById('note_dist_canvas');
  buildChart(c2, labels, values, 'Note counts');

  renderNoteDistributionTable('note_distribution_table', notes);
  }catch(e){
    console.error('updateNoteDistribution error', e);
    const el = document.getElementById('note_distribution_table'); if(el) el.textContent = 'Error loading note distribution';
  }
}

// Fetch and display all-time totals at top (from server)
async function fetchAllTotals(){
  try{
    const r = await fetch('/api/stats/all_totals');
    const j = await r.json();
    if(!j.ok) return;
    const t = j.totals || {};
    if(document.getElementById('total_notes_top')) document.getElementById('total_notes_top').textContent = formatBigNumber(t.total_notes || 0);
    if(document.getElementById('total_energy_top')) document.getElementById('total_energy_top').textContent = (t.total_energy || 0).toFixed(2);
    if(document.getElementById('total_note_hours_top')) document.getElementById('total_note_hours_top').textContent = (t.total_note_duration_hours || 0).toFixed(1);
    if(document.getElementById('total_practice_hours_top')) document.getElementById('total_practice_hours_top').textContent = (t.total_practice_hours || 0).toFixed(1);
    if(document.getElementById('total_pedal_presses_top')) document.getElementById('total_pedal_presses_top').textContent = (t.total_pedal_presses || 0);
    if(document.getElementById('total_midi_mb_top')) document.getElementById('total_midi_mb_top').textContent = (t.total_midi_mb || 0).toFixed(2);
  }catch(e){ console.error(e); }
}

function formatDuration(ms){
  if(!ms) return '0s';
  const s = Math.round(ms/1000);
  if(s < 60) return `${s}s`;
  if(s < 3600) return `${Math.round(s/60)}m`;
  return `${Math.round(s/3600)}h`;
}

function formatHMS(seconds){
  const s = Math.max(0, Math.floor(Number(seconds) || 0));
  const hh = Math.floor(s / 3600);
  const mm = Math.floor((s % 3600) / 60);
  const ss = s % 60;
  return `${String(hh).padStart(2,'0')}:${String(mm).padStart(2,'0')}:${String(ss).padStart(2,'0')}`;
}

document.addEventListener('DOMContentLoaded', ()=>{
  document.getElementById('range_select').addEventListener('change', ()=>{ updateStats(); updateHeatmap(); });
  document.getElementById('y_select').value = 'total_notes'; // default to total_notes
  document.getElementById('y_select').addEventListener('change', updateStats);
  document.getElementById('dist_date').addEventListener('change', updateNoteDistribution);
  document.getElementById('heatmap_refresh').addEventListener('click', updateHeatmap);
  // load totals and data, protective try/catch to avoid leaving Loading...
  fetchAllTotals().catch(e=>console.error(e));
  updateStats().catch(e=>console.error(e));
  updateNoteDistribution().catch(e=>console.error(e));
  updateHeatmap().catch(e=>console.error(e));

  // Prev/Next date navigation for note distribution
  const prevBtn = document.getElementById('dist_prev');
  const nextBtn = document.getElementById('dist_next');
  const dateInput = document.getElementById('dist_date');
  function shiftDate(days){
    let d = dateInput.value ? new Date(dateInput.value) : new Date();
    d.setDate(d.getDate() + days);
    const s = d.toISOString().slice(0,10);
    dateInput.value = s;
    // refresh both the table and heatmap immediately
    updateNoteDistribution().catch(e=>console.error(e));
    updateHeatmap().catch(e=>console.error(e));
  }
  prevBtn.addEventListener('click', ()=> shiftDate(-1));
  nextBtn.addEventListener('click', ()=> shiftDate(1));
  // auto-refresh heatmap when date changes
  dateInput.addEventListener('change', ()=>{ updateHeatmap().catch(e=>console.error(e)); updateNoteDistribution().catch(e=>console.error(e)); });
});

// Heatmap piano rendering
async function updateHeatmap(){
  try{
    const range = document.getElementById('range_select').value;
    const date = document.getElementById('dist_date').value || new Date().toISOString().slice(0,10);
    const url = `/api/heatmap_distribution?range=${encodeURIComponent(range)}&date=${encodeURIComponent(date)}`;
    const r = await fetch(url);
    const j = await r.json();
    if(!j.ok){ console.error('heatmap fetch failed', j); return; }
    const counts = {};
    (j.notes || []).forEach(n=>{ counts[Number(n.midi_note)] = Number(n.count||0); });
    renderPianoHeatmap('heatmap_piano', counts);
    // legend
    const legend = document.getElementById('heatmap_legend');
    legend.innerHTML = `<div>Range: ${range}</div><div>Total notes: ${j.totals ? j.totals.total_notes : '-'}</div>`;
  }catch(e){ console.error('updateHeatmap error', e); }
}

function renderPianoHeatmap(canvasId, counts){
  const canvas = document.getElementById(canvasId);
  if(!canvas) return;
  const ctx = canvas.getContext('2d');
  const midiMin = 21, midiMax = 108;
  const totalKeys = midiMax - midiMin + 1;
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0,0,width,height);

  // compute max for normalization
  let maxCount = 0;
  for(let k=midiMin;k<=midiMax;k++) maxCount = Math.max(maxCount, counts[k]||0);
  if(maxCount === 0) maxCount = 1;

  // draw white keys as equal-width rectangles; small piano mockup, 88 keys
  const keyWidth = width / totalKeys;
  for(let i=0;i<totalKeys;i++){
    const midi = midiMin + i;
    const c = counts[midi] || 0;
    const intensity = c / maxCount;
    // color from light gray to blue
    const blue = Math.round(80 + intensity * 175);
    const alpha = 0.2 + intensity * 0.8;
    ctx.fillStyle = `rgba(43,140,190,${alpha.toFixed(2)})`;
    ctx.fillRect(i * keyWidth, 0, Math.ceil(keyWidth), height * 0.7);
    // draw key border
    ctx.strokeStyle = '#ddd';
    ctx.strokeRect(i * keyWidth, 0, Math.ceil(keyWidth), height * 0.7);
  }

  // draw black key overlays
  const blackSet = [1,3,6,8,10];
  for(let i=0;i<totalKeys;i++){
    const midi = midiMin + i;
    const noteInOctave = midi % 12;
    if(blackSet.includes(noteInOctave)){
      const c = counts[midi] || 0;
      const intensity = c / maxCount;
      const alpha = 0.15 + intensity * 0.85;
      const bw = Math.ceil(keyWidth * 0.6);
      ctx.fillStyle = `rgba(0,0,0,${alpha.toFixed(2)})`;
      ctx.fillRect(i * keyWidth + keyWidth*0.7, 0, bw, height * 0.45);
    }
  }

  // draw small counts under each key (rotated for space)
  ctx.save();
  ctx.fillStyle = '#333';
  ctx.font = '10px sans-serif';
  ctx.textAlign = 'center';
  for(let i=0;i<totalKeys;i++){
    const midi = midiMin + i;
    const c = counts[midi] || 0;
    const x = i * keyWidth + keyWidth/2;
    const y = height * 0.78;
    // draw rotated small text (vertical)
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(-Math.PI/2);
    ctx.fillText(String(c), 0, 0);
    ctx.restore();
  }
  ctx.restore();

  // Tooltip handling
  const tooltip = document.getElementById('heatmap_tooltip');
  canvas.onmousemove = function(ev){
    const rect = canvas.getBoundingClientRect();
    const px = ev.clientX - rect.left;
    const keyIndex = Math.floor(px / keyWidth);
    if(keyIndex < 0 || keyIndex >= totalKeys){ tooltip.style.display = 'none'; return; }
    const midi = midiMin + keyIndex;
    const count = counts[midi] || 0;
    const noteNames = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
    const name = noteNames[midi % 12] + (Math.floor(midi/12)-1);
    tooltip.style.display = 'block';
    tooltip.textContent = `${name}: ${count}`;
    // Position tooltip centered horizontally over the key and slightly above the piano
    const left = rect.left + keyIndex * keyWidth + keyWidth/2;
    const top = rect.top + height * 0.65;
    // Place using page coordinates but keep tooltip within the heatmap container bounds if possible
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
  };
  canvas.onmouseout = function(){ const t = document.getElementById('heatmap_tooltip'); if(t) t.style.display = 'none'; };
}
