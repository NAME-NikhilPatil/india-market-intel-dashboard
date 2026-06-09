// ────────────────────────────────────────────────────────────
// FT-styled renderers. Every chart uses the FT palette.
// No legend boxes — labels are placed directly on lines.
// ────────────────────────────────────────────────────────────

const FT = {
  paper: '#FFF1E5', paper2: '#F7E1CE', paper3: '#FBE9D6',
  ink: '#262A33', inkMid: '#66605C', inkFaint: '#9F938A',
  rule: '#CCC1B7',
  claret: '#990F3D', navy: '#0D2A4C', teal: '#0F5499', green: '#00867D',
  olive: '#806F47', gold: '#B68900', red: '#CC3333',
  cell: '#0F5499', module: '#990F3D',
};

// ─── Compute the last YYYY-MM that has any non-zero data, globally ───
const LAST_YM = (() => {
  let last = '0000-00';
  DATA.cellMonthlyAgg.concat(DATA.moduleMonthlyAgg).forEach(r => {
    if (r.mw > 0) {
      const ym = r.year + '-' + String(r.month).padStart(2,'0');
      if (ym > last) last = ym;
    }
  });
  return last;
})();
const LAST_YEAR = +LAST_YM.slice(0, 4);
const LAST_MONTH = +LAST_YM.slice(5, 7);

// ─── Search active helpers ───
function searchActive() { return STATE.search && STATE.search.trim().length > 0; }
function matchesSearch(name) { return !searchActive() || name.toLowerCase().includes(STATE.search.toLowerCase()); }
function searchMatchCount() {
  if (!searchActive()) return 0;
  const allNames = new Set();
  DATA.derived.companiesCell.forEach(c => allNames.add(c.name));
  DATA.derived.companiesModule.forEach(c => allNames.add(c.name));
  let n = 0; allNames.forEach(name => { if (matchesSearch(name)) n++; });
  return n;
}
function applySearchFilter(list, key='name') {
  if (!searchActive()) return list;
  return list.filter(o => (o[key]||'').toLowerCase().includes(STATE.search.toLowerCase()));
}

// ─── Helper: month/year cells that should NOT be rendered because data hasn't arrived yet ───
function isFutureMonth(year, month) {
  return year > LAST_YEAR || (year === LAST_YEAR && month > LAST_MONTH);
}
function isFutureYM(ym) {
  return ym > LAST_YM;
}

const baseAxisOpts = () => ({
  responsive: true, maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: FT.paper, borderColor: FT.ink, borderWidth: 1,
      titleColor: FT.ink, bodyColor: FT.ink,
      titleFont: { family: "'Source Serif 4', Georgia, serif", weight: 700, size: 13 },
      bodyFont: { family: "'Inter', sans-serif", size: 12 },
      padding: 10, cornerRadius: 0, displayColors: true, boxPadding: 4,
    },
  },
  scales: {
    x: { grid: { display: false, drawBorder: false }, ticks: { color: FT.inkMid, font: { size: 10.5 } }, border: { color: FT.ink } },
    y: { grid: { color: 'rgba(38,42,51,0.06)', drawBorder: false }, ticks: { color: FT.inkMid, font: { size: 10.5 }, callback: v => v>=1000 ? (v/1000).toFixed(v>=10000?0:1)+'k' : v }, border: { display: false } },
  },
});

// ─── Direct-label plugin with overlap repulsion (simple iterative push apart) ───
const directLabelPlugin = {
  id: 'directLabel',
  afterDatasetsDraw(chart) {
    const { ctx, chartArea } = chart;
    ctx.save();
    ctx.font = "600 11px 'Inter', sans-serif";
    const minGap = 14; // px between label center lines
    // Collect labels with their natural positions
    const items = [];
    chart.data.datasets.forEach((ds, idx) => {
      if (ds.hidden) return;
      const label = ds._directLabel || '';
      if (!label) return;
      const meta = chart.getDatasetMeta(idx);
      // find last non-null point
      let lastPt = null, lastV = null;
      for (let i = meta.data.length - 1; i >= 0; i--) {
        if (ds.data[i] != null && meta.data[i]) { lastPt = meta.data[i]; lastV = ds.data[i]; break; }
      }
      if (!lastPt) return;
      items.push({ y: lastPt.y, x: lastPt.x, label, color: ds.borderColor || FT.ink });
    });
    // Sort by y and resolve overlaps by pushing later items down or earlier items up
    items.sort((a,b) => a.y - b.y);
    for (let pass = 0; pass < 6; pass++) {
      let changed = false;
      for (let i = 1; i < items.length; i++) {
        const gap = items[i].y - items[i-1].y;
        if (gap < minGap) {
          const push = (minGap - gap) / 2;
          items[i-1].y -= push;
          items[i].y += push;
          changed = true;
        }
      }
      if (!changed) break;
    }
    // Clamp to chart area
    items.forEach(it => { it.y = Math.max(chartArea.top + 8, Math.min(chartArea.bottom - 4, it.y)); });
    // Draw
    items.forEach(it => {
      ctx.fillStyle = it.color;
      ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
      ctx.fillText(it.label, it.x + 8, it.y);
    });
    ctx.restore();
  }
};
Chart.register(directLabelPlugin);

// ────────────────────────────────────────────────────────────
// 0 · KPI snapshot strip
// ────────────────────────────────────────────────────────────
function renderKPI() {
  const t = DATA.totals;
  const ytC = DATA.derived.yearlyTotalsCell, ytM = DATA.derived.yearlyTotalsModule;
  const stock = DATA.stockTotals;
  const totalStock = stock.cell_with_manufacturer_mw + stock.cell_with_reseller_mw + stock.module_with_manufacturer_mw + stock.module_with_reseller_mw;
  const totalUnc = stock.cell_unclaimed_with_manufacturer_mw + stock.cell_unclaimed_with_reseller_mw + stock.module_unclaimed_with_manufacturer_mw + stock.module_unclaimed_with_reseller_mw;
  const cell25 = ytC[2025], cell24 = ytC[2024];
  const mod25 = ytM[2025], mod24 = ytM[2024];
  const cellG = (cell25-cell24)/cell24*100;
  const modG = (mod25-mod24)/mod24*100;
  const yrs = [2022,2023,2024,2025,2026];
  const cellSpark = yrs.map(y => ytC[y]||0);
  const modSpark = yrs.map(y => ytM[y]||0);

  const cards = [
    { eyebrow: 'Cell 2025 MW', figure: fmtMW(cell25), unit: 'MW', delta: `<span class="up">${fmtPct(cellG)}</span> vs 2024 · 18-month trend`,
      spark: svgSpark(cellSpark, { color: FT.cell, w: 90, h: 22, sw: 1.8, dot: true }) },
    { eyebrow: 'Module 2025 MW', figure: fmtMW(mod25), unit: 'MW', delta: `<span class="up">${fmtPct(modG)}</span> vs 2024 · 18-month trend`,
      spark: svgSpark(modSpark, { color: FT.module, w: 90, h: 22, sw: 1.8, dot: true }) },
    { eyebrow: 'Cell makers', figure: t.solar_cell_manufacturers.toString(), unit: 'live', delta: `<span>${DATA.derived.activeCell[2025]}</span> active in 2025 · was 2 in '22`,
      spark: svgSpark(yrs.map(y => DATA.derived.activeCell[y]||0), { color: FT.cell, w: 90, h: 22, sw: 1.8 }) },
    { eyebrow: 'Module makers', figure: t.solar_module_manufacturers.toString(), unit: 'live', delta: `<span>${DATA.derived.activeModule[2025]}</span> active in 2025 · was 1 in '22`,
      spark: svgSpark(yrs.map(y => DATA.derived.activeModule[y]||0), { color: FT.module, w: 90, h: 22, sw: 1.8 }) },
    { eyebrow: 'Live stock', figure: fmtMW(totalStock), unit: 'MW', delta: `Claimed · with mfrs &amp; resellers`,
      spark: svgSpark([stock.cell_with_manufacturer_mw, stock.cell_with_reseller_mw, stock.module_with_manufacturer_mw, stock.module_with_reseller_mw], { color: FT.green, w: 90, h: 22, sw: 1.8 }) },
    { eyebrow: 'Unclaimed', figure: fmtMW(totalUnc), unit: 'MW', delta: `<span class="down">${(totalUnc/(totalStock+totalUnc)*100).toFixed(1)}%</span> of total stock`,
      spark: svgSpark([stock.cell_unclaimed_with_manufacturer_mw, stock.cell_unclaimed_with_reseller_mw, stock.module_unclaimed_with_manufacturer_mw, stock.module_unclaimed_with_reseller_mw], { color: FT.red, w: 90, h: 22, sw: 1.8 }) },
  ];
  document.getElementById('kpiStrip').innerHTML = cards.map(c => `
    <div class="kpi-cell">
      <div class="kpi-eyebrow">${c.eyebrow}</div>
      <div class="kpi-figure">${c.figure}<span class="unit">${c.unit}</span></div>
      <div class="kpi-delta">${c.delta}</div>
      <div class="kpi-spark">${c.spark}</div>
    </div>
  `).join('');
}

// ────────────────────────────────────────────────────────────
// 1 · Monthly market volumes table (replaces old annual line chart)
// ────────────────────────────────────────────────────────────
function renderMarketTable() {
  const wrap = document.getElementById('marketTableWrap');
  if (!wrap) return;
  const seg = STATE.marketSeg || 'cell';
  const mfgMetric = `${seg}_manufactured_mw`;
  const agg = aggMonthlyForSeg(seg);
  const segColor = SEG_COLOR[seg];

  // Build matrix: rows = years, columns = month index 1..12
  const yrs = [2022, 2023, 2024, 2025, 2026];
  const monthlyMatrix = {};  // year -> array of 12 values
  yrs.forEach(y => { monthlyMatrix[y] = Array(12).fill(0); });
  agg.forEach(r => {
    if (r.metric === mfgMetric) monthlyMatrix[r.year][r.month - 1] = r.mw;
  });

  // Quarterly mode?
  const granularity = STATE.monVolGran || 'monthly';
  const isQ = granularity === 'quarterly';
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const cols = isQ
    ? [{ label: 'Q1', months: [0,1,2] }, { label: 'Q2', months: [3,4,5] }, { label: 'Q3', months: [6,7,8] }, { label: 'Q4', months: [9,10,11] }]
    : months.map((m, i) => ({ label: m.slice(0,1), months: [i], full: m }));

  // ── Header ──
  const head = `<tr>
    <th class="left sticky-l" style="min-width: 70px;">Year</th>
    ${cols.map(c => `<th class="num" style="width: ${isQ?'90':'48'}px;" title="${c.months.map(mi => months[mi]).join(', ')}">${c.label}</th>`).join('')}
    <th class="num annual sticky-r">FY Total</th>
  </tr>`;

  // ── Body ──
  let grand = 0;
  const body = yrs.map(y => {
    const vals = monthlyMatrix[y];
    const lastMonthForYear = (y === LAST_YEAR) ? LAST_MONTH : 12;
    const yt = vals.slice(0, lastMonthForYear).reduce((s,v) => s + v, 0);
    grand += yt;
    const cells = cols.map((col, ci) => {
      const validMonths = col.months.filter(mi => mi + 1 <= lastMonthForYear);
      if (validMonths.length === 0) {
        return `<td class="future-month" style="background: transparent; border-bottom: none; padding: 0;"></td>`;
      }
      const v = validMonths.reduce((s, mi) => s + vals[mi], 0);
      const partial = isQ && validMonths.length < col.months.length;
      // bar widening proportionally inside the cell — subtle, behind the number
      return `<td class="num ${v===0?'zero':''}" data-csv="${v.toFixed(2)}" title="${col.months.map(mi=>months[mi]+' '+y).join(', ')}">${v===0?'·':fmtMW(v)}${partial?'*':''}</td>`;
    }).join('');
    const isPartialYr = (y === LAST_YEAR && LAST_MONTH < 12);
    return `<tr>
      <td class="left sticky-l" style="font-weight: 700; ${isPartialYr?'color: var(--claret);':''}">${y}${isPartialYr?` YTD ${months[LAST_MONTH-1]}`:''}</td>
      ${cells}
      <td class="num annual sticky-r" data-csv="${yt.toFixed(2)}" style="font-weight: 700;">${fmtMW(yt)}</td>
    </tr>`;
  }).join('');

  // ── Footer 1: Average per month/quarter across active years ──
  const colSums = cols.map(() => 0);
  const colCounts = cols.map(() => 0);
  yrs.forEach(y => {
    const lastMonthForYear = (y === LAST_YEAR) ? LAST_MONTH : 12;
    cols.forEach((col, ci) => {
      const validMonths = col.months.filter(mi => mi + 1 <= lastMonthForYear);
      if (validMonths.length === 0) return;
      const v = validMonths.reduce((s, mi) => s + monthlyMatrix[y][mi], 0);
      if (v > 0) { colSums[ci] += v; colCounts[ci] += 1; }
    });
  });
  const avgRow = `<tr class="tot-row">
    <td class="left sticky-l">Avg (active ${isQ?'Q':'mo'}s)</td>
    ${colSums.map((s, i) => {
      const v = colCounts[i] ? s/colCounts[i] : 0;
      return `<td class="num ${v===0?'zero':''}" data-csv="${v.toFixed(2)}">${v===0?'·':fmtMW(v)}</td>`;
    }).join('')}
    <td class="num annual sticky-r" data-csv="${grand.toFixed(2)}" style="font-weight: 700;">${fmtMW(grand)}</td>
  </tr>`;

  // ── Footer 2: YoY % growth row (vs prior year of same month/quarter) ──
  // For each column, compute 2025 vs 2024 ratio (most informative single comparison)
  const yoyRow = `<tr class="tot-row" style="background: transparent;">
    <td class="left sticky-l" style="font-style: italic; color: var(--ink-mid); font-weight: 500;">YoY 2025 / 2024</td>
    ${cols.map((col, ci) => {
      let v25 = 0, v24 = 0;
      col.months.forEach(mi => { v25 += monthlyMatrix[2025][mi]; v24 += monthlyMatrix[2024][mi]; });
      if (v24 === 0) return `<td class="num zero">—</td>`;
      const pct = (v25 - v24) / v24 * 100;
      const color = pct > 0 ? 'var(--green)' : 'var(--claret)';
      return `<td class="num" style="color: ${color}; font-weight: 600;" data-csv="${pct.toFixed(1)}">${pct>0?'+':''}${pct.toFixed(0)}%</td>`;
    }).join('')}
    <td class="num annual sticky-r" data-csv="">${(() => {
      const y25 = monthlyMatrix[2025].reduce((s,v)=>s+v,0);
      const y24 = monthlyMatrix[2024].reduce((s,v)=>s+v,0);
      if (y24 === 0) return '—';
      const pct = (y25 - y24) / y24 * 100;
      const color = pct > 0 ? 'var(--green)' : 'var(--claret)';
      return `<span style="color: ${color}; font-weight: 700;">${pct>0?'+':''}${pct.toFixed(0)}%</span>`;
    })()}</td>
  </tr>`;

  wrap.innerHTML = `<table class="data-tbl" id="marketTable" style="min-width: 100%;">
    <thead>${head}</thead>
    <tbody>${body}${avgRow}${yoyRow}</tbody>
  </table>${isQ?'<div style="margin-top: 6px; font-size: 10.5px; color: var(--ink-mid); font-style: italic;">Q* = partial quarter (fewer than 3 months of data).</div>':''}`;

  // Also refresh the key events strip (which used to be rendered as a side-effect of renderAnnualMW)
  if (typeof renderKeyEvents === 'function') renderKeyEvents();
}

// Compatibility shim: some old call sites may still reference renderAnnualMW
function renderAnnualMW_DEPRECATED() {
  destroyChart('chartAnnualMW');
  const ctx = document.getElementById('chartAnnualMW').getContext('2d');
  const yrs = activeYears();
  const ytC = DATA.derived.yearlyTotalsCell, ytM = DATA.derived.yearlyTotalsModule;
  const has2026 = yrs.includes(2026);
  const idx2026 = yrs.indexOf(2026);

  // raw values
  let dC = yrs.map(y => ytC[y]||0), dM = yrs.map(y => ytM[y]||0);
  if (STATE.overviewView === 'cum') {
    let cc=0, mm=0; dC = dC.map(v => cc+=v); dM = dM.map(v => mm+=v);
  } else if (STATE.overviewView === 'yoy') {
    const yoy = arr => arr.map((v,i) => i===0 ? null : (arr[i-1]===0?null:((v-arr[i-1])/arr[i-1]*100)));
    dC = yoy(yrs.map(y => ytC[y]||0)); dM = yoy(yrs.map(y => ytM[y]||0));
  }

  // Split full-year and YTD-segment for visual distinction
  // Strategy: build TWO datasets per segment — "full" stops at 2025, "ytd" carries 2025→2026 only (so the line continues as dashed)
  function splitYears(vals) {
    if (!has2026) return { full: vals, ytd: vals.map(_ => null) };
    const fullCutIdx = idx2026 - 1; // index of 2025
    const full = vals.map((v, i) => i <= fullCutIdx ? v : null);
    const ytd  = vals.map((v, i) => (i === fullCutIdx || i === idx2026) ? v : null);
    return { full, ytd };
  }

  const datasets = [];
  const segs = activeSegments();
  const filling = STATE.overviewView !== 'yoy';
  if (segs.includes('cell')) {
    const split = splitYears(dC);
    datasets.push({ label: 'Cell', _directLabel: 'Cell', data: split.full, borderColor: FT.cell, backgroundColor: 'rgba(15,84,153,0.10)', fill: filling ? 'origin' : false, tension: 0.32, borderWidth: 2.4, pointRadius: 3, pointBackgroundColor: FT.cell, pointBorderColor: FT.paper, pointBorderWidth: 1.5, spanGaps: false });
    if (has2026) datasets.push({ label: 'Cell (2026 YTD)', _directLabel: '', data: split.ytd, borderColor: FT.cell, backgroundColor: 'rgba(15,84,153,0.06)', fill: filling ? 'origin' : false, tension: 0.32, borderWidth: 2, borderDash: [5, 4], pointRadius: 3, pointBackgroundColor: FT.paper, pointBorderColor: FT.cell, pointBorderWidth: 1.8, spanGaps: false });
  }
  if (segs.includes('module')) {
    const split = splitYears(dM);
    datasets.push({ label: 'Module', _directLabel: 'Module', data: split.full, borderColor: FT.module, backgroundColor: 'rgba(153,15,61,0.10)', fill: filling ? 'origin' : false, tension: 0.32, borderWidth: 2.4, pointRadius: 3, pointBackgroundColor: FT.module, pointBorderColor: FT.paper, pointBorderWidth: 1.5, spanGaps: false });
    if (has2026) datasets.push({ label: 'Module (2026 YTD)', _directLabel: '', data: split.ytd, borderColor: FT.module, backgroundColor: 'rgba(153,15,61,0.06)', fill: filling ? 'origin' : false, tension: 0.32, borderWidth: 2, borderDash: [5, 4], pointRadius: 3, pointBackgroundColor: FT.paper, pointBorderColor: FT.module, pointBorderWidth: 1.8, spanGaps: false });
  }

  const opts = baseAxisOpts();
  if (STATE.overviewView === 'yoy') opts.scales.y.ticks.callback = v => v + '%';
  opts.layout = { padding: { right: 60, top: 10 } };
  opts.plugins.tooltip.callbacks = {
    label: c => `${c.dataset.label}: ${STATE.overviewView==='yoy' ? (c.parsed.y==null?'—':c.parsed.y.toFixed(1)+'%') : fmtMWfull(c.parsed.y) + ' MW'}`
  };

  // YTD shading + label for the 2025→2026 region
  const ytdShade = {
    id: 'ytdShade',
    beforeDatasetsDraw(chart) {
      if (!has2026 || STATE.overviewView === 'yoy') return;
      const { ctx, chartArea, scales } = chart;
      const x0 = scales.x.getPixelForValue(idx2026 - 1);
      const x1 = scales.x.getPixelForValue(idx2026);
      ctx.save();
      // diagonal hatch
      const w = x1 - x0;
      ctx.fillStyle = 'rgba(38,42,51,0.04)';
      ctx.fillRect(x0, chartArea.top, w, chartArea.bottom - chartArea.top);
      ctx.fillStyle = FT.inkMid;
      ctx.font = "italic 10px 'Source Serif 4', Georgia, serif";
      ctx.fillText('YTD May', x0 + 4, chartArea.top + 12);
      ctx.restore();
    }
  };

  CHARTS.chartAnnualMW = new Chart(ctx, {
    type: 'line', data: { labels: yrs.map(y => y===2026 ? '2026' : String(y)), datasets }, options: opts,
    plugins: [ytdShade]
  });

  renderKeyEvents();
}

function renderKeyEvents() {
  const ytC = DATA.derived.yearlyTotalsCell, ytM = DATA.derived.yearlyTotalsModule;
  const events = [
    { year: 2022, tag: 'GENESIS', text: `<strong>Jupiter International</strong> alone in cell (<span class="num">${fmtMW(ytC[2022])} MW</span>); a single module maker registers.` },
    { year: 2023, tag: 'TAKEOFF', text: `Cell output multiplies <span class="num">29×</span> to <span class="num">${fmtMW(ytC[2023])} MW</span>; <strong>Waaree</strong> opens the module field.` },
    { year: 2024, tag: 'SURGE', text: `<strong>FS India</strong> debuts at <span class="num">1.8 GW</span> cell; module field swells to <span class="num">42 makers</span>; ${fmtMW(ytC[2024])} MW cell · ${fmtMW(ytM[2024])} MW module.` },
    { year: 2025, tag: 'LEADERSHIP SHIFT', text: `<strong>TP Solar</strong> leaps to cell #1 at <span class="num">3.4 GW</span>; HHI falls to <span class="num">${DATA.derived.hhiCell[2025]}</span> (cell), <span class="num">${DATA.derived.hhiModule[2025]}</span> (module).` },
    { year: 2026, tag: 'YTD MAY', text: `Cell already at <span class="num">${fmtMW(ytC[2026])} MW</span> through May; annualises to <span class="num">~${fmtMW(DATA.derived.projection2026.cell_mfg.projected_full_year)} MW</span>.` },
  ];
  const el = document.getElementById('keyEvents');
  if (!el) return;
  el.innerHTML = events.map(e => `<div class="ke">
    <div class="ke-tag">${e.tag}</div>
    <div class="ke-year">${e.year}</div>
    <div class="ke-text">${e.text}</div>
  </div>`).join('');
}

// ────────────────────────────────────────────────────────────
// 2 · HHI line with reference bands
// ────────────────────────────────────────────────────────────
function renderHHI() {
  destroyChart('chartHHI');
  const ctx = document.getElementById('chartHHI').getContext('2d');
  const yrs = activeYears();
  const has2026 = yrs.includes(2026);
  const idx2026 = yrs.indexOf(2026);

  function splitYears(vals) {
    if (!has2026) return { full: vals, ytd: vals.map(_ => null) };
    const cut = idx2026 - 1;
    return {
      full: vals.map((v,i) => i <= cut ? v : null),
      ytd:  vals.map((v,i) => (i === cut || i === idx2026) ? v : null)
    };
  }

  const datasets = [];
  const segs = activeSegments();
  if (segs.includes('cell')) {
    const split = splitYears(yrs.map(y => DATA.derived.hhiCell[y]||null));
    datasets.push({ label: 'Cell HHI', _directLabel: 'Cell', data: split.full, borderColor: FT.cell, fill: false, tension: 0.3, borderWidth: 2.4, pointRadius: 4, pointBackgroundColor: FT.cell, spanGaps: false });
    if (has2026) datasets.push({ label: 'Cell HHI (YTD)', _directLabel: '', data: split.ytd, borderColor: FT.cell, borderDash: [5,4], fill: false, tension: 0.3, borderWidth: 2, pointRadius: 4, pointBackgroundColor: FT.paper, pointBorderColor: FT.cell, pointBorderWidth: 1.8, spanGaps: false });
  }
  if (segs.includes('module')) {
    const split = splitYears(yrs.map(y => DATA.derived.hhiModule[y]||null));
    datasets.push({ label: 'Module HHI', _directLabel: 'Module', data: split.full, borderColor: FT.module, fill: false, tension: 0.3, borderWidth: 2.4, pointRadius: 4, pointBackgroundColor: FT.module, spanGaps: false });
    if (has2026) datasets.push({ label: 'Module HHI (YTD)', _directLabel: '', data: split.ytd, borderColor: FT.module, borderDash: [5,4], fill: false, tension: 0.3, borderWidth: 2, pointRadius: 4, pointBackgroundColor: FT.paper, pointBorderColor: FT.module, pointBorderWidth: 1.8, spanGaps: false });
  }

  const refBands = {
    id: 'refBands',
    beforeDatasetsDraw(chart) {
      const { ctx, chartArea, scales } = chart;
      const y1500 = scales.y.getPixelForValue(1500);
      const y2500 = scales.y.getPixelForValue(2500);
      ctx.save();
      // moderate-concentration band (1500-2500)
      ctx.fillStyle = 'rgba(15,84,153,0.04)';
      ctx.fillRect(chartArea.left, y2500, chartArea.right - chartArea.left, y1500 - y2500);
      // reference lines
      ctx.strokeStyle = 'rgba(38,42,51,0.30)'; ctx.lineWidth = 1; ctx.setLineDash([3,3]);
      ctx.beginPath(); ctx.moveTo(chartArea.left, y1500); ctx.lineTo(chartArea.right, y1500); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(chartArea.left, y2500); ctx.lineTo(chartArea.right, y2500); ctx.stroke();
      ctx.setLineDash([]);
      // labels at the LEFT (data points generally trend downward to the right, so left is clear)
      ctx.font = "italic 10px 'Source Serif 4', serif"; ctx.fillStyle = FT.inkMid; ctx.textAlign = 'left';
      // Position labels slightly inside chart area, near the line itself
      if (y1500 >= chartArea.top && y1500 <= chartArea.bottom) {
        // small white-paper backsplash so text stays legible over any band fill
        ctx.fillStyle = FT.paper;
        ctx.fillRect(chartArea.left + 4, y1500 - 11, 134, 11);
        ctx.fillStyle = FT.inkMid;
        ctx.fillText('1,500 unconcentrated', chartArea.left + 6, y1500 - 3);
      }
      if (y2500 >= chartArea.top && y2500 <= chartArea.bottom) {
        ctx.fillStyle = FT.paper;
        ctx.fillRect(chartArea.left + 4, y2500 - 11, 158, 11);
        ctx.fillStyle = FT.inkMid;
        ctx.fillText('2,500 highly concentrated', chartArea.left + 6, y2500 - 3);
      }
      ctx.restore();
    }
  };

  const opts = baseAxisOpts();
  opts.layout = { padding: { right: 50 } };
  CHARTS.chartHHI = new Chart(ctx, {
    type: 'line', data: { labels: yrs.map(y => y===2026?'2026 YTD':String(y)), datasets }, options: opts,
    plugins: [refBands]
  });
}

// ────────────────────────────────────────────────────────────
// 3 · Mini KPIs strip (4 mini sparkline blocks)
// ────────────────────────────────────────────────────────────
function renderMiniKPIs() {
  const yrs = [2022,2023,2024,2025,2026];
  const ytC = DATA.derived.yearlyTotalsCell, ytM = DATA.derived.yearlyTotalsModule;
  const total = yrs.map(y => (ytC[y]||0) + (ytM[y]||0));
  const active = yrs.map(y => (DATA.derived.activeCell[y]||0) + (DATA.derived.activeModule[y]||0));
  // Top-3 share over time (combined)
  const top3 = yrs.map(y => {
    let allCo = {};
    DATA.cellYearly.filter(r => r.year===y).forEach(r => allCo[r.company] = (allCo[r.company]||0)+r.mw);
    DATA.moduleYearly.filter(r => r.year===y).forEach(r => allCo[r.company] = (allCo[r.company]||0)+r.mw);
    const vals = Object.values(allCo).sort((a,b)=>b-a);
    const tot = vals.reduce((s,v)=>s+v, 0);
    return tot ? vals.slice(0,3).reduce((s,v)=>s+v,0)/tot*100 : 0;
  });
  const avgSize = yrs.map((y,i) => active[i] ? total[i]/active[i] : 0);

  const items = [
    { l: 'Total MW (cell + module)', v: fmtMW(total[3]), sub: '2025 · all manufacturers', d: total, color: FT.ink },
    { l: 'Active manufacturers', v: active[3], sub: '2025 · cell + module distinct', d: active, color: FT.olive },
    { l: 'Top-3 combined share', v: top3[3].toFixed(0)+'%', sub: '2025 · down from '+top3[0].toFixed(0)+'% in 2022', d: top3, color: FT.gold },
    { l: 'Avg company size, MW', v: fmtMW(avgSize[3]), sub: '2025 · total ÷ active manufacturers', d: avgSize, color: FT.teal },
  ];
  ['mini1','mini2','mini3','mini4'].forEach((id, i) => {
    const it = items[i];
    document.getElementById(id).innerHTML = `
      <div class="kpi-eyebrow">${it.l}</div>
      <div class="kpi-figure" style="font-size: 22px;">${it.v}</div>
      <div class="kpi-delta" style="font-size: 10.5px;">${it.sub}</div>
      <div style="margin-top: 4px;">${svgSpark(it.d, { color: it.color, w: 160, h: 26, sw: 1.6, dot: true })}</div>
    `;
  });
}

// ────────────────────────────────────────────────────────────
// 4 · Leaderboard — rich columns, sortable
// ────────────────────────────────────────────────────────────
let lbSortField = 'total_mw';
let lbSortDir = -1;
function renderLeaderboard() {
  const segs = activeSegments();
  let rows = [];
  segs.forEach(seg => {
    companiesForSeg(seg).forEach(c => rows.push({...c, seg}));
  });
  // build combined: if same name in both segments, keep both rows (it's informative)
  if (STATE.lbYear !== 'all') {
    const y = +STATE.lbYear;
    rows = rows.map(c => ({...c, year_mw: c.by_year[y]||0})).filter(c => c.year_mw > 0);
  } else {
    rows = rows.map(c => ({...c, year_mw: c.total_mw}));
  }
  if (searchActive()) rows = rows.filter(c => matchesSearch(c.name));

  rows.sort((a,b) => {
    const av = a[lbSortField], bv = b[lbSortField];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === 'string') return lbSortDir * av.localeCompare(bv);
    return lbSortDir * (av - bv);
  });

  const tbl = document.getElementById('leaderboard');
  const showYearMW = STATE.lbYear !== 'all';
  const yearLabel = showYearMW ? STATE.lbYear : 'All-time';
  const maxVal = Math.max(...rows.map(r => r.year_mw || 0), 1);

  const headers = [
    { k: 'rank', label: '#', cls: 'rank-cell', sortable: false },
    { k: 'name', label: 'Company', cls: 'co-name' },
    { k: 'seg', label: 'Seg' },
    { k: 'is_almm', label: 'ALMM' },
    { k: 'by_year_2024', label: '2024 MW', cls: 'num' },
    { k: 'by_year_2025', label: '2025 MW', cls: 'num' },
    { k: 'by_year_2026', label: '2026 YTD', cls: 'num' },
    { k: 'total_mw', label: 'All-time MW', cls: 'num' },
    { k: 'share_seg', label: '% Segment 2025', cls: 'num' },
    { k: 'share_dcr', label: '% DCR 2025', cls: 'num' },
    { k: 'cagr_pct', label: 'CAGR', cls: 'num' },
    { k: 'sparkline', label: 'Monthly · 28-mo', sortable: false },
  ];

  // Compute share columns and 2024/2025/2026 columns lazily
  rows = rows.map(r => {
    const sm = DATA.derived[r.seg==='cell'?'shareSegCell':'shareSegModule'][r.name] || {};
    return {
      ...r,
      by_year_2024: r.by_year[2024] || 0,
      by_year_2025: r.by_year[2025] || 0,
      by_year_2026: r.by_year[2026] || 0,
      share_seg: sm[2025] || 0,
      share_dcr: (DATA.derived.shareDCR[r.name]||{})[2025] || 0,
    };
  });

  document.getElementById('lbCount').textContent = `${rows.length} companies`;

  tbl.innerHTML = `
    <thead><tr>
      ${headers.map(h => `<th data-sort="${h.k}" class="${h.cls||''}">${h.label}${lbSortField===h.k ? ` <span class="sort-ind">${lbSortDir===-1?'▼':'▲'}</span>`:''}</th>`).join('')}
    </tr></thead>
    <tbody>
      ${rows.slice(0, 200).map((c, i) => {
        // monthly sparkline: pull last 28 months from monthlyPerCo data
        const series = (DATA.derived[c.seg==='cell'?'monthlyPerCoCell':'monthlyPerCoModule'])[c.name] || [];
        const last28 = series.slice(-28).map(x => x.mw);
        const spark = last28.length ? svgSpark(last28, { color: SEG_COLOR[c.seg], w: 90, h: 22, sw: 1.4, fill: SEG_COLOR[c.seg] }) : '';
        const barW = (c.year_mw / maxVal * 60).toFixed(1);
        return `<tr data-co="${c.name}" data-seg="${c.seg}" ${c.name===STATE.selectedCompany?'class="selected"':''}>
          <td class="rank-cell">${i+1}</td>
          <td class="co-name">${c.name}</td>
          <td><span class="tag ${c.seg}">${c.seg.slice(0,3)}</span></td>
          <td>${c.is_almm?'<span class="tag almm">ALMM</span>':'<span class="tag no-almm">non</span>'}</td>
          <td class="num">${c.by_year_2024?fmtMW(c.by_year_2024):'—'}</td>
          <td class="num">${c.by_year_2025?fmtMW(c.by_year_2025):'—'}</td>
          <td class="num">${c.by_year_2026?fmtMW(c.by_year_2026):'—'}</td>
          <td class="num"><div style="display:flex; align-items:center; gap:6px; justify-content:flex-end;"><span class="iv-bar ${c.seg}" style="width: ${barW}px;"></span>${fmtMW(c.total_mw)}</div></td>
          <td class="num">${c.share_seg ? c.share_seg.toFixed(1)+'%' : '—'}</td>
          <td class="num">${c.share_dcr ? c.share_dcr.toFixed(1)+'%' : '—'}</td>
          <td class="num" style="color: ${c.cagr_pct==null?FT.inkFaint:(c.cagr_pct>0?FT.green:FT.claret)}">${c.cagr_pct==null?'—':fmtPct(c.cagr_pct)}</td>
          <td>${spark}</td>
        </tr>`;
      }).join('')}
    </tbody>`;

  tbl.querySelectorAll('th[data-sort]').forEach(th => {
    if (th.dataset.sort === 'rank' || th.dataset.sort === 'sparkline') return;
    th.addEventListener('click', () => {
      if (lbSortField === th.dataset.sort) lbSortDir = -lbSortDir;
      else { lbSortField = th.dataset.sort; lbSortDir = (th.dataset.sort==='name')?1:-1; }
      renderLeaderboard();
    });
  });
  tbl.querySelectorAll('tbody tr').forEach(tr => tr.addEventListener('click', () => {
    STATE.selectedCompany = tr.dataset.co;
    renderLeaderboard();
    renderDrill(tr.dataset.co, tr.dataset.seg);
  }));
}

// ────────────────────────────────────────────────────────────
// 5 · Drill panel
// ────────────────────────────────────────────────────────────
function renderDrill(name, seg) {
  const c = companiesForSeg(seg).find(x => x.name === name);
  if (!c) return;
  const segs_seen = ['cell','module'].filter(s => companiesForSeg(s).some(x => x.name===name));
  const yrs = [2022,2023,2024,2025,2026];
  const ytC = DATA.derived.yearlyTotalsCell, ytM = DATA.derived.yearlyTotalsModule;
  const segTotalByYr = (s, y) => s==='cell' ? (ytC[y]||0) : (ytM[y]||0);
  const ranks = {};
  yrs.forEach(y => {
    const rows = yearlyForSeg(seg).filter(r => r.year === y).sort((a,b) => b.mw-a.mw);
    const idx = rows.findIndex(r => r.company === name);
    if (idx >= 0) ranks[y] = idx + 1;
  });

  // Monthly series
  const monthly = (DATA.derived[seg==='cell'?'monthlyPerCoCell':'monthlyPerCoModule'])[name] || [];
  const mvals = monthly.map(p => p.mw);
  const mlabels = monthly.map(p => p.ym);
  const SPARK_W = 380, SPARK_H = 80;
  const sparkBig = svgSpark(mvals, { color: SEG_COLOR[seg], w: SPARK_W, h: SPARK_H, sw: 2, fill: SEG_COLOR[seg], dot: true });
  // Year ticks: find first index of each year
  const yrStarts = {};
  monthly.forEach((p, i) => { const y = p.ym.slice(0,4); if (!(y in yrStarts)) yrStarts[y] = i; });
  const yrAxisHtml = `<div style="display: flex; margin-top: 2px; position: relative; height: 14px;">
    ${Object.entries(yrStarts).map(([y, i]) => {
      const left = (i / Math.max(monthly.length - 1, 1)) * 100;
      return `<div style="position: absolute; left: ${left}%; transform: translateX(0); border-left: 1px solid var(--rule); padding-left: 4px; font-size: 10px; color: var(--ink-mid); font-family: 'Inter', sans-serif;">${y === '2026' ? '\'26 YTD' : "'" + y.slice(-2)}</div>`;
    }).join('')}
  </div>`;

  // Share-of-segment over time
  const shareTrend = yrs.map(y => {
    const tot = segTotalByYr(seg, y); return tot ? (c.by_year[y]||0)/tot*100 : 0;
  });
  const shareSpark = svgSpark(shareTrend, { color: FT.gold, w: 200, h: 50, sw: 1.8, dot: true });

  // Annual MW
  const annualVals = yrs.map(y => c.by_year[y]||0);
  const maxA = Math.max(...annualVals,1);

  // Annual comparison table data: Year · MW · % Segment · % DCR · Rank
  const totDCRByYr = DATA.derived.yearlyTotalDCR;
  const annualRows = yrs.map((y, i) => {
    const mw = c.by_year[y] || 0;
    const segShare = segTotalByYr(seg, y) ? (mw / segTotalByYr(seg, y) * 100) : 0;
    const dcrShare = totDCRByYr[y] ? (mw / totDCRByYr[y] * 100) : 0;
    return { year: y, mw, segShare, dcrShare, rank: ranks[y] || null };
  });
  const annualCmpTable = `
    <div style="margin-top: 12px;">
      <h5 style="margin: 0 0 6px 0;">Year-by-year position</h5>
      <table class="data-tbl" style="width: 100%;">
        <thead><tr><th class="left">Year</th><th class="num">MW</th><th class="num">% ${seg}</th><th class="num">% total DCR</th><th class="num">Rank in ${seg}</th></tr></thead>
        <tbody>
          ${annualRows.map(r => `<tr>
            <td class="left" style="font-weight: 700; ${r.year===LAST_YEAR && LAST_MONTH < 12 ?'color: var(--claret);':''}">${r.year}${r.year===LAST_YEAR && LAST_MONTH < 12 ?' YTD':''}</td>
            <td class="num">${r.mw===0?'·':fmtMW(r.mw)}</td>
            <td class="num">${r.segShare===0?'·':r.segShare.toFixed(1)+'%'}</td>
            <td class="num">${r.dcrShare===0?'·':r.dcrShare.toFixed(1)+'%'}</td>
            <td class="num" style="font-weight: 700; color: ${r.rank?'var(--claret)':'var(--ink-faint)'};">${r.rank?'#'+r.rank:'—'}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>`;

  // Build monthly tables (one per segment company actually operates in)
  function buildMonthlyTable(segKey, coName) {
    const seriesData = (DATA.derived[segKey==='cell'?'monthlyPerCoCell':'monthlyPerCoModule'])[coName] || [];
    if (!seriesData.length) return '';
    // Group by year, then by month index 1-12
    const grouped = {};
    seriesData.forEach(p => {
      const y = +p.ym.slice(0,4); const m = +p.ym.slice(5,7);
      grouped[y] = grouped[y] || Array(12).fill(0);
      grouped[y][m-1] = p.mw;
    });
    const yrs = Object.keys(grouped).map(y=>+y).sort();
    // Trim to only years with non-zero output
    const nonZeroYrs = yrs.filter(y => grouped[y].some(v => v > 0));
    if (!nonZeroYrs.length) return '';

    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const segColor = SEG_COLOR[segKey];
    const granularity = STATE.monVolGran || 'monthly';
    const isQ = granularity === 'quarterly';

    // Build column structure: either 12 months or 4 quarters
    const cols = isQ
      ? [{ label: 'Q1', months: [0,1,2] }, { label: 'Q2', months: [3,4,5] }, { label: 'Q3', months: [6,7,8] }, { label: 'Q4', months: [9,10,11] }]
      : months.map((m, i) => ({ label: m.slice(0,1), months: [i] }));

    const head = `<tr>
      <th class="left">Year</th>
      ${cols.map(c => `<th class="num" style="width: ${isQ?'72':'38'}px;">${c.label}</th>`).join('')}
      <th class="num annual">Total</th>
    </tr>`;

    const body = nonZeroYrs.map(y => {
      const vals = grouped[y];
      const lastMonthForYear = (y === LAST_YEAR) ? LAST_MONTH : 12;
      const yt = vals.reduce((s,v)=>s+v, 0);
      const cells = cols.map(col => {
        // Check if all months in this column are future
        const validMonths = col.months.filter(mi => mi+1 <= lastMonthForYear);
        if (validMonths.length === 0) {
          return `<td class="future-month" style="background: transparent; border-bottom: none; padding: 0;"></td>`;
        }
        const v = validMonths.reduce((s, mi) => s + vals[mi], 0);
        const partial = isQ && validMonths.length < col.months.length;
        return `<td class="num ${v===0?'zero':''}" data-csv="${v.toFixed(2)}" title="${col.months.map(mi=>months[mi]+' '+y).join(', ')}">${v===0?'·':v.toFixed(v<10?1:0)}${partial?'*':''}</td>`;
      }).join('');
      return `<tr>
        <td class="left" style="font-weight: 700; ${y===LAST_YEAR && LAST_MONTH < 12 ?'color: var(--claret);':''}">${y}${y===LAST_YEAR && LAST_MONTH < 12 ?' YTD '+months[LAST_MONTH-1]:''}</td>
        ${cells}
        <td class="num annual" data-csv="${yt.toFixed(2)}">${yt===0?'·':fmtMW(yt)}</td>
      </tr>`;
    }).join('');

    // Avg row (across active years)
    const colSums = cols.map(() => 0);
    const colCounts = cols.map(() => 0);
    nonZeroYrs.forEach(y => {
      const lastMonthForYear = (y === LAST_YEAR) ? LAST_MONTH : 12;
      cols.forEach((col, ci) => {
        const validMonths = col.months.filter(mi => mi+1 <= lastMonthForYear);
        if (validMonths.length === 0) return;
        const v = validMonths.reduce((s, mi) => s + grouped[y][mi], 0);
        if (v > 0) { colSums[ci] += v; colCounts[ci] += 1; }
      });
    });
    const colAvgs = colSums.map((s, i) => colCounts[i] ? s/colCounts[i] : 0);
    const grandTot = nonZeroYrs.reduce((s,y) => s + grouped[y].reduce((a,b)=>a+b,0), 0);
    const footer = `<tr class="tot-row">
      <td class="left">Avg (active ${isQ?'Qs':'mos'})</td>
      ${colAvgs.map(v => `<td class="num ${v===0?'zero':''}" data-csv="${v.toFixed(2)}">${v===0?'·':v.toFixed(v<10?1:0)}</td>`).join('')}
      <td class="num annual" data-csv="${grandTot.toFixed(2)}">${fmtMW(grandTot)}</td>
    </tr>`;
    return `
      <div style="margin-top: 14px;">
        <h5><span style="color: ${segColor}; font-weight: 700;">■</span> ${segKey==='cell'?'Cell':'Module'} · ${isQ?'quarterly':'monthly'} MW</h5>
        <div style="overflow-x: auto;"><table class="data-tbl" id="drillMonthly_${segKey}" style="min-width: 100%;"><thead>${head}</thead><tbody>${body}${footer}</tbody></table></div>
      </div>`;
  }
  const monthlyTablesHtml = segs_seen.map(s => buildMonthlyTable(s, name)).join('');
  const csvBtn = `<button class="csv-btn" onclick="(function(){const tbls=document.querySelectorAll('#drillPanel table.data-tbl');let csv='';tbls.forEach((t,i)=>{const seg=t.id.includes('cell')?'CELL':'MODULE';csv+='# '+seg+'\\n';Array.from(t.querySelectorAll('tr')).forEach(tr=>{csv+=Array.from(tr.querySelectorAll('th,td')).map(c=>(c.dataset.csv!=null?c.dataset.csv:c.textContent.trim().replace(/\\s+/g,' '))).join(',')+'\\n';});csv+='\\n';});const blob=new Blob([csv],{type:'text/csv'});const u=URL.createObjectURL(blob);const a=document.createElement('a');a.href=u;a.download='${name.replace(/[^a-zA-Z0-9]/g,'_')}_monthly.csv';a.click();})()" style="margin-left: 8px;">Download CSV</button>`;

  document.getElementById('drillPanel').innerHTML = `
    <div class="drill-panel">
      <div class="drill-head">
        <div>
          <h3>${c.name}</h3>
          <div class="sub">
            <span class="tag ${seg}">${seg}</span>
            ${c.is_almm?'<span class="tag almm">ALMM</span>':'<span class="tag no-almm">non-ALMM</span>'}
            ${segs_seen.length>1?'<span class="tag dual">DUAL-SEG</span>':''}
            · First production ${c.first_year} · ${c.years_active} active years
          </div>
        </div>
        <div>${csvBtn}<button class="drill-close" onclick="document.getElementById('drillPanel').innerHTML=''; STATE.selectedCompany=null; renderLeaderboard();" style="margin-left: 8px;">Close</button></div>
      </div>
      <div class="drill-body">
        <div>
          <div class="block-title" style="font-size: 13px;">Monthly manufactured MW · ${monthly[0]?.ym} → ${monthly[monthly.length-1]?.ym}</div>
          <div style="margin: 8px 0;">${sparkBig}${yrAxisHtml}</div>
          <hr class="rule">
          <div class="block-title" style="font-size: 13px;">Annual MW (with rank below)</div>
          <div style="display: flex; gap: 8px; align-items: flex-end; height: 100px; margin: 10px 0;">
            ${annualVals.map((v,i) => { const h = (v/maxA*84) || 2; return `<div style="flex:1; display: flex; flex-direction: column; align-items: center; gap: 3px;">
              <div style="font-size: 10px; color: var(--ink-mid); font-variant-numeric: tabular-nums;">${v ? fmtMW(v) : ''}</div>
              <div style="width: 100%; background: ${SEG_COLOR[seg]}; height: ${h}px;"></div>
              <div style="font-size: 10px; color: var(--ink); font-weight: 600;">${yrs[i]===2026?'\'26':yrs[i].toString().slice(-2)}</div>
              <div style="font-size: 10px; color: var(--claret); font-weight: 700;">${ranks[yrs[i]]?'#'+ranks[yrs[i]]:'—'}</div>
            </div>`}).join('')}
          </div>
        </div>
        <div>
          <div class="drill-stats">
            <div class="drill-stat"><div class="l">All-time MW</div><div class="v">${fmtMW(c.total_mw)}</div></div>
            <div class="drill-stat"><div class="l">2025 MW</div><div class="v">${fmtMW(c.by_year[2025]||0)}</div></div>
            <div class="drill-stat"><div class="l">2026 YTD</div><div class="v">${fmtMW(c.by_year[2026]||0)}</div></div>
            <div class="drill-stat"><div class="l">CAGR (full years)</div><div class="v" style="color: ${c.cagr_pct==null?FT.inkMid:(c.cagr_pct>0?FT.green:FT.claret)}">${c.cagr_pct==null?'—':fmtPct(c.cagr_pct)}</div></div>
          </div>
          ${annualCmpTable}
          ${segs_seen.length>1?(()=>{
            const o = companiesForSeg(segs_seen.find(s=>s!==seg)).find(x=>x.name===name);
            if (!o) return '';
            return `<hr class="rule"><div class="block-title" style="font-size: 13px;">Other segment · ${segs_seen.find(s=>s!==seg)}</div>
              <div style="display: flex; gap: 12px; align-items: baseline; margin-top: 6px;">
                <div><span class="kpi-eyebrow">All-time</span><div class="kpi-figure" style="font-size: 18px;">${fmtMW(o.total_mw)}</div></div>
                <div><span class="kpi-eyebrow">2025</span><div class="kpi-figure" style="font-size: 18px;">${fmtMW(o.by_year[2025]||0)}</div></div>
              </div>`;
          })():''}
        </div>
      </div>
      <div class="drill-monthly">
        <div style="display: flex; justify-content: space-between; align-items: baseline;">
          <h5 style="margin: 0;">Monthly volumes, every month since first production</h5>
          <span class="muted">12 calendar columns × ${segs_seen.length===1?'one year per row':'one per row per segment'} · zero values dotted</span>
        </div>
        ${monthlyTablesHtml}
      </div>
    </div>`;
  const dp = document.getElementById('drillPanel');
  if (dp && typeof dp.scrollIntoView === 'function') dp.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ────────────────────────────────────────────────────────────
// 6 · 3a Share of segment over time (stacked 100%)
// ────────────────────────────────────────────────────────────
function renderShareSeg() {
  destroyChart('chartShareSeg');
  const ctx = document.getElementById('chartShareSeg').getContext('2d');
  const seg = STATE.shareSeg;
  const yrs = [2022,2023,2024,2025,2026];
  const comps = companiesForSeg(seg).slice(0, 10);
  const compNames = comps.map(c => c.name);
  const sm = DATA.derived[seg==='cell'?'shareSegCell':'shareSegModule'];

  const datasets = comps.map((c, i) => ({
    label: c.name,
    data: yrs.map(y => (sm[c.name]||{})[y] || 0),
    backgroundColor: colorFor(c.name, i),
    borderColor: FT.paper, borderWidth: 1,
    stack: 's',
  }));
  // Others
  datasets.push({
    label: 'Others',
    data: yrs.map(y => {
      const taken = compNames.reduce((s, n) => s + ((sm[n]||{})[y] || 0), 0);
      return Math.max(0, 100 - taken);
    }),
    backgroundColor: '#B3A9A0', borderColor: FT.paper, borderWidth: 1, stack: 's',
  });

  // In-chart segment labels — only for big slices in the latest year, kept INSIDE the bar
  const inBarLabels = {
    id: 'inBarLabels',
    afterDatasetsDraw(chart) {
      const { ctx, chartArea, scales } = chart;
      const lastIdx = yrs.length - 1;
      const x = scales.x.getPixelForValue(lastIdx);
      let cumY = 100;
      ctx.save();
      ctx.font = "700 10.5px 'Inter', sans-serif"; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      chart.data.datasets.forEach((ds) => {
        const v = ds.data[lastIdx];
        const segTop = scales.y.getPixelForValue(cumY);
        const segBot = scales.y.getPixelForValue(cumY - v);
        cumY -= v;
        // Only label segments that are tall enough to fit text comfortably
        if (v < 6) return;
        const midY = (segTop + segBot) / 2;
        const barW = chart.getDatasetMeta(0).data[lastIdx].width;
        // Pick text color for contrast: dark on light backgrounds, light on dark ones
        ctx.fillStyle = '#FFFFFF';
        ctx.fillText(`${v.toFixed(0)}%`, x, midY);
      });
      ctx.restore();
    }
  };

  const opts = baseAxisOpts();
  opts.layout = { padding: { right: 8 } };
  opts.scales.x.stacked = true; opts.scales.y.stacked = true; opts.scales.y.max = 100;
  opts.scales.y.ticks.callback = v => v + '%';
  opts.plugins.tooltip.callbacks = { label: c => `${c.dataset.label}: ${c.parsed.y.toFixed(1)}%` };

  CHARTS.chartShareSeg = new Chart(ctx, { type: 'bar', data: { labels: yrs.map(y=>y===2026?'2026 YTD':y), datasets }, options: opts, plugins: [inBarLabels] });

  // Below-chart legend with 2025 shares
  const legend = document.getElementById('shareSegLegend');
  if (legend) {
    const items = datasets.map(ds => ({ name: ds.label, color: ds.backgroundColor, share: ds.data[3] || 0 }));
    legend.innerHTML = items.map(it => `<div class="lg-item">
      <span class="lg-swatch" style="background: ${it.color};"></span>
      <span class="lg-name" title="${it.name}">${it.name}</span>
      <span class="lg-pct">${it.share.toFixed(1)}%</span>
    </div>`).join('');
  }
}

// ────────────────────────────────────────────────────────────
// 7 · 3b Share of total DCR output (cell + module combined)
// ────────────────────────────────────────────────────────────
function renderShareDCR() {
  destroyChart('chartShareDCR');
  const ctx = document.getElementById('chartShareDCR').getContext('2d');
  const yrs = [2022,2023,2024,2025,2026];

  // Aggregate per company across both segments
  const allCo = {};
  DATA.cellYearly.forEach(r => { allCo[r.company] = allCo[r.company] || {}; allCo[r.company][r.year] = (allCo[r.company][r.year]||0) + r.mw; });
  DATA.moduleYearly.forEach(r => { allCo[r.company] = allCo[r.company] || {}; allCo[r.company][r.year] = (allCo[r.company][r.year]||0) + r.mw; });

  // rank by 2025
  const ranked = Object.entries(allCo).map(([name, byYr]) => ({ name, byYr, _25: byYr[2025]||0 })).sort((a,b) => b._25 - a._25);
  const top = ranked.slice(0, 10);

  const totByYr = DATA.derived.yearlyTotalDCR;

  const datasets = top.map((c, i) => ({
    label: c.name,
    data: yrs.map(y => totByYr[y] ? (c.byYr[y]||0)/totByYr[y]*100 : 0),
    backgroundColor: colorFor(c.name, i),
    borderColor: FT.paper, borderWidth: 1, stack: 's',
  }));
  datasets.push({
    label: 'Others',
    data: yrs.map(y => {
      const taken = top.reduce((s, c) => s + (totByYr[y] ? (c.byYr[y]||0)/totByYr[y]*100 : 0), 0);
      return Math.max(0, 100 - taken);
    }),
    backgroundColor: '#B3A9A0', borderColor: FT.paper, borderWidth: 1, stack: 's',
  });

  const inBarLabels = {
    id: 'inBarLabels2',
    afterDatasetsDraw(chart) {
      const { ctx, scales } = chart;
      const lastIdx = yrs.length - 1;
      const x = scales.x.getPixelForValue(lastIdx);
      let cumY = 100;
      ctx.save();
      ctx.font = "700 10.5px 'Inter', sans-serif"; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      chart.data.datasets.forEach(ds => {
        const v = ds.data[lastIdx];
        const segTop = scales.y.getPixelForValue(cumY);
        const segBot = scales.y.getPixelForValue(cumY - v);
        cumY -= v;
        if (v < 6) return;
        const midY = (segTop + segBot) / 2;
        ctx.fillStyle = '#FFFFFF';
        ctx.fillText(`${v.toFixed(0)}%`, x, midY);
      });
      ctx.restore();
    }
  };

  const opts = baseAxisOpts();
  opts.layout = { padding: { right: 8 } };
  opts.scales.x.stacked = true; opts.scales.y.stacked = true; opts.scales.y.max = 100;
  opts.scales.y.ticks.callback = v => v + '%';
  opts.plugins.tooltip.callbacks = { label: c => `${c.dataset.label}: ${c.parsed.y.toFixed(1)}%` };

  CHARTS.chartShareDCR = new Chart(ctx, { type: 'bar', data: { labels: yrs.map(y=>y===2026?'2026 YTD':y), datasets }, options: opts, plugins: [inBarLabels] });

  const legend = document.getElementById('shareDCRLegend');
  if (legend) {
    const items = datasets.map(ds => ({ name: ds.label, color: ds.backgroundColor, share: ds.data[3] || 0 }));
    legend.innerHTML = items.map(it => `<div class="lg-item">
      <span class="lg-swatch" style="background: ${it.color};"></span>
      <span class="lg-name" title="${it.name}">${it.name}</span>
      <span class="lg-pct">${it.share.toFixed(1)}%</span>
    </div>`).join('');
  }
}

// ────────────────────────────────────────────────────────────
// 8 · 3c Cell-vs-module mix for dual-segment companies
// ────────────────────────────────────────────────────────────
function renderDual() {
  destroyChart('chartDual');
  const ctx = document.getElementById('chartDual').getContext('2d');
  const y = STATE.dualYr;
  const split = DATA.derived.dualSegmentSplit;
  // build sorted list by total for selected year
  const rows = Object.entries(split).map(([name, d]) => ({
    name, cell: d.cell[y]||0, module: d.module[y]||0, total: d.total[y]||0
  })).filter(r => r.total > 0).sort((a,b) => b.total - a.total);

  const labels = rows.map(r => r.name.length>32 ? r.name.slice(0,30)+'…' : r.name);

  const opts = baseAxisOpts();
  opts.indexAxis = 'y';
  opts.scales = {
    x: { stacked: false, grid: { color: 'rgba(38,42,51,0.06)' }, ticks: { color: FT.inkMid, callback: v => v>=1000?(v/1000).toFixed(1)+'k':v } },
    y: { stacked: false, grid: { display: false }, ticks: { color: FT.ink, font: { size: 11, weight: 500 } } }
  };
  opts.plugins.tooltip.callbacks = { label: c => `${c.dataset.label}: ${fmtMWfull(c.parsed.x)} MW` };

  CHARTS.chartDual = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: 'Cell MW', data: rows.map(r=>r.cell), backgroundColor: FT.cell },
        { label: 'Module MW', data: rows.map(r=>r.module), backgroundColor: FT.module },
      ]
    },
    options: opts,
  });
}

// ────────────────────────────────────────────────────────────
// 9 · 3d Monthly share oscillation
// ────────────────────────────────────────────────────────────
function renderOscillation() {
  destroyChart('chartOscillation');
  const ctx = document.getElementById('chartOscillation').getContext('2d');
  const seg = STATE.oscSeg;
  const ms = DATA.derived[seg==='cell'?'monthlyShareCell':'monthlyShareModule'];

  // pick top 5 by 2025 MW
  const top5 = companiesForSeg(seg).slice(0, 5);
  // Get latest 24 months
  const monthsAll = top5[0] ? (ms[top5[0].name] || []).map(p => p.ym) : [];
  const months = monthsAll.slice(-24);

  const datasets = top5.map((c, i) => {
    const series = ms[c.name] || [];
    const last24 = series.slice(-24);
    return {
      label: c.name.length > 26 ? c.name.slice(0,24)+'…' : c.name,
      _directLabel: c.name.split(' ')[0],
      data: last24.map(p => p.share),
      borderColor: colorFor(c.name, i), backgroundColor: colorFor(c.name, i)+'1A',
      fill: false, tension: 0.32, borderWidth: 2, pointRadius: 0,
    };
  });

  const opts = baseAxisOpts();
  opts.layout = { padding: { right: 90 } };
  opts.scales.x.ticks.maxTicksLimit = 8;
  opts.scales.y.ticks.callback = v => v + '%';
  opts.plugins.tooltip.callbacks = { label: c => `${c.dataset.label}: ${c.parsed.y.toFixed(1)}%` };
  CHARTS.chartOscillation = new Chart(ctx, { type: 'line', data: { labels: months, datasets }, options: opts });
}

// ────────────────────────────────────────────────────────────
// 10 · Small multiples — per-company monthly mini-charts
// ────────────────────────────────────────────────────────────
function renderSmallMultiples() {
  const grid = document.getElementById('smGrid');
  const allCo = [];
  ['cell','module'].forEach(seg => {
    if (STATE.smSeg === 'both' || STATE.smSeg === seg) {
      companiesForSeg(seg).forEach(c => allCo.push({...c, seg}));
    }
  });
  // sort
  if (STATE.smSort === 'size_25') allCo.sort((a,b) => (b.by_year[2025]||0) - (a.by_year[2025]||0));
  else if (STATE.smSort === 'size_all') allCo.sort((a,b) => b.total_mw - a.total_mw);
  else if (STATE.smSort === 'growth') allCo.sort((a,b) => (b.cagr_pct||-Infinity) - (a.cagr_pct||-Infinity));

  // Apply search filter; otherwise top 24
  const top24 = searchActive() ? applySearchFilter(allCo) : allCo.slice(0, 24);
  if (!top24.length) {
    grid.innerHTML = `<div style="grid-column: 1/-1; padding: 28px 0; text-align: center; color: var(--ink-mid); font-style: italic;">No companies match "${STATE.search}".</div>`;
    return;
  }
  const ytC = DATA.derived.yearlyTotalsCell, ytM = DATA.derived.yearlyTotalsModule;

  // shared y-axis: find max monthly across selected
  let globalMax = 0;
  const seriesMap = {};
  top24.forEach(c => {
    const series = (DATA.derived[c.seg==='cell'?'monthlyPerCoCell':'monthlyPerCoModule'])[c.name] || [];
    const last28 = series.slice(-28);
    seriesMap[c.name+'|'+c.seg] = last28;
    last28.forEach(p => { if (p.mw > globalMax) globalMax = p.mw; });
  });

  grid.innerHTML = top24.map(c => {
    const series = seriesMap[c.name+'|'+c.seg];
    const vals = series.map(p => p.mw);
    const labels = series.map(p => p.ym);
    const segTot25 = c.seg==='cell' ? ytC[2025] : ytM[2025];
    const shareSeg = segTot25 ? (c.by_year[2025]||0)/segTot25*100 : 0;
    const v24 = c.by_year[2024]||0, v25 = c.by_year[2025]||0;
    const delta = v24 ? ((v25-v24)/v24*100) : null;

    // SVG mini sparkline with shared y-scale + filled
    const W = 180, H = 56, pad = 4;
    const yMax = globalMax || 1;
    const pts = vals.map((v, i) => `${pad + (i / (vals.length - 1 || 1)) * (W - 2*pad)},${H - pad - (v / yMax) * (H - 2*pad)}`);
    const path = pts.length ? ('M' + pts.join('L')) : '';
    const areaPath = path ? (path + ` L${W-pad},${H-pad} L${pad},${H-pad} Z`) : '';

    return `<div class="sm-tile" data-co="${c.name}" data-seg="${c.seg}">
      <div class="sm-tile-head">
        <div class="sm-tile-name" title="${c.name}">${c.name}</div>
        <div class="sm-tile-meta">
          <span class="mw">${fmtMW(c.by_year[2025]||0)} MW</span>
          <span class="tag ${c.seg}" style="font-size: 8.5px;">${c.seg.slice(0,3)}</span>
          ${c.is_almm?'<span class="tag almm" style="font-size: 8.5px;">A</span>':''}
        </div>
        <div class="sm-tile-foot">
          <span>${shareSeg.toFixed(1)}% of ${c.seg}</span>
          <span class="delta ${delta>0?'up':delta<0?'down':''}">${delta==null?'new':fmtPct(delta)}</span>
        </div>
      </div>
      <div class="sm-tile-chart">
        <svg width="100%" height="${H}" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
          <path d="${areaPath}" fill="${SEG_COLOR[c.seg]}" opacity="0.16"/>
          <path d="${path}" stroke="${SEG_COLOR[c.seg]}" stroke-width="1.4" fill="none" stroke-linejoin="round"/>
          <line x1="${pad}" y1="${H-pad}" x2="${W-pad}" y2="${H-pad}" stroke="${FT.rule}" stroke-width="0.5"/>
        </svg>
      </div>
    </div>`;
  }).join('');

  grid.querySelectorAll('.sm-tile').forEach(t => t.addEventListener('click', () => {
    STATE.selectedCompany = t.dataset.co;
    renderLeaderboard();
    renderDrill(t.dataset.co, t.dataset.seg);
  }));
}

// ────────────────────────────────────────────────────────────
// 11 · Monthly mfg vs sold
// ────────────────────────────────────────────────────────────
function renderMonthlyMfgSold() {
  destroyChart('chartMonthlyMfgSold');
  const ctx = document.getElementById('chartMonthlyMfgSold').getContext('2d');
  const seg = STATE.monSeg;
  const agg = aggMonthlyForSeg(seg);
  const byKey = {};
  agg.forEach(r => {
    const k = r.year + '-' + String(r.month).padStart(2,'0');
    byKey[k] = byKey[k] || { ym: k };
    byKey[k][r.metric] = r.mw;
  });
  const sorted = Object.values(byKey).sort((a,b) => a.ym.localeCompare(b.ym));
  const labels = sorted.map(r => r.ym);
  const mfg = sorted.map(r => r[`${seg}_manufactured_mw`]||0);
  const sold = sorted.map(r => r[`${seg}_sold_mw`]||0);
  const gap = mfg.map((m,i) => Math.max(0, m - sold[i]));

  const opts = baseAxisOpts();
  opts.layout = { padding: { right: 72 } };
  opts.scales.x.ticks.maxTicksLimit = 10;

  CHARTS.chartMonthlyMfgSold = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Build-up', _directLabel: 'Build-up', data: gap, borderColor: FT.olive, backgroundColor: 'rgba(128,111,71,0.32)', fill: 'origin', tension: 0.3, borderWidth: 0, pointRadius: 0, order: 3 },
        { label: 'Manufactured', _directLabel: 'Made', data: mfg, borderColor: FT.green, backgroundColor: 'transparent', fill: false, tension: 0.3, borderWidth: 2, pointRadius: 0, order: 1 },
        { label: 'Sold', _directLabel: 'Sold', data: sold, borderColor: FT.gold, backgroundColor: 'transparent', fill: false, tension: 0.3, borderWidth: 2, pointRadius: 0, order: 2 },
      ]
    },
    options: opts
  });
}

// ────────────────────────────────────────────────────────────
// 12 · Seasonality
// ────────────────────────────────────────────────────────────
function renderSeasonality() {
  destroyChart('chartSeasonality');
  const ctx = document.getElementById('chartSeasonality').getContext('2d');
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const segs = activeSegments();
  const datasets = segs.map(seg => {
    const agg = aggMonthlyForSeg(seg);
    const sums = Array(12).fill(0), counts = Array(12).fill(0);
    agg.forEach(r => {
      if (r.metric === `${seg}_manufactured_mw` && r.mw > 0) { sums[r.month-1] += r.mw; counts[r.month-1] += 1; }
    });
    return {
      label: seg, _directLabel: seg.charAt(0).toUpperCase()+seg.slice(1),
      data: sums.map((s, i) => counts[i]?s/counts[i]:0),
      backgroundColor: SEG_COLOR[seg], borderRadius: 0, barPercentage: 0.7,
    };
  });
  const opts = baseAxisOpts();
  opts.layout = { padding: { right: 40 } };
  CHARTS.chartSeasonality = new Chart(ctx, { type: 'bar', data: { labels: months, datasets }, options: opts });
}

// ────────────────────────────────────────────────────────────
// 13 · Heatmap (FT-palette intensity)
// ────────────────────────────────────────────────────────────
function renderHeatmap() {
  const seg = STATE.heatSeg;
  const monthly = monthlyForSeg(seg).filter(r => r.metric === `${seg}_manufactured_mw` && r.company !== 'All Manufacturers');
  const comps = companiesForSeg(seg).slice(0, 25).map(c => c.name);
  const ymSet = new Set();
  monthly.forEach(r => ymSet.add(r.year + '-' + String(r.month).padStart(2,'0')));
  // Drop future months past LAST_YM
  const yms = Array.from(ymSet).sort().filter(ym => !isFutureYM(ym));
  const lookup = {};
  monthly.forEach(r => { lookup[r.company + '|' + r.year + '-' + String(r.month).padStart(2,'0')] = r.mw; });
  const maxVal = Math.max(...monthly.map(r => r.mw));
  const segColor = SEG_COLOR[seg];

  // Group year-months by year, count months per year
  const yearGroups = [];
  yms.forEach(ym => {
    const y = ym.slice(0, 4);
    let g = yearGroups.find(g => g.year === y);
    if (!g) { g = { year: y, months: [] }; yearGroups.push(g); }
    g.months.push(ym);
  });

  // Build a two-row header: top row spans year groups, bottom row shows compact month labels
  const monthAbbr = ['','J','F','M','A','M','J','J','A','S','O','N','D'];

  const html = `
    <table>
      <thead>
        <tr>
          <th class="heat-co" rowspan="2">Manufacturer</th>
          ${yearGroups.map(g => `<th colspan="${g.months.length}" class="year-group" style="text-align: left; padding: 2px 4px 4px 4px; font-family: 'Source Serif 4', serif; font-size: 12px; font-weight: 700; color: var(--ink); border-bottom: 1px solid var(--rule); letter-spacing: 0;">${g.year}</th>`).join('')}
          <th class="heat-tot" rowspan="2">Total</th>
        </tr>
        <tr>
          ${yearGroups.map(g => g.months.map((ym, i) => {
            const mo = +ym.slice(5,7);
            return `<th style="font-size: 8.5px; color: var(--ink-faint); padding: 0; text-align: center; vertical-align: middle; height: 14px; ${i === 0 ? 'border-left: 1px solid var(--rule);' : ''}">${monthAbbr[mo]}</th>`;
          }).join('')).join('')}
        </tr>
      </thead>
      <tbody>
        ${comps.map(co => {
          let tot = 0;
          let cells = '';
          yearGroups.forEach(g => {
            g.months.forEach((ym, i) => {
              const v = lookup[co + '|' + ym] || 0;
              tot += v;
              const intensity = v === 0 ? 0 : Math.min(1, Math.sqrt(v/maxVal));
              const op = v === 0 ? 0.05 : 0.18 + intensity*0.82;
              const bg = v === 0 ? 'var(--paper-2)' : segColor;
              const lb = i === 0 ? 'border-left: 1px solid var(--rule);' : '';
              cells += `<td style="background: ${bg}; opacity: ${op}; ${lb}" data-tt="${co}|${ym}|${v.toFixed(2)}"></td>`;
            });
          });
          return `<tr>
            <td class="heat-co">${co}</td>
            ${cells}
            <td class="heat-tot">${fmtMW(tot)}</td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>`;
  const w = document.getElementById('heatmapWrap'); w.innerHTML = html;
  w.querySelectorAll('td[data-tt]').forEach(td => {
    td.addEventListener('mouseenter', e => {
      const [co, ym, v] = td.dataset.tt.split('|');
      showTT(`<div class="tt-title">${co}</div><div class="tt-row"><span class="tt-key">Period</span><span class="tt-val">${ym}</span></div><div class="tt-row"><span class="tt-key">MW</span><span class="tt-val">${(+v).toFixed(2)}</span></div>`, e);
    });
    td.addEventListener('mousemove', e => { const html = TT.innerHTML; showTT(html, e); });
    td.addEventListener('mouseleave', hideTT);
  });
}

// ────────────────────────────────────────────────────────────
// 14 · Tile cartogram (FT palette)
// ────────────────────────────────────────────────────────────
const STATE_GRID = {
  'Ladakh': [0, 4], 'Jammu and Kashmir': [1, 3],
  'Himachal Pradesh': [2, 3], 'Punjab': [2, 2], 'Chandigarh': [2, 4],
  'Uttarakhand': [3, 4], 'Haryana': [3, 3], 'Delhi': [3, 5],
  'Sikkim': [3, 7], 'Arunachal Pradesh': [3, 9],
  'Rajasthan': [4, 2], 'Uttar Pradesh': [4, 4], 'Bihar': [4, 6], 'Assam': [4, 8], 'Nagaland': [4, 9],
  'Gujarat': [5, 1], 'Madhya Pradesh': [5, 3], 'Jharkhand': [5, 5], 'West Bengal': [5, 6], 'Meghalaya': [5, 7], 'Manipur': [5, 9],
  'Tripura': [6, 7], 'Dadra and Nagar Haveli and Daman and Diu': [6, 1], 'Maharashtra': [6, 2], 'Chhattisgarh': [6, 4], 'Odisha': [6, 5], 'Mizoram': [6, 9],
  'Goa': [7, 1], 'Telangana': [7, 3], 'Andhra Pradesh': [7, 4],
  'Karnataka': [8, 2], 'Puducherry': [8, 4],
  'Kerala': [9, 2], 'Tamil Nadu': [9, 3], 'Andaman and Nicobar Islands': [9, 6],
};
const STATE_CODES = {
  'Ladakh':'LA','Jammu and Kashmir':'JK','Himachal Pradesh':'HP','Punjab':'PB','Chandigarh':'CH','Uttarakhand':'UK','Haryana':'HR','Delhi':'DL','Sikkim':'SK','Arunachal Pradesh':'AR','Rajasthan':'RJ','Uttar Pradesh':'UP','Bihar':'BR','Assam':'AS','Nagaland':'NL','Gujarat':'GJ','Madhya Pradesh':'MP','Jharkhand':'JH','West Bengal':'WB','Meghalaya':'ML','Manipur':'MN','Tripura':'TR','Dadra and Nagar Haveli and Daman and Diu':'DD','Maharashtra':'MH','Chhattisgarh':'CG','Odisha':'OR','Mizoram':'MZ','Goa':'GA','Telangana':'TG','Andhra Pradesh':'AP','Karnataka':'KA','Puducherry':'PY','Kerala':'KL','Tamil Nadu':'TN','Andaman and Nicobar Islands':'AN'
};

function ftColor(t) {
  // 5-stop FT-feeling scale: paper-2 → tan → olive → claret → deep claret
  if (t <= 0) return '#F7E1CE';
  if (t < 0.2) return '#EFD0A8';
  if (t < 0.45) return '#D4A574';
  if (t < 0.7) return '#B5654F';
  if (t < 0.9) return '#990F3D';
  return '#7A0A30';
}

function renderTileMap() {
  const map = document.getElementById('tileMap');
  let maxRow = 0, maxCol = 0;
  Object.values(STATE_GRID).forEach(([r,c]) => { if (r>maxRow) maxRow=r; if (c>maxCol) maxCol=c; });
  map.style.gridTemplateColumns = `repeat(${maxCol+1}, 1fr)`;
  map.style.gridTemplateRows = `repeat(${maxRow+1}, minmax(40px, 1fr))`;
  const metric = STATE.geoMetric;
  const max = Math.max(...DATA.states.map(s => s[metric]||0));
  const byState = {}; DATA.states.forEach(s => byState[s.state] = s);

  const tiles = [];
  Object.entries(STATE_GRID).forEach(([st, [r,c]]) => {
    const data = byState[st];
    const v = data ? (data[metric]||0) : 0;
    const t = max ? Math.sqrt(v/max) : 0;
    const bg = ftColor(t);
    const code = STATE_CODES[st] || st.slice(0,2).toUpperCase();
    const labelColor = t > 0.5 ? '#FFF1E5' : FT.ink;
    tiles.push(`<div class="state-tile ${data?'has-data':''}" style="grid-row:${r+1}; grid-column:${c+1}; background:${bg}; color:${labelColor};" data-state="${st}">
      <div class="tile-code">${code}</div>
      <div class="tile-val">${v ? (metric==='unclaimed_pct'?v.toFixed(0)+'%':fmtMW(v)) : '·'}</div>
    </div>`);
  });
  map.innerHTML = tiles.join('');

  // legend
  const legendStops = [0, 0.2, 0.45, 0.7, 0.9, 1.0];
  const labels = metric === 'unclaimed_pct' ? ['0%','low','mid','high','peak','—'] : ['—','low','mid','high','high','peak'];
  document.getElementById('tileLegend').innerHTML = `<div style="display: flex; gap: 0; align-items: center;">
    <span style="margin-right: 8px; font-size: 10.5px; color: var(--ink-mid);">${metric==='unclaimed_pct'?'% unclaimed':'MW intensity'}:</span>
    ${legendStops.map((s,i) => `<span style="display: inline-block; width: 28px; height: 12px; background: ${ftColor(s)};"></span>`).join('')}
    <span style="margin-left: 8px; font-size: 10.5px; color: var(--ink-mid);">low → high</span>
  </div>`;

  map.querySelectorAll('.state-tile.has-data').forEach(el => {
    el.addEventListener('mouseenter', e => {
      const st = el.dataset.state; const d = byState[st]; if (!d) return;
      showTT(`<div class="tt-title">${st}</div>
        <div class="tt-row"><span class="tt-key">Total stock MW</span><span class="tt-val">${fmtMWfull(d.grand_total)}</span></div>
        <div class="tt-row"><span class="tt-key">Claimed</span><span class="tt-val">${fmtMWfull(d.total_stock)}</span></div>
        <div class="tt-row"><span class="tt-key">Unclaimed</span><span class="tt-val">${fmtMWfull(d.total_unclaimed)}</span></div>
        <div class="tt-row"><span class="tt-key">% unclaimed</span><span class="tt-val">${d.unclaimed_pct}%</span></div>
        <div class="tt-row"><span class="tt-key">Registered users</span><span class="tt-val">${fmtInt(d.total_users)}</span></div>
        <div class="tt-row"><span class="tt-key">MW per user</span><span class="tt-val">${d.per_user_mw}</span></div>`, e);
    });
    el.addEventListener('mousemove', e => { const h = TT.innerHTML; showTT(h, e); });
    el.addEventListener('mouseleave', hideTT);
  });
}

// ────────────────────────────────────────────────────────────
// 15 · State table
// ────────────────────────────────────────────────────────────
function renderStateTable() {
  const tbl = document.getElementById('stateTable');
  const sorted = [...DATA.states].sort((a,b) => (b[STATE.stateSort]||0) - (a[STATE.stateSort]||0));
  const maxTotal = Math.max(...sorted.map(s => s.grand_total));
  tbl.innerHTML = `
    <thead><tr><th>State</th><th class="num">Users</th><th>Claimed / Unclaimed</th><th class="num">MW/user</th></tr></thead>
    <tbody>
      ${sorted.map(s => {
        const cw = (s.total_stock/maxTotal*100).toFixed(1);
        const uw = (s.total_unclaimed/maxTotal*100).toFixed(1);
        return `<tr>
          <td><div class="co-name">${s.state}</div><div style="font-size: 10.5px; color: var(--ink-mid);">${fmtMW(s.grand_total)} MW · ${s.unclaimed_pct}% unc.</div></td>
          <td class="num">${fmtInt(s.total_users)}</td>
          <td style="min-width: 160px;">
            <div class="bar-h"><i style="width: ${cw}%; background: var(--green);"></i></div>
            <div class="bar-h" style="margin-top: 2px;"><i class="unc" style="width: ${uw}%;"></i></div>
          </td>
          <td class="num">${s.per_user_mw}</td>
        </tr>`;
      }).join('')}
    </tbody>`;
}

// ────────────────────────────────────────────────────────────
// 16 · Manufacturer vs Reseller stacked bar
// ────────────────────────────────────────────────────────────
function renderMfgVsRes() {
  destroyChart('chartMfgVsRes');
  const ctx = document.getElementById('chartMfgVsRes').getContext('2d');
  const sorted = [...DATA.states].sort((a,b) => (b.cell_mfg+b.cell_res+b.mod_mfg+b.mod_res) - (a.cell_mfg+a.cell_res+a.mod_mfg+a.mod_res)).slice(0, 15);
  const labels = sorted.map(s => s.state);
  const datasets = [
    { label: 'Cell · with mfg', data: sorted.map(s => s.cell_mfg), backgroundColor: FT.cell, stack: 's' },
    { label: 'Cell · with reseller', data: sorted.map(s => s.cell_res), backgroundColor: '#4F8FCC', stack: 's' },
    { label: 'Module · with mfg', data: sorted.map(s => s.mod_mfg), backgroundColor: FT.module, stack: 's' },
    { label: 'Module · with reseller', data: sorted.map(s => s.mod_res), backgroundColor: '#C5294D', stack: 's' },
  ];
  const opts = baseAxisOpts();
  opts.indexAxis = 'y';
  opts.scales = {
    x: { stacked: true, grid: { color: 'rgba(38,42,51,0.06)' }, ticks: { color: FT.inkMid, callback: v => v>=1000?(v/1000).toFixed(0)+'k':v } },
    y: { stacked: true, grid: { display: false }, ticks: { color: FT.ink } }
  };
  opts.plugins.tooltip.callbacks = { label: c => `${c.dataset.label}: ${fmtMWfull(c.parsed.x)} MW` };
  // FT-style top legend strip drawn after chart
  const legendPlugin = {
    id: 'topLegend',
    afterDraw(chart) {
      const { ctx, chartArea } = chart;
      ctx.save(); ctx.font = "10.5px 'Inter', sans-serif"; ctx.fillStyle = FT.inkMid;
      let x = chartArea.left;
      const y = chartArea.top - 12;
      chart.data.datasets.forEach(ds => {
        ctx.fillStyle = ds.backgroundColor; ctx.fillRect(x, y - 7, 10, 10);
        ctx.fillStyle = FT.inkMid; ctx.fillText(ds.label, x + 14, y);
        x += ctx.measureText(ds.label).width + 30;
      });
      ctx.restore();
    }
  };
  CHARTS.chartMfgVsRes = new Chart(ctx, { type: 'bar', data: { labels, datasets }, options: opts, plugins: [legendPlugin] });
}

// ────────────────────────────────────────────────────────────
// 17 · Unclaimed leakage
// ────────────────────────────────────────────────────────────
function renderUnclaimed() {
  destroyChart('chartUnclaimed');
  const ctx = document.getElementById('chartUnclaimed').getContext('2d');
  const sorted = [...DATA.states].filter(s => s.total_unclaimed > 1).sort((a,b) => b.total_unclaimed - a.total_unclaimed).slice(0, 15);
  const labels = sorted.map(s => s.state);
  const datasets = [
    { label: 'Cell unclaimed', data: sorted.map(s => s.cell_unc_mfg + s.cell_unc_res), backgroundColor: FT.cell, stack: 'u' },
    { label: 'Module unclaimed', data: sorted.map(s => s.mod_unc_mfg + s.mod_unc_res), backgroundColor: FT.claret, stack: 'u' },
  ];
  const opts = baseAxisOpts();
  opts.indexAxis = 'y';
  opts.scales = {
    x: { stacked: true, grid: { color: 'rgba(38,42,51,0.06)' }, ticks: { color: FT.inkMid, callback: v => v>=1000?(v/1000).toFixed(0)+'k':v } },
    y: { stacked: true, grid: { display: false }, ticks: { color: FT.ink } }
  };
  opts.plugins.tooltip.callbacks = { label: c => `${c.dataset.label}: ${fmtMWfull(c.parsed.x)} MW` };
  const legendPlugin = {
    id: 'topLegend2',
    afterDraw(chart) {
      const { ctx, chartArea } = chart;
      ctx.save(); ctx.font = "10.5px 'Inter', sans-serif";
      let x = chartArea.left;
      const y = chartArea.top - 12;
      chart.data.datasets.forEach(ds => {
        ctx.fillStyle = ds.backgroundColor; ctx.fillRect(x, y - 7, 10, 10);
        ctx.fillStyle = FT.inkMid; ctx.fillText(ds.label, x + 14, y);
        x += ctx.measureText(ds.label).width + 30;
      });
      ctx.restore();
    }
  };
  CHARTS.chartUnclaimed = new Chart(ctx, { type: 'bar', data: { labels, datasets }, options: opts, plugins: [legendPlugin] });
}

// ────────────────────────────────────────────────────────────
// 18 · Sankey (FT palette)
// ────────────────────────────────────────────────────────────
function renderSankey() {
  const wrap = document.getElementById('sankeyWrap');
  wrap.innerHTML = '';
  const W = wrap.clientWidth || 1000;
  const H = 500;
  const st = DATA.stockTotals;
  const nodes = [
    { name: 'Cell' }, { name: 'Module' },
    { name: 'With Manufacturer' }, { name: 'With Reseller' },
    { name: 'Unclaimed (Mfg)' }, { name: 'Unclaimed (Reseller)' },
    { name: 'Claimed' }, { name: 'Unclaimed' },
  ];
  const idx = n => nodes.findIndex(x => x.name === n);
  const links = [
    { source: idx('Cell'), target: idx('With Manufacturer'), value: +st.cell_with_manufacturer_mw.toFixed(2) },
    { source: idx('Cell'), target: idx('With Reseller'), value: +st.cell_with_reseller_mw.toFixed(2) },
    { source: idx('Cell'), target: idx('Unclaimed (Mfg)'), value: +st.cell_unclaimed_with_manufacturer_mw.toFixed(2) },
    { source: idx('Cell'), target: idx('Unclaimed (Reseller)'), value: +st.cell_unclaimed_with_reseller_mw.toFixed(2) },
    { source: idx('Module'), target: idx('With Manufacturer'), value: +st.module_with_manufacturer_mw.toFixed(2) },
    { source: idx('Module'), target: idx('With Reseller'), value: +st.module_with_reseller_mw.toFixed(2) },
    { source: idx('Module'), target: idx('Unclaimed (Mfg)'), value: +st.module_unclaimed_with_manufacturer_mw.toFixed(2) },
    { source: idx('Module'), target: idx('Unclaimed (Reseller)'), value: +st.module_unclaimed_with_reseller_mw.toFixed(2) },
    { source: idx('With Manufacturer'), target: idx('Claimed'), value: +(st.cell_with_manufacturer_mw+st.module_with_manufacturer_mw).toFixed(2) },
    { source: idx('With Reseller'), target: idx('Claimed'), value: +(st.cell_with_reseller_mw+st.module_with_reseller_mw).toFixed(2) },
    { source: idx('Unclaimed (Mfg)'), target: idx('Unclaimed'), value: +(st.cell_unclaimed_with_manufacturer_mw+st.module_unclaimed_with_manufacturer_mw).toFixed(2) },
    { source: idx('Unclaimed (Reseller)'), target: idx('Unclaimed'), value: +(st.cell_unclaimed_with_reseller_mw+st.module_unclaimed_with_reseller_mw).toFixed(2) },
  ].filter(l => l.value > 0);

  const COLOR = {
    'Cell': FT.cell, 'Module': FT.module,
    'With Manufacturer': FT.green, 'With Reseller': FT.gold,
    'Unclaimed (Mfg)': '#CC3333', 'Unclaimed (Reseller)': '#7A1100',
    'Claimed': FT.green, 'Unclaimed': '#CC3333',
  };

  const sankey = d3.sankey().nodeWidth(14).nodePadding(18).extent([[1,1],[W-1,H-6]]);
  const graph = sankey({ nodes: nodes.map(d => ({...d})), links: links.map(d => ({...d})) });

  const svg = d3.select(wrap).append('svg').attr('width', W).attr('height', H);
  svg.append('g').attr('fill','none').selectAll('path')
    .data(graph.links).join('path')
    .attr('d', d3.sankeyLinkHorizontal())
    .attr('stroke', d => COLOR[d.source.name] || FT.inkMid)
    .attr('stroke-opacity', 0.35)
    .attr('stroke-width', d => Math.max(1, d.width))
    .on('mouseenter', (e, d) => showTT(`<div class="tt-title">${d.source.name} → ${d.target.name}</div><div class="tt-row"><span class="tt-key">MW</span><span class="tt-val">${fmtMWfull(d.value)}</span></div>`, e))
    .on('mousemove', (e, d) => showTT(`<div class="tt-title">${d.source.name} → ${d.target.name}</div><div class="tt-row"><span class="tt-key">MW</span><span class="tt-val">${fmtMWfull(d.value)}</span></div>`, e))
    .on('mouseleave', hideTT);
  svg.append('g').selectAll('rect')
    .data(graph.nodes).join('rect')
    .attr('x', d => d.x0).attr('y', d => d.y0)
    .attr('height', d => Math.max(2, d.y1 - d.y0))
    .attr('width', d => d.x1 - d.x0)
    .attr('fill', d => COLOR[d.name] || FT.ink);
  svg.append('g').selectAll('text')
    .data(graph.nodes).join('text')
    .attr('x', d => d.x0 < W/2 ? d.x1 + 6 : d.x0 - 6)
    .attr('y', d => (d.y0 + d.y1)/2)
    .attr('dy', '0.35em')
    .attr('text-anchor', d => d.x0 < W/2 ? 'start' : 'end')
    .attr('fill', FT.ink)
    .text(d => `${d.name}  ${fmtMW(d.value)}`);
}

// ────────────────────────────────────────────────────────────
// 19 · Compare
// ────────────────────────────────────────────────────────────
function renderCompare() {
  // build dedup list across segments
  const segs = activeSegments();
  let comps = [];
  segs.forEach(seg => companiesForSeg(seg).slice(0, 40).forEach(c => comps.push({...c, seg})));
  const seen = new Set(); comps = comps.filter(c => seen.has(c.name) ? false : (seen.add(c.name), true));
  comps.sort((a,b) => b.total_mw - a.total_mw);

  // Set defaults BEFORE generating pills HTML so they render in the .on state
  if (STATE.selectedCompanies.length === 0) STATE.selectedCompanies = comps.slice(0, 3).map(c => c.name);

  const pills = document.getElementById('comparePills');
  pills.innerHTML = comps.slice(0, 30).map(c => `<span class="pill ${STATE.selectedCompanies.includes(c.name)?'on':''}" data-co="${c.name}" data-seg="${c.seg}">${c.name}</span>`).join('');
  pills.querySelectorAll('.pill').forEach(p => p.addEventListener('click', () => {
    const co = p.dataset.co;
    if (STATE.selectedCompanies.includes(co)) STATE.selectedCompanies = STATE.selectedCompanies.filter(x => x !== co);
    else if (STATE.selectedCompanies.length < 4) STATE.selectedCompanies.push(co);
    renderCompare();
  }));

  // Annual chart
  destroyChart('chartCompareAnnual');
  const aCtx = document.getElementById('chartCompareAnnual').getContext('2d');
  const yrs = [2022,2023,2024,2025,2026];
  const datasets = STATE.selectedCompanies.map((co, i) => {
    const row = comps.find(c => c.name === co);
    if (!row) return null;
    return {
      label: co.length > 24 ? co.slice(0,22)+'…' : co,
      _directLabel: co.split(' ')[0],
      data: yrs.map(y => row.by_year[y]||0),
      borderColor: colorFor(co, i+1), backgroundColor: colorFor(co, i+1)+'15',
      fill: false, tension: 0.3, borderWidth: 2.2, pointRadius: 3,
    };
  }).filter(Boolean);
  const aOpts = baseAxisOpts(); aOpts.layout = { padding: { right: 80 } };
  CHARTS.chartCompareAnnual = new Chart(aCtx, { type: 'line', data: { labels: yrs, datasets }, options: aOpts });

  // Monthly chart
  destroyChart('chartCompareMonthly');
  const mCtx = document.getElementById('chartCompareMonthly').getContext('2d');
  // Combine cell + module monthly per company (if dual-segment)
  let monthsLabel = null;
  const monthlyDS = STATE.selectedCompanies.map((co, i) => {
    let series = [];
    ['cell','module'].forEach(seg => {
      const s = (DATA.derived[seg==='cell'?'monthlyPerCoCell':'monthlyPerCoModule'])[co];
      if (s) {
        if (series.length === 0) series = s.map(x => ({ym: x.ym, mw: x.mw}));
        else s.forEach((x,j) => { if (series[j]) series[j].mw += x.mw; });
      }
    });
    if (!series.length) return null;
    const last24 = series.slice(-24);
    if (!monthsLabel) monthsLabel = last24.map(p => p.ym);
    return {
      label: co.length > 22 ? co.slice(0,20)+'…' : co,
      _directLabel: co.split(' ')[0],
      data: last24.map(p => p.mw),
      borderColor: colorFor(co, i+1),
      backgroundColor: colorFor(co, i+1)+'18',
      fill: false, tension: 0.32, borderWidth: 1.8, pointRadius: 0,
    };
  }).filter(Boolean);
  const mOpts = baseAxisOpts(); mOpts.layout = { padding: { right: 80 } }; mOpts.scales.x.ticks.maxTicksLimit = 8;
  CHARTS.chartCompareMonthly = new Chart(mCtx, { type: 'line', data: { labels: monthsLabel || [], datasets: monthlyDS }, options: mOpts });
}

// ────────────────────────────────────────────────────────────
// CSV export helper
// ────────────────────────────────────────────────────────────
function downloadCSV(tableId, filename) {
  const tbl = document.getElementById(tableId);
  if (!tbl) return;
  const rows = Array.from(tbl.querySelectorAll('tr'));
  const csv = rows.map(tr => {
    const cells = Array.from(tr.querySelectorAll('th,td'));
    return cells.map(c => {
      let txt = (c.dataset.csv != null) ? c.dataset.csv : c.textContent.trim().replace(/\s+/g, ' ');
      if (txt.includes(',') || txt.includes('"') || txt.includes('\n')) txt = '"' + txt.replace(/"/g, '""') + '"';
      return txt;
    }).join(',');
  }).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.style.display = 'none';
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
window.downloadCSV = downloadCSV;

// ────────────────────────────────────────────────────────────
// T1 · Top 15 monthly volumes + annual table
// ────────────────────────────────────────────────────────────
function renderMonthlyVolTable() {
  const wrap = document.getElementById('monthlyVolWrap');
  if (!wrap) return;
  const seg = STATE.monVolSeg || 'cell';
  // If searching, show all matching companies; else top 15 of segment
  let comps;
  if (searchActive()) {
    comps = applySearchFilter(companiesForSeg(seg));
  } else {
    comps = companiesForSeg(seg).slice(0, 15);
  }
  const monthlyPerCo = DATA.derived[seg==='cell'?'monthlyPerCoCell':'monthlyPerCoModule'];

  // Build a full sorted YYYY-MM list from union; trim to non-zero range AND drop any future months past LAST_YM
  const allYms = new Set();
  comps.forEach(c => (monthlyPerCo[c.name] || []).forEach(p => allYms.add(p.ym)));
  let yms = Array.from(allYms).sort();
  // Drop future months (we don't have data after May 2026)
  yms = yms.filter(ym => !isFutureYM(ym));
  // Trim leading and trailing all-zero months across these companies
  const colTotals = yms.map(ym => comps.reduce((s, c) => {
    const pt = (monthlyPerCo[c.name] || []).find(x => x.ym === ym);
    return s + (pt ? pt.mw : 0);
  }, 0));
  let startIdx = colTotals.findIndex(v => v > 0);
  let endIdx = colTotals.length - 1;
  while (endIdx >= 0 && colTotals[endIdx] === 0) endIdx--;
  if (startIdx < 0) startIdx = 0;
  if (endIdx < startIdx) endIdx = startIdx;
  yms = yms.slice(startIdx, endIdx + 1);

  if (!comps.length) {
    wrap.innerHTML = `<div style="padding: 28px 0; text-align: center; color: var(--ink-mid); font-style: italic;">No companies match "${STATE.search}" in ${seg} segment.</div>`;
    return;
  }

  // Year groups
  const yearGroups = [];
  yms.forEach(ym => {
    const y = ym.slice(0, 4);
    let g = yearGroups.find(g => g.year === y);
    if (!g) { g = { year: y, months: [] }; yearGroups.push(g); }
    g.months.push(ym);
  });

  const monthAbbr = ['','J','F','M','A','M','J','J','A','S','O','N','D'];

  // helper to get value
  const get = (co, ym) => {
    const s = monthlyPerCo[co] || [];
    const pt = s.find(x => x.ym === ym);
    return pt ? pt.mw : 0;
  };

  // For quarterly view: collapse each year's months into Q1/Q2/Q3/Q4
  const granularity = STATE.monVolGran || 'monthly';
  const isQuarterly = granularity === 'quarterly';

  // Build "buckets" per year: in monthly mode = individual YMs; in quarterly mode = arrays of YMs that share a quarter
  function bucketsForYear(g) {
    if (!isQuarterly) return g.months.map(ym => ({ ym, ymsInBucket: [ym], label: monthAbbr[+ym.slice(5,7)] }));
    const byQ = {};
    g.months.forEach(ym => {
      const mo = +ym.slice(5,7);
      const q = Math.ceil(mo/3);
      if (!byQ[q]) byQ[q] = { q, ymsInBucket: [], label: 'Q'+q };
      byQ[q].ymsInBucket.push(ym);
    });
    // Mark partial quarters (e.g. 2026-Q2 has only Apr/May)
    return Object.values(byQ).sort((a,b)=>a.q-b.q).map(b => ({ ...b, ym: g.year+'-Q'+b.q, label: b.label + (b.ymsInBucket.length < 3 ? '*' : '') }));
  }

  const headRow1 = `<tr>
    <th class="sticky-l left" rowspan="2">${searchActive() ? 'Matches' : 'Top 15'} · ${seg}</th>
    ${yearGroups.map(g => {
      const buckets = bucketsForYear(g);
      const isPartial = g.months.length < 12;
      const label = `${g.year}${isPartial?` · ${monthAbbr[+g.months[0].slice(5,7)]}–${monthAbbr[+g.months[g.months.length-1].slice(5,7)]}`:''}`;
      return `<th class="year-hd ${isPartial?'year-hd-ytd':''}" colspan="${buckets.length + 1}">${label}</th>`;
    }).join('')}
    <th class="sticky-r" rowspan="2">All-time</th>
  </tr>`;
  const headRow2 = `<tr>
    ${yearGroups.map(g => bucketsForYear(g).map((b, i) => `<th class="${i===0?'year-sep':''}" style="font-size: ${isQuarterly?'10px':'9px'};">${b.label}</th>`).join('') + `<th class="annual" style="font-size: 9px;">FY</th>`).join('')}
  </tr>`;

  // Get value summed across bucket months
  const getBucket = (co, bucket) => bucket.ymsInBucket.reduce((s, ym) => s + get(co, ym), 0);

  // body rows
  const body = comps.map((c, idx) => {
    let grand = 0;
    const yearSubtotals = yearGroups.map(g => {
      let yt = 0;
      g.months.forEach(ym => yt += get(c.name, ym));
      grand += yt;
      return yt;
    });
    const cells = yearGroups.map((g, gi) => {
      const buckets = bucketsForYear(g);
      return buckets.map((b, i) => {
        const v = getBucket(c.name, b);
        return `<td class="num ${v===0?'zero':''} ${i===0?'year-sep':''}" data-csv="${v.toFixed(2)}" title="${b.ymsInBucket.join(', ')}">${v===0?'·':v.toFixed(v<10?1:0)}</td>`;
      }).join('') + `<td class="num annual" data-csv="${yearSubtotals[gi].toFixed(2)}">${yearSubtotals[gi]===0?'·':fmtMW(yearSubtotals[gi])}</td>`;
    }).join('');
    return `<tr>
      <td class="sticky-l left"><span style="color: var(--ink-mid); width: 22px; display: inline-block;">${idx+1}</span> ${c.name}${c.is_almm?' <span class="cell-tag">A</span>':''}</td>
      ${cells}
      <td class="sticky-r" data-csv="${grand.toFixed(2)}">${fmtMW(grand)}</td>
    </tr>`;
  }).join('');

  // Footer: Top-15 total
  let grandTot = 0;
  const ftYearSubs = yearGroups.map(g => {
    let yt = 0;
    g.months.forEach(ym => comps.forEach(c => yt += get(c.name, ym)));
    grandTot += yt;
    return yt;
  });
  const footCells = yearGroups.map((g, gi) => {
    const buckets = bucketsForYear(g);
    return buckets.map((b, i) => {
      const v = comps.reduce((s, c) => s + getBucket(c.name, b), 0);
      return `<td class="num ${i===0?'year-sep':''}" data-csv="${v.toFixed(2)}">${v===0?'·':v.toFixed(v<10?1:0)}</td>`;
    }).join('') + `<td class="num annual" data-csv="${ftYearSubs[gi].toFixed(2)}">${fmtMW(ftYearSubs[gi])}</td>`;
  }).join('');
  const footer = `<tr class="tot-row">
    <td class="sticky-l left">${searchActive() ? 'Match total' : 'Top-15 '+seg+' total'}</td>
    ${footCells}
    <td class="sticky-r" data-csv="${grandTot.toFixed(2)}">${fmtMW(grandTot)}</td>
  </tr>`;

  wrap.innerHTML = `<table class="data-tbl" id="monthlyVolTable">
    <thead>${headRow1}${headRow2}</thead>
    <tbody>${body}${footer}</tbody>
  </table>${isQuarterly?'<div style="margin-top:6px; font-size: 10.5px; color: var(--ink-mid); font-style: italic;">Q* = partial quarter (fewer than 3 months of data).</div>':''}`;
}

// ────────────────────────────────────────────────────────────
// T2 · Top 15 annual MW + share + CAGR + concentration ratios
// ────────────────────────────────────────────────────────────
function renderTopAnnualTable() {
  const wrap = document.getElementById('topAnnualWrap');
  if (!wrap) return;
  const yrs = [2022,2023,2024,2025,2026];
  // Combined cell + module per-company per-year
  const allCo = {};
  DATA.cellYearly.forEach(r => { allCo[r.company] = allCo[r.company] || {byYr: {}, segs: new Set(), is_almm: false}; allCo[r.company].byYr[r.year] = (allCo[r.company].byYr[r.year]||0) + r.mw; allCo[r.company].segs.add('cell'); allCo[r.company].is_almm = allCo[r.company].is_almm || r.is_almm; });
  DATA.moduleYearly.forEach(r => { allCo[r.company] = allCo[r.company] || {byYr: {}, segs: new Set(), is_almm: false}; allCo[r.company].byYr[r.year] = (allCo[r.company].byYr[r.year]||0) + r.mw; allCo[r.company].segs.add('module'); allCo[r.company].is_almm = allCo[r.company].is_almm || r.is_almm; });
  const ranked = Object.entries(allCo).map(([name, d]) => ({ name, ...d, total: Object.values(d.byYr).reduce((s,v)=>s+v,0), _25: d.byYr[2025]||0 })).sort((a,b) => b._25 - a._25);
  // If searching, show all matches; else top 15
  const top15 = searchActive() ? applySearchFilter(ranked) : ranked.slice(0, 15);
  const totByYr = DATA.derived.yearlyTotalDCR;
  if (!top15.length) {
    wrap.innerHTML = `<div style="padding: 28px 0; text-align: center; color: var(--ink-mid); font-style: italic;">No companies match "${STATE.search}".</div>`;
    return;
  }

  // CAGR per company (using first full year to 2025)
  function cagr(byYr) {
    const ys = Object.keys(byYr).map(y=>+y).filter(y => y < 2026 && byYr[y] > 0).sort();
    if (ys.length < 2) return null;
    const v0 = byYr[ys[0]], v1 = byYr[ys[ys.length-1]];
    const n = ys[ys.length-1] - ys[0];
    return (((v1/v0)**(1/n)) - 1) * 100;
  }

  const headRow1 = `<tr>
    <th class="sticky-l left" rowspan="2">#</th>
    <th class="sticky-l left" rowspan="2" style="left: 28px;">Company</th>
    <th rowspan="2">Segments</th>
    ${yrs.map(y => `<th class="year-hd ${y===2026?'year-hd-ytd':''}" colspan="2">${y}${y===2026?' YTD':''}</th>`).join('')}
    <th rowspan="2" class="annual">CAGR<br>'22→'25</th>
  </tr>`;
  const headRow2 = `<tr>
    ${yrs.map(y => `<th class="year-sep">MW</th><th>%</th>`).join('')}
  </tr>`;

  const body = top15.map((c, i) => {
    const cells = yrs.map(y => {
      const mw = c.byYr[y] || 0;
      const sh = totByYr[y] ? mw/totByYr[y]*100 : 0;
      return `<td class="num year-sep" data-csv="${mw.toFixed(2)}">${mw===0?'·':fmtMW(mw)}</td><td class="num" data-csv="${sh.toFixed(2)}">${mw===0?'·':sh.toFixed(1)+'%'}</td>`;
    }).join('');
    const cg = cagr(c.byYr);
    return `<tr>
      <td class="sticky-l left" style="min-width: 28px; max-width: 28px;">${i+1}</td>
      <td class="sticky-l left" style="left: 28px;">${c.name}${c.is_almm?' <span class="cell-tag">A</span>':''}${c.segs.size>1?' <span class="cell-tag">·dual</span>':''}</td>
      <td>${Array.from(c.segs).map(s=>`<span class="tag ${s}" style="font-size: 8px;">${s.slice(0,3)}</span>`).join(' ')}</td>
      ${cells}
      <td class="num annual" data-csv="${cg==null?'':cg.toFixed(2)}" style="color: ${cg==null?'var(--ink-faint)':(cg>0?'var(--green)':'var(--claret)')};">${cg==null?'—':fmtPct(cg)}</td>
    </tr>`;
  }).join('');

  // Concentration ratio footer rows: CR-3, CR-5, CR-10 share-of-DCR per year
  function crShare(n, y) {
    const arr = Object.entries(allCo).map(([name, d]) => d.byYr[y]||0).sort((a,b) => b-a);
    const tot = totByYr[y] || 0;
    if (!tot) return 0;
    return arr.slice(0, n).reduce((s,v)=>s+v, 0) / tot * 100;
  }
  function crRow(n) {
    const cells = yrs.map(y => {
      const v = crShare(n, y);
      return `<td class="num year-sep" data-csv=""></td><td class="num" data-csv="${v.toFixed(2)}">${v.toFixed(1)}%</td>`;
    }).join('');
    return `<tr class="tot-row">
      <td class="sticky-l left" style="min-width: 28px; max-width: 28px;"></td>
      <td class="sticky-l left" style="left: 28px;">CR-${n} (top ${n} combined share)</td>
      <td></td>
      ${cells}
      <td class="annual" data-csv=""></td>
    </tr>`;
  }

  wrap.innerHTML = `<table class="data-tbl" id="topAnnualTable">
    <thead>${headRow1}${headRow2}</thead>
    <tbody>${body}${crRow(3)}${crRow(5)}${crRow(10)}</tbody>
  </table>`;
}

// ────────────────────────────────────────────────────────────
// T3 · Dual-segment cell:module ratio table
// ────────────────────────────────────────────────────────────
function renderDualTable() {
  const wrap = document.getElementById('dualTableWrap');
  if (!wrap) return;
  const yrs = [2022,2023,2024,2025,2026];
  const split = DATA.derived.dualSegmentSplit;
  let rows = Object.entries(split).map(([name, d]) => {
    const total25 = (d.cell[2025]||0) + (d.module[2025]||0);
    return { name, d, total25 };
  }).filter(r => r.total25 > 0).sort((a,b) => b.total25 - a.total25);
  if (searchActive()) rows = applySearchFilter(rows);
  if (!rows.length) {
    wrap.innerHTML = `<div style="padding: 28px 0; text-align: center; color: var(--ink-mid); font-style: italic;">No dual-segment companies match "${STATE.search}".</div>`;
    return;
  }

  const headRow1 = `<tr>
    <th class="sticky-l left" rowspan="2">Company</th>
    ${yrs.map(y => `<th class="year-hd ${y===2026?'year-hd-ytd':''}" colspan="3">${y}${y===2026?' YTD':''}</th>`).join('')}
    <th rowspan="2" class="annual">All-time C:M</th>
  </tr>`;
  const headRow2 = `<tr>
    ${yrs.map(y => `<th class="year-sep">Cell</th><th>Mod</th><th>C:M</th>`).join('')}
  </tr>`;

  const body = rows.map(r => {
    let totC = 0, totM = 0;
    const cells = yrs.map(y => {
      const c = r.d.cell[y]||0, m = r.d.module[y]||0;
      totC += c; totM += m;
      const ratio = (c+m)===0 ? null : (m === 0 ? '∞' : (c/m).toFixed(2));
      const ratioColor = ratio === null ? 'var(--ink-faint)' : ratio === '∞' ? 'var(--cell)' : (parseFloat(ratio) > 1 ? 'var(--cell)' : 'var(--module)');
      return `<td class="num year-sep" data-csv="${c.toFixed(2)}">${c===0?'·':fmtMW(c)}</td>
              <td class="num" data-csv="${m.toFixed(2)}">${m===0?'·':fmtMW(m)}</td>
              <td class="num" data-csv="${ratio||''}" style="color: ${ratioColor};">${ratio===null?'·':ratio}</td>`;
    }).join('');
    const allRatio = totM === 0 ? '∞' : (totC/totM).toFixed(2);
    return `<tr>
      <td class="sticky-l left">${r.name}</td>
      ${cells}
      <td class="num annual" data-csv="${allRatio}">${allRatio}</td>
    </tr>`;
  }).join('');

  wrap.innerHTML = `<table class="data-tbl" id="dualTable">
    <thead>${headRow1}${headRow2}</thead>
    <tbody>${body}</tbody>
  </table>`;
}

// ────────────────────────────────────────────────────────────
// T4 · Movers tables (risers / new / fallers)
// ────────────────────────────────────────────────────────────
function renderMoversTables() {
  // pool: union of cell + module companies, with 2024 and 2025 MW
  const pool = {};
  ['cell','module'].forEach(seg => {
    companiesForSeg(seg).forEach(c => {
      const key = c.name + '|' + seg;
      pool[key] = { name: c.name, seg, v0: c.by_year[2024]||0, v1: c.by_year[2025]||0 };
    });
  });
  const arr = Object.values(pool);
  const movers = arr.filter(r => r.v1 > 0).map(r => ({ ...r, delta: r.v1 - r.v0, growth: r.v0 ? (r.v1-r.v0)/r.v0*100 : null }));
  let risers = movers.filter(r => r.growth != null).sort((a,b) => b.growth - a.growth);
  let fallers = movers.filter(r => r.growth != null).sort((a,b) => a.growth - b.growth);
  let newE = movers.filter(r => r.v0 === 0 && r.v1 > 0).sort((a,b) => b.v1 - a.v1);
  if (searchActive()) {
    risers = applySearchFilter(risers); fallers = applySearchFilter(fallers); newE = applySearchFilter(newE);
  }
  risers = risers.slice(0, 10); fallers = fallers.slice(0, 10); newE = newE.slice(0, 10);

  function tableHTML(rows, kind) {
    const header = kind === 'new'
      ? `<tr><th class="left">#</th><th class="left">Company</th><th>Seg</th><th class="num">2025 MW</th></tr>`
      : `<tr><th class="left">#</th><th class="left">Company</th><th>Seg</th><th class="num">2024</th><th class="num">2025</th><th class="num">Δ MW</th><th class="num">Δ %</th></tr>`;
    const body = rows.map((r, i) => {
      if (kind === 'new') {
        return `<tr><td>${i+1}</td><td class="co-name">${r.name}</td><td><span class="tag ${r.seg}" style="font-size: 8.5px;">${r.seg.slice(0,3)}</span></td><td class="num">${fmtMW(r.v1)}</td></tr>`;
      }
      const color = r.growth > 0 ? 'var(--green)' : 'var(--claret)';
      return `<tr>
        <td>${i+1}</td>
        <td class="co-name">${r.name}</td>
        <td><span class="tag ${r.seg}" style="font-size: 8.5px;">${r.seg.slice(0,3)}</span></td>
        <td class="num">${fmtMW(r.v0)}</td>
        <td class="num">${fmtMW(r.v1)}</td>
        <td class="num" style="color: ${color};">${r.delta>0?'+':''}${fmtMW(r.delta)}</td>
        <td class="num" style="color: ${color}; font-weight: 700;">${fmtPct(r.growth)}</td>
      </tr>`;
    }).join('');
    return `<table class="ft-table" style="font-size: 11.5px;"><thead>${header}</thead><tbody>${body}</tbody></table>`;
  }

  if (document.getElementById('risersTable')) document.getElementById('risersTable').innerHTML = tableHTML(risers, 'rise');
  if (document.getElementById('newEntrantsTable')) document.getElementById('newEntrantsTable').innerHTML = tableHTML(newE, 'new');
  if (document.getElementById('fallersTable')) document.getElementById('fallersTable').innerHTML = tableHTML(fallers, 'fall');
}

// ────────────────────────────────────────────────────────────
// T5 · Company size distribution table
// ────────────────────────────────────────────────────────────
function renderTierTable() {
  const wrap = document.getElementById('tierWrap');
  if (!wrap) return;
  const yrs = [2022,2023,2024,2025,2026];
  const tiers = [
    { label: '<10 MW · sub-scale', min: 0, max: 10, color: '#B3A9A0' },
    { label: '10–100 MW · small', min: 10, max: 100, color: '#806F47' },
    { label: '100–500 MW · mid', min: 100, max: 500, color: '#B68900' },
    { label: '500–1,000 MW · large', min: 500, max: 1000, color: '#0F5499' },
    { label: '1 GW+ · majors', min: 1000, max: Infinity, color: '#990F3D' },
  ];

  function bucket(seg, y, t) {
    return yearlyForSeg(seg).filter(r => r.year === y && r.mw >= t.min && r.mw < t.max).length;
  }

  // global max for bar scaling
  let maxCount = 0;
  yrs.forEach(y => tiers.forEach(t => { ['cell','module'].forEach(seg => { const n = bucket(seg, y, t); if (n > maxCount) maxCount = n; }); }));

  const head = `<tr>
    <th class="sticky-l left">Size tier</th>
    <th>Seg</th>
    ${yrs.map(y => `<th class="num year-hd ${y===2026?'year-hd-ytd':''}">${y}${y===2026?' YTD':''}</th>`).join('')}
    <th class="num annual">Avg</th>
  </tr>`;

  const body = tiers.map(t => {
    return ['cell','module'].map(seg => {
      const cells = yrs.map(y => {
        const n = bucket(seg, y, t);
        const barW = maxCount ? n/maxCount*60 : 0;
        return `<td class="num year-sep" data-csv="${n}"><span class="tier-bar" style="width: ${barW}px; background: ${t.color}; opacity: 0.85;"></span>${n||'·'}</td>`;
      }).join('');
      const avg = (yrs.reduce((s,y) => s + bucket(seg,y,t), 0) / yrs.length).toFixed(1);
      return `<tr>
        <td class="sticky-l left"><span style="color: ${t.color}; font-weight: 700;">■</span> ${t.label}</td>
        <td><span class="tag ${seg}" style="font-size: 8.5px;">${seg.slice(0,3)}</span></td>
        ${cells}
        <td class="num annual" data-csv="${avg}">${avg}</td>
      </tr>`;
    }).join('');
  }).join('');

  // total active per year footer
  const totalCells = yrs.map(y => `<td class="num year-sep" data-csv="${DATA.derived.activeCell[y]+DATA.derived.activeModule[y]}">${(DATA.derived.activeCell[y]||0)+(DATA.derived.activeModule[y]||0)}</td>`).join('');
  const footer = `<tr class="tot-row">
    <td class="sticky-l left">Active total (cell + module)</td>
    <td></td>
    ${totalCells}
    <td class="annual"></td>
  </tr>`;

  wrap.innerHTML = `<table class="data-tbl" id="tierTable"><thead>${head}</thead><tbody>${body}${footer}</tbody></table>`;
}

// ────────────────────────────────────────────────────────────
// T6 · State cell-vs-module mix table
// ────────────────────────────────────────────────────────────
let stateMixSort = 'total';
let stateMixDir = -1;
function renderStateMixTable() {
  const wrap = document.getElementById('stateMixWrap');
  if (!wrap) return;
  const rows = DATA.states.map(s => {
    const cell = s.cell_mfg + s.cell_res;
    const mod = s.mod_mfg + s.mod_res;
    const total = cell + mod;
    const cellPct = total ? (cell/total*100) : 0;
    const cmRatio = mod === 0 ? (cell === 0 ? null : Infinity) : (cell/mod);
    return { state: s.state, users: s.total_users, cell, mod, cell_mfg: s.cell_mfg, cell_res: s.cell_res, mod_mfg: s.mod_mfg, mod_res: s.mod_res, total, cellPct, cmRatio };
  }).filter(r => r.total > 0);

  // sort
  const key = stateMixSort;
  rows.sort((a,b) => {
    if (key === 'state') return stateMixDir * a.state.localeCompare(b.state);
    return stateMixDir * ((a[key]||0) - (b[key]||0));
  });

  // visual bar widths
  const maxTotal = Math.max(...rows.map(r => r.total), 1);

  const cols = [
    { k: 'state', label: 'State', cls: 'left' },
    { k: 'users', label: 'Users', cls: 'num' },
    { k: 'cell', label: 'Cell · mfg+res', cls: 'num' },
    { k: 'mod', label: 'Module · mfg+res', cls: 'num' },
    { k: 'total', label: 'Total claimed', cls: 'num' },
    { k: 'cellPct', label: 'Cell share', cls: 'num' },
    { k: 'cmRatio', label: 'C:M', cls: 'num' },
  ];

  const sortInd = (k) => stateMixSort === k ? `<span style="color: var(--claret); margin-left: 3px;">${stateMixDir===-1?'▼':'▲'}</span>` : '';

  const head = `<tr>${cols.map(c => `<th class="${c.cls}" data-sort="${c.k}" style="cursor: pointer;">${c.label}${sortInd(c.k)}</th>`).join('')}</tr>`;
  const body = rows.map(r => {
    const cellW = (r.cell / maxTotal * 80).toFixed(1);
    const modW = (r.mod / maxTotal * 80).toFixed(1);
    const cmStr = r.cmRatio === null ? '—' : (r.cmRatio === Infinity ? '∞' : r.cmRatio.toFixed(2));
    const cmColor = r.cmRatio === null ? 'var(--ink-faint)' : (r.cmRatio === Infinity || r.cmRatio > 1 ? 'var(--cell)' : 'var(--module)');
    const cellPctColor = r.cellPct > 50 ? 'var(--cell)' : 'var(--module)';
    return `<tr>
      <td class="left"><div style="font-weight: 600;">${r.state}</div></td>
      <td class="num">${fmtInt(r.users)}</td>
      <td class="num"><div style="display: flex; gap: 6px; align-items: center; justify-content: flex-end;"><span class="iv-bar cell" style="width: ${cellW}px;"></span>${r.cell===0?'·':fmtMW(r.cell)}</div></td>
      <td class="num"><div style="display: flex; gap: 6px; align-items: center; justify-content: flex-end;"><span class="iv-bar module" style="width: ${modW}px;"></span>${r.mod===0?'·':fmtMW(r.mod)}</div></td>
      <td class="num" style="font-weight: 700;">${fmtMW(r.total)}</td>
      <td class="num" style="color: ${cellPctColor}; font-weight: 600;">${r.cellPct.toFixed(0)}%</td>
      <td class="num" style="color: ${cmColor}; font-weight: 600;">${cmStr}</td>
    </tr>`;
  }).join('');

  // Totals footer
  const totCell = rows.reduce((s,r)=>s+r.cell, 0);
  const totMod = rows.reduce((s,r)=>s+r.mod, 0);
  const totAll = totCell + totMod;
  const totCellPct = totAll ? (totCell/totAll*100) : 0;
  const totCM = totMod ? (totCell/totMod) : Infinity;
  const footer = `<tr class="tot-row">
    <td class="left">India total</td>
    <td class="num">${fmtInt(rows.reduce((s,r)=>s+r.users, 0))}</td>
    <td class="num">${fmtMW(totCell)}</td>
    <td class="num">${fmtMW(totMod)}</td>
    <td class="num" style="font-weight: 700;">${fmtMW(totAll)}</td>
    <td class="num">${totCellPct.toFixed(0)}%</td>
    <td class="num">${totCM === Infinity ? '∞' : totCM.toFixed(2)}</td>
  </tr>`;

  wrap.innerHTML = `<table class="data-tbl" id="stateMixTable"><thead>${head}</thead><tbody>${body}${footer}</tbody></table>`;

  // wire sort
  wrap.querySelectorAll('th[data-sort]').forEach(th => th.addEventListener('click', () => {
    if (stateMixSort === th.dataset.sort) stateMixDir = -stateMixDir;
    else { stateMixSort = th.dataset.sort; stateMixDir = (stateMixSort === 'state') ? 1 : -1; }
    renderStateMixTable();
  }));
}

// ────────────────────────────────────────────────────────────
// T7 · First-production calendar (Arrivals)
// ────────────────────────────────────────────────────────────
function renderArrivals() {
  const wrap = document.getElementById('arrivalsWrap');
  if (!wrap) return;

  // Build per-(company,segment) first-production record
  const rows = [];
  ['cell','module'].forEach(seg => {
    const monthlyPerCo = DATA.derived[seg==='cell'?'monthlyPerCoCell':'monthlyPerCoModule'];
    companiesForSeg(seg).forEach(c => {
      const series = monthlyPerCo[c.name] || [];
      const firstPt = series.find(p => p.mw > 0);
      if (!firstPt) return;
      // Get rank in 2025 for this segment
      const yearly = yearlyForSeg(seg);
      const rows25 = yearly.filter(r => r.year === 2025).sort((a,b) => b.mw - a.mw);
      const rankIdx = rows25.findIndex(r => r.company === c.name);
      rows.push({
        name: c.name, seg, firstYM: firstPt.ym, firstMW: firstPt.mw,
        mw25: c.by_year[2025] || 0,
        rank25: rankIdx >= 0 ? rankIdx + 1 : null,
        totalMW: c.total_mw,
        is_almm: c.is_almm,
      });
    });
  });

  // Apply search
  let filtered = searchActive() ? applySearchFilter(rows) : rows;

  // Sort
  const sortMode = STATE.calSort || 'first_asc';
  if (sortMode === 'first_asc') filtered.sort((a,b) => a.firstYM.localeCompare(b.firstYM) || b.totalMW - a.totalMW);
  else if (sortMode === 'first_desc') filtered.sort((a,b) => b.firstYM.localeCompare(a.firstYM) || b.totalMW - a.totalMW);
  else if (sortMode === 'size') filtered.sort((a,b) => b.mw25 - a.mw25);

  if (!filtered.length) {
    wrap.innerHTML = `<div style="padding: 28px 0; text-align: center; color: var(--ink-mid); font-style: italic;">No companies match "${STATE.search}".</div>`;
    return;
  }

  // Group by first-year for visual subheaders if sorting chronologically
  const head = `<tr>
    <th class="left" style="min-width: 30px;">#</th>
    <th class="left" style="min-width: 240px;">Company</th>
    <th>Segment</th>
    <th>First month</th>
    <th class="num">First-month MW</th>
    <th class="num">2025 MW</th>
    <th class="num">Rank '25</th>
    <th class="num">All-time MW</th>
  </tr>`;

  // Inline group separators by year (only when sorted by first)
  let lastYear = '';
  const body = filtered.map((r, i) => {
    const year = r.firstYM.slice(0, 4);
    let groupSep = '';
    if ((sortMode === 'first_asc' || sortMode === 'first_desc') && year !== lastYear) {
      groupSep = `<tr><td colspan="8" style="padding: 8px 0 4px 0; border-bottom: 1px solid var(--rule-strong); font-family: 'Source Serif 4', serif; font-weight: 700; color: var(--ink); font-size: 13px; background: var(--paper);">${year} · ${filtered.filter(x => x.firstYM.slice(0,4) === year).length} debut(s)</td></tr>`;
      lastYear = year;
    }
    return groupSep + `<tr data-co="${r.name}" data-seg="${r.seg}" style="cursor: pointer;">
      <td class="left">${i+1}</td>
      <td class="left"><span style="font-weight: 600;">${r.name}</span>${r.is_almm?' <span class="cell-tag">A</span>':''}</td>
      <td><span class="tag ${r.seg}" style="font-size: 8.5px;">${r.seg.slice(0,3)}</span></td>
      <td style="font-variant-numeric: tabular-nums;">${r.firstYM}</td>
      <td class="num">${fmtMW(r.firstMW)}</td>
      <td class="num" style="font-weight: 600;">${r.mw25===0?'·':fmtMW(r.mw25)}</td>
      <td class="num" style="color: ${r.rank25?'var(--claret)':'var(--ink-faint)'}; font-weight: 700;">${r.rank25?'#'+r.rank25:'—'}</td>
      <td class="num">${fmtMW(r.totalMW)}</td>
    </tr>`;
  }).join('');

  wrap.innerHTML = `<table class="data-tbl" id="arrivalsTable"><thead>${head}</thead><tbody>${body}</tbody></table>`;

  // wire row clicks to open drill
  wrap.querySelectorAll('tbody tr[data-co]').forEach(tr => tr.addEventListener('click', () => {
    STATE.selectedCompany = tr.dataset.co;
    renderLeaderboard();
    renderDrill(tr.dataset.co, tr.dataset.seg);
  }));
}

// ────────────────────────────────────────────────────────────
// 20 · Insights (with mini thumb charts)
// ────────────────────────────────────────────────────────────
function renderInsights() {
  const ytC = DATA.derived.yearlyTotalsCell, ytM = DATA.derived.yearlyTotalsModule;
  const yrs = [2022,2023,2024,2025,2026];
  const stock = DATA.stockTotals;
  const totalUnc = stock.cell_unclaimed_with_manufacturer_mw + stock.cell_unclaimed_with_reseller_mw + stock.module_unclaimed_with_manufacturer_mw + stock.module_unclaimed_with_reseller_mw;
  const totalStock = stock.cell_with_manufacturer_mw + stock.cell_with_reseller_mw + stock.module_with_manufacturer_mw + stock.module_with_reseller_mw + totalUnc;

  const ins = [];

  // 1
  ins.push({
    tag: 'GROWTH',
    head: `Cell manufacturing scaled ${(ytC[2025]/ytC[2022]).toFixed(0)}× from 2022 to 2025`,
    body: `Total DCR-eligible cell MW grew from <span class="num">${fmtMW(ytC[2022])}</span> in 2022 to <span class="num">${fmtMW(ytC[2025])}</span> in 2025. 2026 has already booked <span class="num">${fmtMW(ytC[2026])} MW</span> through May — annualising to roughly <span class="num">${fmtMW(DATA.derived.projection2026.cell_mfg.projected_full_year)} MW</span>.`,
    chart: svgSpark(yrs.map(y => ytC[y]||0), { color: FT.cell, w: 100, h: 60, sw: 2, fill: FT.cell, dot: true })
  });

  // 2 fragmentation in plain language (no HHI)
  ins.push({
    tag: 'FRAGMENTATION',
    head: `Module field exploded from 1 maker to ${DATA.derived.activeModule[2025]} in three years`,
    body: `Module sector has rapidly broadened. From a single active producer in 2022, <span class="num">${DATA.derived.activeModule[2024]}</span> companies were active in 2024 and <span class="num">${DATA.derived.activeModule[2025]}</span> in 2025. Cell remains relatively tight with <span class="num">${DATA.derived.activeCell[2025]}</span> active producers.`,
    chart: svgSpark(yrs.map(y => DATA.derived.activeModule[y]||0), { color: FT.module, w: 100, h: 60, sw: 2, fill: FT.module, dot: true })
  });

  // 3 unclaimed
  ins.push({
    tag: 'COMPLIANCE',
    head: `Nearly half of all live stock — ${fmtMW(totalUnc)} MW — sits unclaimed`,
    body: `Out of <span class="num">${fmtMW(totalStock)} MW</span> total live stock, <span class="num">${(totalUnc/totalStock*100).toFixed(1)}%</span> has not been claimed against a buyer. Module unclaimed-with-manufacturer alone runs at <span class="num">${fmtMW(stock.module_unclaimed_with_manufacturer_mw)} MW</span>.`,
    chart: svgSpark([stock.cell_with_manufacturer_mw, stock.module_with_manufacturer_mw, stock.cell_unclaimed_with_manufacturer_mw, stock.module_unclaimed_with_manufacturer_mw], { color: FT.red, w: 100, h: 60, sw: 2, fill: FT.red, dot: true })
  });

  // 4 top mover
  const mv = DATA.derived.moversCell.risers[0];
  ins.push({
    tag: 'STANDOUT',
    head: `${mv.name} surged ${fmtPct(mv.growth_pct)} year-on-year`,
    body: `Cell production jumped from <span class="num">${fmtMW(mv.v0)} MW (2024)</span> to <span class="num">${fmtMW(mv.v1)} MW (2025)</span>, catapulting the company to the top of the cell rankings.`,
    chart: svgSpark([mv.v0, mv.v1], { color: FT.green, w: 100, h: 60, sw: 2, fill: FT.green, dot: true })
  });

  // 5 bottleneck
  ins.push({
    tag: 'STRUCTURE',
    head: `Cell is the bottleneck — 18 cell makers feed 140 module makers`,
    body: `The ratio of <span class="num">7.8</span> module manufacturers per cell manufacturer means cell capacity gates total DCR throughput; module makers are vying for an upstream constraint.`,
    chart: svgSpark([18, 140], { color: FT.olive, w: 100, h: 60, sw: 2, fill: FT.olive, dot: true })
  });

  // 6 ALMM
  const cellAlmm = DATA.derived.companiesCell.filter(c=>c.is_almm).length;
  const modAlmm = DATA.derived.companiesModule.filter(c=>c.is_almm).length;
  ins.push({
    tag: 'POLICY',
    head: `ALMM gating is module-only: ${modAlmm} module makers carry it, ${cellAlmm} cell makers do`,
    body: `In this dataset, <span class="num">${modAlmm}/${DATA.derived.companiesModule.length}</span> module manufacturers carry an ALMM tag (Approved List of Models &amp; Manufacturers) versus <span class="num">${cellAlmm}/${DATA.derived.companiesCell.length}</span> cell manufacturers.`,
    chart: svgSpark([modAlmm, DATA.derived.companiesModule.length - modAlmm, cellAlmm, DATA.derived.companiesCell.length - cellAlmm], { color: FT.teal, w: 100, h: 60, sw: 2, fill: FT.teal })
  });

  // 7 geography
  const tn = DATA.states.find(s => s.state === 'Tamil Nadu');
  const mh = DATA.states.find(s => s.state === 'Maharashtra');
  ins.push({
    tag: 'GEOGRAPHY',
    head: `Production lives in Tamil Nadu, distribution in Maharashtra`,
    body: `Tamil Nadu holds <span class="num">${fmtMW(tn.mod_mfg)} MW</span> of manufacturer-held module stock — the country's largest. Maharashtra holds <span class="num">${fmtMW(mh.mod_res)} MW</span> in reseller hands — also the country's largest. TN is the production state, MH is the distribution hub.`,
    chart: svgSpark([tn.mod_mfg, mh.mod_res, tn.mod_res, mh.mod_mfg], { color: FT.gold, w: 100, h: 60, sw: 2, fill: FT.gold })
  });

  // 8 projection
  const pC = DATA.derived.projection2026.cell_mfg.projected_full_year;
  const pM = DATA.derived.projection2026.module_mfg.projected_full_year;
  const gC = (pC/ytC[2025]-1)*100, gM = (pM/ytM[2025]-1)*100;
  ins.push({
    tag: 'OUTLOOK',
    head: `2026 trajectory: cell ${fmtPct(gC)} vs 2025, module ${fmtPct(gM)} vs 2025`,
    body: `If the Jan–May run-rate holds, full-year 2026 manufacturing reaches <span class="num">${fmtMW(pC)} MW</span> cell and <span class="num">${fmtMW(pM)} MW</span> module. Cell continues to outpace module in absolute terms; module growth is decelerating after the 5× surge in 2024.`,
    chart: svgSpark([ytC[2025], pC], { color: FT.navy, w: 100, h: 60, sw: 2, fill: FT.navy, dot: true })
  });

  document.getElementById('insightsList').innerHTML = ins.map(i => `
    <div class="insight-row">
      <div class="insight-thumb">${i.chart}</div>
      <div class="insight-body">
        <div class="insight-tag">${i.tag}</div>
        <h4>${i.head}</h4>
        <p>${i.body}</p>
      </div>
    </div>`).join('');
}
