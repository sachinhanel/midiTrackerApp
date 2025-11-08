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
let noteDistChart = null;

// buildChart: renders a time-based Chart.js bar chart. `range` influences time unit (hour/day/week/month).
function buildChart(canvas, labels, values, label, range = 'daily'){
  if(!canvas){ console.error('buildChart: canvas is null'); return; }

  // Determine which chart to manage based on canvas ID
  const isMainChart = canvas.id === 'stats_chart';
  const chartRef = isMainChart ? statsChart : noteDistChart;

  // Destroy the appropriate existing chart
  if(chartRef){ try{ chartRef.destroy(); }catch(e){ console.error('Chart destroy error:', e); } }

  const ctx = canvas.getContext('2d');
  const points = labels.map((l,i)=>({ x: l, y: values[i] }));
  let timeUnit = 'day';
  if(range === 'hourly') timeUnit = 'hour';
  else if(range === 'monthly') timeUnit = 'month';
  else if(range === 'weekly') timeUnit = 'week';

  console.log(`buildChart: range=${range}, timeUnit=${timeUnit}, points=${points.length}, label=${label}`);

  try{
    const newChart = new Chart(ctx, {
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

    // Assign to the appropriate global variable
    if(isMainChart){
      statsChart = newChart;
    } else {
      noteDistChart = newChart;
    }

    console.log('Chart created successfully');
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

  // Define standard column order: date fields first, then key fields, then metrics
  const columnOrder = ['date', 'week_start', 'month_start', 'hour', 'week_key', 'month_key', 'total_notes', 'session_seconds', 'note_time_ms', 'total_data', 'total_energy', 'avg_velocity'];

  // Get columns that exist in the data, in the preferred order
  const allKeys = Object.keys(data[0]);
  const orderedKeys = columnOrder.filter(k => allKeys.includes(k));
  // Add any remaining keys that weren't in our order list
  const remainingKeys = allKeys.filter(k => !orderedKeys.includes(k));
  const finalKeys = orderedKeys.concat(remainingKeys);

  // Pagination setup
  let pageSize = 25;
  let currentPage = 0;
  let totalPages = Math.ceil(data.length / pageSize);

  const tableWrapper = document.createElement('div');
  tableWrapper.className = 'table_wrapper';

  const table = document.createElement('table');
  table.className = 'compact_table';
  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  finalKeys.forEach(k=>{ const th = document.createElement('th'); th.textContent = k; headerRow.appendChild(th);});
  thead.appendChild(headerRow);
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  table.appendChild(tbody);

  function renderPage(page){
    tbody.innerHTML = '';
    const start = page * pageSize;
    const end = Math.min(data.length, start + pageSize);
    for(let i = start; i < end; i++){
      const row = data[i];
      const tr = document.createElement('tr');
      finalKeys.forEach(k=>{
        const td = document.createElement('td');
        // Format time fields as HH:MM:SS
        if(k === 'session_seconds' && row[k] !== undefined && row[k] !== null){
          td.textContent = formatHMS(row[k]);
        } else if(k === 'note_time_ms' && row[k] !== undefined && row[k] !== null){
          td.textContent = formatHMS(row[k] / 1000); // Convert ms to seconds
        } else {
          td.textContent = row[k];
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    }
  }

  // Create pagination controls
  const pager = document.createElement('div');
  pager.className = 'pager';

  // Page size selector
  const pageSizeLabel = document.createElement('label');
  pageSizeLabel.textContent = 'Items per page: ';
  pageSizeLabel.style.marginRight = '8px';

  const pageSizeSelect = document.createElement('select');
  [10, 25, 50].forEach(size => {
    const option = document.createElement('option');
    option.value = size;
    option.textContent = size;
    if(size === pageSize) option.selected = true;
    pageSizeSelect.appendChild(option);
  });

  pageSizeSelect.addEventListener('change', ()=>{
    pageSize = Number(pageSizeSelect.value);
    totalPages = Math.ceil(data.length / pageSize);
    currentPage = 0; // Reset to first page
    renderPage(currentPage);
    pageLabel.textContent = `Page ${currentPage + 1} / ${totalPages}`;
    prevBtn.disabled = currentPage === 0;
    nextBtn.disabled = currentPage >= totalPages - 1;
  });

  const prevBtn = document.createElement('button'); prevBtn.textContent = 'Prev';
  const nextBtn = document.createElement('button'); nextBtn.textContent = 'Next';
  const pageLabel = document.createElement('span'); pageLabel.textContent = `Page ${currentPage + 1} / ${totalPages}`;
  pageLabel.style.margin = '0 8px';

  prevBtn.disabled = currentPage === 0;
  nextBtn.disabled = currentPage >= totalPages - 1;

  prevBtn.addEventListener('click', ()=>{
    if(currentPage > 0){
      currentPage--;
      renderPage(currentPage);
      pageLabel.textContent = `Page ${currentPage + 1} / ${totalPages}`;
      prevBtn.disabled = currentPage === 0;
      nextBtn.disabled = false;
    }
  });

  nextBtn.addEventListener('click', ()=>{
    if(currentPage < totalPages - 1){
      currentPage++;
      renderPage(currentPage);
      pageLabel.textContent = `Page ${currentPage + 1} / ${totalPages}`;
      nextBtn.disabled = currentPage >= totalPages - 1;
      prevBtn.disabled = false;
    }
  });

  pager.appendChild(pageSizeLabel);
  pager.appendChild(pageSizeSelect);
  pager.appendChild(prevBtn);
  pager.appendChild(pageLabel);
  pager.appendChild(nextBtn);
  tableWrapper.appendChild(pager);

  tableWrapper.appendChild(table);
  el.appendChild(tableWrapper);
  renderPage(currentPage);
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
  const durFmt = formatHMS((n.total_duration_ms || 0) / 1000); // Convert ms to seconds for HH:MM:SS
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

let useShortFormat = true; // Global flag for number formatting

function formatBigNumber(v){
  if(v === null || v === undefined) return '-';
  if(useShortFormat){
    if(v >= 1e6) return (v/1e6).toFixed(1)+'M';
    if(v >= 1e3) return (v/1e3).toFixed(1)+'k';
  }
  return String(Math.round(v));
}

async function updateStats(){
  try{
    const range = document.getElementById('range_select').value;
    const yKey = document.getElementById('y_select').value;
    console.log(`updateStats called: range=${range}, yKey=${yKey}`);
    const data = await fetchStats(range);
    console.log(`fetchStats returned ${data.length} rows`);

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
      // server returned month_key/month_start and totals (newest first, so reverse to oldest first)
      const reversed = data.slice().reverse();
      reversed.forEach(d=>{ labels.push((d.month_key || d.month_start) + '-01 00:00'); values.push(round2(Number(d[yKey]||0))); });
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
    // server returns week_start and totals (newest first, so reverse to oldest first)
    const reversed = data.slice().reverse();
    reversed.forEach(d=>{ labels.push((d.week_start || d.week_key) + ' 00:00'); values.push(round2(Number(d[yKey]||0))); });
  } else { // trends
    const reversed = data.slice().reverse();
    reversed.forEach(d=>{ labels.push((d.date||'') + ' 00:00'); values.push(round2(Number(d[yKey]||0))); });
  }

  const canvas = document.getElementById('stats_chart');
  console.log(`Sample labels: ${labels.slice(0, 3).join(', ')}`);
  buildChart(canvas, labels, values, yKey, range);
  // prepare a simplified table where numbers are rounded
  const normalized = data.map(d=>{
    const copy = Object.assign({}, d);
    Object.keys(copy).forEach(k=>{ if(typeof copy[k] === 'number') copy[k] = round2(copy[k]); });
    return copy;
  });
  renderSimpleTable('stats_table', normalized);

  // Calculate and display range totals
  updateRangeTotals(data, range);
  }catch(e){
    console.error('updateStats error', e);
    const el = document.getElementById('stats_table'); if(el) el.textContent = 'Error loading stats: ' + (e && e.message ? e.message : String(e));
  }
}

// Store range totals globally so we can re-format them when toggle changes
let rangeTotalsData = null;

function updateRangeTotals(data, range){
  // Calculate totals based on the current period (not cumulative)
  let totalNotes = 0;
  let totalEnergy = 0;
  let totalNoteDurationMs = 0;
  let totalSessionSeconds = 0;
  let totalDataBytes = 0;

  const now = new Date();
  const today = now.toISOString().slice(0, 10);
  const currentHour = now.getHours();
  const currentWeekStart = getWeekStart(now);
  const currentMonth = now.toISOString().slice(0, 7);

  // Filter data to only include the current period
  let filteredData = [];
  if(range === 'hourly'){
    // Current hour only
    filteredData = data.filter(d => d.date === today && d.hour === currentHour);
  } else if(range === 'daily'){
    // Current day only
    filteredData = data.filter(d => d.date === today);
  } else if(range === 'weekly'){
    // Current week only
    filteredData = data.filter(d => d.week_start === currentWeekStart || d.week_key === getISOWeek(now));
  } else if(range === 'monthly'){
    // Current month only
    filteredData = data.filter(d => (d.month_start && d.month_start.startsWith(currentMonth)) || d.month_key === currentMonth);
  } else {
    // Trends: sum everything (all-time)
    filteredData = data;
  }

  filteredData.forEach(d => {
    totalNotes += Number(d.total_notes || 0);
    totalEnergy += Number(d.total_energy || 0);
    totalNoteDurationMs += Number(d.note_time_ms || 0);
    totalSessionSeconds += Number(d.session_seconds || 0);
    totalDataBytes += Number(d.total_data || 0);
  });

  // Store data globally
  rangeTotalsData = {
    totalNotes,
    totalEnergy,
    totalNoteDurationMs,
    totalSessionSeconds,
    totalDataBytes,
    range
  };

  displayRangeTotals();
}

// Helper function to get ISO week (YYYY-WW format)
function getISOWeek(date){
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() + 4 - (d.getDay() || 7));
  const yearStart = new Date(d.getFullYear(), 0, 1);
  const weekNo = Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
  return d.getFullYear() + '-' + String(weekNo).padStart(2, '0');
}

// Helper function to get week start date (Monday of current week)
function getWeekStart(date){
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Adjust to Monday
  const monday = new Date(d.setDate(diff));
  return monday.toISOString().slice(0, 10);
}

function displayRangeTotals(){
  if(!rangeTotalsData) return;
  const {totalNotes, totalEnergy, totalNoteDurationMs, totalSessionSeconds, totalDataBytes, range} = rangeTotalsData;

  // Update range label and card labels
  const rangeLabelMap = {
    'hourly': 'Current Hour',
    'daily': 'Today',
    'weekly': 'This Week',
    'monthly': 'This Month',
    'trends': 'All-Time'
  };
  const rangeLabel = document.getElementById('range_totals_label');
  if(rangeLabel) rangeLabel.textContent = rangeLabelMap[range] || range;

  // Update card labels to match the range
  const labelSuffix = range === 'trends' ? ' (All-Time)' : '';
  if(document.getElementById('range_label_notes')) document.getElementById('range_label_notes').textContent = 'Notes' + labelSuffix;
  if(document.getElementById('range_label_energy')) document.getElementById('range_label_energy').textContent = 'Energy (J)' + labelSuffix;
  if(document.getElementById('range_label_note_hours')) document.getElementById('range_label_note_hours').textContent = 'Note Duration (hrs)' + labelSuffix;
  if(document.getElementById('range_label_practice_hours')) document.getElementById('range_label_practice_hours').textContent = 'Practice Hours' + labelSuffix;
  if(document.getElementById('range_label_midi_mb')) document.getElementById('range_label_midi_mb').textContent = 'MIDI data (MB)' + labelSuffix;

  // Update display values
  const noteHours = totalNoteDurationMs / (1000.0 * 3600.0);
  const practiceHours = totalSessionSeconds / 3600.0;
  const midiMB = totalDataBytes / (1024.0 * 1024.0);

  document.getElementById('range_total_notes').textContent = formatBigNumber(totalNotes);
  document.getElementById('range_total_energy').textContent = totalEnergy.toFixed(2);
  document.getElementById('range_note_hours').textContent = noteHours.toFixed(1);
  document.getElementById('range_practice_hours').textContent = practiceHours.toFixed(1);
  document.getElementById('range_midi_mb').textContent = midiMB.toFixed(2);
}

function round2(v){
  if(v === null || v === undefined) return 0;
  return Math.round(Number(v) * 100) / 100;
}

async function updateNoteDistribution(){
  try{
    const range = document.getElementById('range_select').value;
    const el = document.getElementById('dist_date');
    let date = el.value;
    if(!date){ date = new Date().toISOString().slice(0,10); el.value = date; }

    // Use the heatmap API which already supports range-based queries
    const url = `/api/heatmap_distribution?range=${encodeURIComponent(range)}&date=${encodeURIComponent(date)}`;
    const r = await fetch(url);
    const resp = await r.json();

    if(!resp || !resp.ok){ document.getElementById('note_distribution_table').textContent = 'No data'; return; }
  // update big totals (for the selected time range - these are the cards in the Note Distribution section)
  const totals = resp.totals || {};
  document.getElementById('total_notes').textContent = formatBigNumber(totals.total_notes || 0);
  document.getElementById('total_energy').textContent = (totals.total_energy || 0).toFixed(2);
  document.getElementById('avg_velocity').textContent = (totals.avg_velocity || 0).toFixed(1);
  // NOTE: Do NOT update the small top totals (_top) - those should always show all-time totals

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

// Store all-time totals globally so we can re-format them when toggle changes
let allTimeTotals = null;

// Fetch and display all-time totals at top (from server)
async function fetchAllTotals(){
  try{
    const r = await fetch('/api/stats/all_totals');
    const j = await r.json();
    if(!j.ok) return;
    allTimeTotals = j.totals || {};
    displayAllTimeTotals();
  }catch(e){ console.error(e); }
}

function displayAllTimeTotals(){
  if(!allTimeTotals) return;
  const t = allTimeTotals;
  if(document.getElementById('total_notes_top')) document.getElementById('total_notes_top').textContent = formatBigNumber(t.total_notes || 0);
  if(document.getElementById('total_energy_top')) document.getElementById('total_energy_top').textContent = (t.total_energy || 0).toFixed(2);
  if(document.getElementById('total_note_hours_top')) document.getElementById('total_note_hours_top').textContent = (t.total_note_duration_hours || 0).toFixed(1);
  if(document.getElementById('total_practice_hours_top')) document.getElementById('total_practice_hours_top').textContent = (t.total_practice_hours || 0).toFixed(1);
  if(document.getElementById('total_pedal_presses_top')) document.getElementById('total_pedal_presses_top').textContent = formatBigNumber(t.total_pedal_presses || 0);
  if(document.getElementById('total_midi_mb_top')) document.getElementById('total_midi_mb_top').textContent = (t.total_midi_mb || 0).toFixed(2);
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

function updateNoteDistributionLabels(){
  const range = document.getElementById('range_select').value;
  const titleEl = document.querySelector('#stats h3:nth-of-type(3)');
  const dateLabel = document.querySelector('label[for="dist_date"]');

  // Update section title
  if(titleEl){
    let rangeText = 'Per-Day';
    if(range === 'weekly') rangeText = 'Per-Week';
    else if(range === 'monthly') rangeText = 'Per-Month';
    else if(range === 'hourly') rangeText = 'Per-Day';
    else if(range === 'trends') rangeText = 'All-Time';
    titleEl.textContent = `Note Distribution (${rangeText})`;
  }

  // Update date picker label
  if(dateLabel){
    let labelText = 'Date:';
    if(range === 'weekly') labelText = 'Week Starting:';
    else if(range === 'monthly') labelText = 'Month:';
    dateLabel.textContent = labelText;
  }
}

document.addEventListener('DOMContentLoaded', ()=>{
  // Set default values BEFORE setting up event listeners and initial data load
  document.getElementById('y_select').value = 'total_notes'; // default to total_notes

  // Set up event listeners
  document.getElementById('range_select').addEventListener('change', async ()=>{
    updateNoteDistributionLabels();
    // Add a small delay to ensure DOM is ready
    await new Promise(resolve => setTimeout(resolve, 50));
    // Call updateStats first and wait for it to complete before calling others
    await updateStats().catch(e=>console.error(e));
    // Then call the other updates in parallel
    await Promise.all([
      updateHeatmap().catch(e=>console.error(e)),
      updateNoteDistribution().catch(e=>console.error(e))
    ]);
  });
  document.getElementById('y_select').addEventListener('change', ()=>{ updateStats().catch(e=>console.error(e)); });
  document.getElementById('dist_date').addEventListener('change', ()=>{ updateNoteDistribution().catch(e=>console.error(e)); });
  document.getElementById('heatmap_refresh').addEventListener('click', ()=>{ updateHeatmap().catch(e=>console.error(e)); });

  // Toggle event listener for number formatting
  const formatToggle = document.getElementById('format_toggle');
  if(formatToggle){
    formatToggle.addEventListener('change', ()=>{
      useShortFormat = formatToggle.checked;
      // Re-display all totals with new format
      displayAllTimeTotals();
      displayRangeTotals();
      updateNoteDistribution().catch(e=>console.error(e));
    });
  }

  // Load initial data, protective try/catch to avoid leaving Loading...
  fetchAllTotals().catch(e=>console.error(e));
  updateStats().catch(e=>console.error(e));
  updateNoteDistribution().catch(e=>console.error(e));
  updateHeatmap().catch(e=>console.error(e));
  updateNoteDistributionLabels();

  // Prev/Next date navigation for note distribution
  const prevBtn = document.getElementById('dist_prev');
  const nextBtn = document.getElementById('dist_next');
  const dateInput = document.getElementById('dist_date');
  function shiftDate(direction){
    const range = document.getElementById('range_select').value;
    let d = dateInput.value ? new Date(dateInput.value) : new Date();

    // Shift by appropriate interval based on time range
    if(range === 'weekly'){
      d.setDate(d.getDate() + (direction * 7));
    } else if(range === 'monthly'){
      d.setMonth(d.getMonth() + direction);
    } else {
      // hourly, daily, trends - shift by 1 day
      d.setDate(d.getDate() + direction);
    }

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

  // draw white keys first
  let whiteKeyIndex = 0;
  for(let i=0;i<totalKeys;i++){
    const midi = midiMin + i;
    // Only draw white keys in this pass
    if(!isBlackKey(midi)){
      const c = counts[midi] || 0;
      const intensity = c / maxCount;
      // color from light gray to blue
      const alpha = 0.2 + intensity * 0.8;
      ctx.fillStyle = `rgba(43,140,190,${alpha.toFixed(2)})`;
      ctx.fillRect(whiteKeyIndex * whiteKeyWidth, 0, Math.ceil(whiteKeyWidth), height * 0.7);
      // draw key border
      ctx.strokeStyle = '#ddd';
      ctx.strokeRect(whiteKeyIndex * whiteKeyWidth, 0, Math.ceil(whiteKeyWidth), height * 0.7);
      whiteKeyIndex++;
    }
  }

  // draw black key overlays on top, positioned between white keys
  whiteKeyIndex = 0;
  for(let i=0;i<totalKeys;i++){
    const midi = midiMin + i;
    if(!isBlackKey(midi)){
      whiteKeyIndex++;
    } else {
      const c = counts[midi] || 0;
      const intensity = c / maxCount;
      const alpha = 0.15 + intensity * 0.85;
      const blackKeyWidth = whiteKeyWidth * 0.6;
      const xPos = whiteKeyIndex * whiteKeyWidth - blackKeyWidth / 2;

      ctx.fillStyle = `rgba(0,0,0,${alpha.toFixed(2)})`;
      ctx.fillRect(xPos, 0, blackKeyWidth, height * 0.45);

      // Draw border for black keys
      ctx.strokeStyle = '#000';
      ctx.strokeRect(xPos, 0, blackKeyWidth, height * 0.45);
    }
  }

  // draw small counts under each key (rotated for space)
  ctx.save();
  ctx.fillStyle = '#333';
  ctx.font = '10px sans-serif';
  ctx.textAlign = 'center';
  whiteKeyIndex = 0;
  for(let i=0;i<totalKeys;i++){
    const midi = midiMin + i;
    const c = counts[midi] || 0;
    let x, y;

    if(!isBlackKey(midi)){
      // White key
      x = whiteKeyIndex * whiteKeyWidth + whiteKeyWidth/2;
      y = height * 0.78;
      whiteKeyIndex++;
    } else {
      // Black key
      const blackKeyWidth = whiteKeyWidth * 0.6;
      x = whiteKeyIndex * whiteKeyWidth;
      y = height * 0.52;
    }

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
      const count = counts[hoveredMidi] || 0;
      const noteNames = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
      const name = noteNames[hoveredMidi % 12] + (Math.floor(hoveredMidi/12)-1);
      tooltip.style.display = 'block';
      tooltip.textContent = `${name}: ${count}`;
      tooltip.style.left = `${rect.left + tooltipX}px`;
      tooltip.style.top = `${rect.top + height * 0.65}px`;
    } else {
      tooltip.style.display = 'none';
    }
  };
  canvas.onmouseout = function(){ const t = document.getElementById('heatmap_tooltip'); if(t) t.style.display = 'none'; };
}
