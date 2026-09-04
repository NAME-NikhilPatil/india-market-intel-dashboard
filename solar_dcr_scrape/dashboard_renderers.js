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

  // ── Footer 3: YoY % growth row (2026 YTD vs same months of 2025) ──
  const yoyRow2026 = `<tr class="tot-row" style="background: transparent;">
    <td class="left sticky-l" style="font-style: italic; color: var(--ink-mid); font-weight: 500;">YoY 2026 / 2025</td>
    ${cols.map((col, ci) => {
      const validMonths = col.months.filter(mi => mi + 1 <= LAST_MONTH);
      if (!validMonths.length) return `<td class="future-month" style="background: transparent; border-bottom: none; padding: 0;"></td>`;
      let v26 = 0, v25 = 0;
      validMonths.forEach(mi => { v26 += monthlyMatrix[2026][mi]; v25 += monthlyMatrix[2025][mi]; });
      if (v25 === 0) return `<td class="num zero">—</td>`;
      const pct = (v26 - v25) / v25 * 100;
      const color = pct > 0 ? 'var(--green)' : 'var(--claret)';
      const partial = isQ && validMonths.length < col.months.length;
      return `<td class="num" style="color: ${color}; font-weight: 600;" data-csv="${pct.toFixed(1)}">${pct>0?'+':''}${pct.toFixed(0)}%${partial?'*':''}</td>`;
    }).join('')}
    <td class="num annual sticky-r" data-csv="">${(() => {
      const y26 = monthlyMatrix[2026].slice(0, LAST_MONTH).reduce((s,v)=>s+v,0);
      const y25ytd = monthlyMatrix[2025].slice(0, LAST_MONTH).reduce((s,v)=>s+v,0);
      if (y25ytd === 0) return '—';
      const pct = (y26 - y25ytd) / y25ytd * 100;
      const color = pct > 0 ? 'var(--green)' : 'var(--claret)';
      return `<span style="color: ${color}; font-weight: 700;">${pct>0?'+':''}${pct.toFixed(0)}%</span>`;
    })()}</td>
  </tr>`;

  wrap.innerHTML = `<table class="data-tbl" id="marketTable" style="min-width: 100%;">
    <thead>${head}</thead>
    <tbody>${body}${avgRow}${yoyRow}${yoyRow2026}</tbody>
  </table>${isQ?'<div style="margin-top: 6px; font-size: 10.5px; color: var(--ink-mid); font-style: italic;">Q* = partial quarter (fewer than 3 months of data).</div>':''}`;
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
  // Show every company in the segment; narrow to search matches when searching
  let comps = companiesForSeg(seg);
  if (searchActive()) comps = applySearchFilter(comps);
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
    <th class="sticky-l left" rowspan="2">${searchActive() ? 'Matches' : 'All ' + comps.length} · ${seg}</th>
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
    <td class="sticky-l left">${searchActive() ? 'Match total' : 'All '+seg+' total'}</td>
    ${footCells}
    <td class="sticky-r" data-csv="${grandTot.toFixed(2)}">${fmtMW(grandTot)}</td>
  </tr>`;

  wrap.innerHTML = `<table class="data-tbl" id="monthlyVolTable">
    <thead>${headRow1}${headRow2}</thead>
    <tbody>${body}${footer}</tbody>
  </table>${isQuarterly?'<div style="margin-top:6px; font-size: 10.5px; color: var(--ink-mid); font-style: italic;">Q* = partial quarter (fewer than 3 months of data).</div>':''}`;
}

