// Smoke test: load the dashboard HTML in jsdom, mock Chart/d3 globals, and verify all renderers run.
const fs = require('fs');
const path = require('path');
const { JSDOM, ResourceLoader } = require('jsdom');

const htmlPath = path.join(__dirname, 'solar_dcr_dashboard.html');
const html = fs.readFileSync(htmlPath, 'utf8');

// We will not let jsdom fetch the external CDN scripts. Instead, we mock Chart/d3 globals before our inline <script> runs.
// Strategy: strip <script src=...> tags so jsdom doesn't try to load them, then inject mocks via a beforeParse-equivalent.

const stripped = html.replace(/<script\s+src="[^"]+"[^>]*>\s*<\/script>/g, '');

const errors = [];
const warnings = [];

const dom = new JSDOM(stripped, {
  runScripts: 'outside-only',  // don't auto-run; we inject mocks first
  pretendToBeVisual: true,
  beforeParse(win) {
    // mocks
    function makeChartCtor() {
      function Chart(ctx, cfg) {
        this.ctx = ctx; this.cfg = cfg;
        this.data = cfg && cfg.data; this.options = cfg && cfg.options;
      }
      Chart.prototype.destroy = function() {};
      Chart.register = () => {};
      Chart.defaults = { color: '', borderColor: '', font: {}, plugins: { datalabels: {} } };
      return Chart;
    }
    win.Chart = makeChartCtor();
    win.ChartDataLabels = function(){};
    // d3 minimal stubs
    function sankey() {
      const f = function(graph) {
        // Assign minimal layout positions
        graph.nodes.forEach((n, i) => { n.x0=i*10; n.x1=i*10+18; n.y0=10; n.y1=30; n.value = (graph.links.filter(l=>l.source===i||l.target===i).reduce((s,l)=>s+l.value,0)/2) || 0; });
        graph.links.forEach(l => { l.source = graph.nodes[l.source]; l.target = graph.nodes[l.target]; l.width = Math.max(1, l.value/100); });
        return graph;
      };
      f.nodeWidth = () => f; f.nodePadding = () => f; f.extent = () => f;
      return f;
    }
    function sankeyLinkHorizontal() { return () => 'M0,0L1,1'; }

    function d3SelectStub() {
      const stub = {
        append: () => stub,
        attr: () => stub,
        style: () => stub,
        selectAll: () => stub,
        data: () => stub,
        join: () => stub,
        text: () => stub,
        on: () => stub,
      };
      return stub;
    }
    win.d3 = {
      sankey, sankeyLinkHorizontal,
      select: () => d3SelectStub(),
    };
    // Canvas: make getContext return a minimal stub so Chart.js construction doesn't blow up
    win.HTMLCanvasElement.prototype.getContext = function() { return { canvas: this }; };
    // IntersectionObserver mock (jsdom doesn't ship it)
    win.IntersectionObserver = class { constructor(){} observe(){} unobserve(){} disconnect(){} };
    // Console capture
    win.console = {
      log: (...a) => console.log('[page]', ...a),
      warn: (...a) => warnings.push(a.join(' ')),
      error: (...a) => errors.push(a.join(' ')),
    };
    win.addEventListener('error', e => errors.push('window.error: ' + e.message));
  }
});

// Extract inline script and run it
const win = dom.window;
const inline = stripped.match(/<script(?![^>]*src=)[^>]*>([\s\S]*?)<\/script>/);
if (!inline) { console.error('no inline script'); process.exit(2); }

try {
  win.eval(inline[1]);
} catch (e) {
  console.error('UNCAUGHT ERROR while evaluating inline script:');
  console.error(e.stack);
  process.exit(1);
}

// fire DOMContentLoaded since we eval'd after
const ev = new win.Event('DOMContentLoaded');
win.document.dispatchEvent(ev);

// Inspect what was set up (note: const-scoped vars from eval don't attach to win, so we check DOM)
const q = (sel) => win.document.querySelectorAll(sel).length;
const has = (id) => { const e = win.document.getElementById(id); return e ? e.children.length || (e.textContent.trim().length?1:0) : 0; };
console.log('KPI strip cells:', has('kpiStrip'));
console.log('standfirst populated:', !!win.document.getElementById('standfirst').textContent.trim());
console.log('leaderboard rows:', q('#leaderboard tbody tr'));
console.log('state table rows:', q('#stateTable tbody tr'));
console.log('tile map tiles:', q('#tileMap .state-tile'));
console.log('compare pills:', q('#comparePills .pill'));
console.log('insights rows:', q('#insightsList .insight-row'));
console.log('small multiples tiles:', q('#smGrid .sm-tile'));
console.log('mini KPIs:', [1,2,3,4].map(i => has('mini'+i)).join(','));
console.log('heatmap rows:', q('#heatmapWrap tbody tr'));
console.log('sankey svg:', q('#sankeyWrap svg'));
console.log('tier table rows:', q('#tierTable tbody tr'));
console.log('top-annual table rows:', q('#topAnnualTable tbody tr'));
console.log('dual table rows:', q('#dualTable tbody tr'));
console.log('monthly-vol table rows:', q('#monthlyVolTable tbody tr'));
console.log('risers table rows:', q('#risersTable tbody tr'));
console.log('new-entrants rows:', q('#newEntrantsTable tbody tr'));
console.log('fallers table rows:', q('#fallersTable tbody tr'));
// Trigger a drill-panel render to test the per-company monthly tables
win.eval(`if (typeof renderDrill === 'function') { renderDrill('TP Solar Limited', 'cell'); }`);
console.log('drill panel monthly tables:', q('#drillPanel .drill-monthly table'));
console.log('drill annual-comparison table:', q('#drillPanel .data-tbl'));
console.log('state-mix table rows:', q('#stateMixTable tbody tr'));
console.log('arrivals table rows:', q('#arrivalsTable tbody tr'));
console.log('market table body rows:', q('#marketTable tbody tr'));
console.log('market table header cells:', q('#marketTable thead th'));
console.log('key-events strip cells:', q('#keyEvents .ke'));

// Verify quarterly toggle works
win.STATE.monVolGran = 'quarterly';
win.rerenderAll();
const qHeaderCells = win.document.querySelectorAll('#monthlyVolTable thead tr:nth-child(2) th').length;
console.log('quarterly view header cells (expect ~20: 4 quarters × 5 years + 5 FYs):', qHeaderCells);
win.STATE.monVolGran = 'monthly';
win.rerenderAll();

// Test: apply search filter and rerender, confirm tables shrink to matches
win.STATE.search = 'TP Solar';
win.rerenderAll();
console.log('--- with search "TP Solar" ---');
console.log('leaderboard rows (search):', q('#leaderboard tbody tr'));
console.log('small multiples (search):', q('#smGrid .sm-tile'));
console.log('top-annual rows (search):', q('#topAnnualTable tbody tr'));
console.log('monthly-vol rows (search):', q('#monthlyVolTable tbody tr'));
console.log('dual rows (search):', q('#dualTable tbody tr'));
console.log('risers rows (search):', q('#risersTable tbody tr'));

// Clear search, confirm restoration
win.STATE.search = '';
win.rerenderAll();
console.log('--- search cleared ---');
console.log('leaderboard rows (cleared):', q('#leaderboard tbody tr'));
console.log('small multiples (cleared):', q('#smGrid .sm-tile'));

if (warnings.length) console.log('WARNINGS:', warnings.slice(0,5));
if (errors.length) {
  console.error('ERRORS:'); errors.slice(0,8).forEach(e => console.error(' -', e.slice(0,500)));
  process.exit(1);
}
console.log('\n✅ All renderers executed without errors');
