/**
 * stat-charts.js — Render doughnut charts from StatResult distribution data.
 *
 * Reads chart definitions from a <script type="application/json" id="stat-charts-data">
 * data island.  Each entry produces a Chart.js doughnut on a matching <canvas>,
 * plus a custom HTML legend rendered under the canvas so that all doughnut rings
 * are always the same size regardless of label length.
 *
 * Expected JSON structure:
 *   [ { "label": "…", "table_name": "…", "column_name": "…",
 *       "data": { "value1": count, "value2": count, … } }, … ]
 */
(function () {
  'use strict';

  var el = document.getElementById('stat-charts-data');
  if (!el) return;

  var charts;
  try { charts = JSON.parse(el.textContent); } catch (_) { return; }
  if (!Array.isArray(charts) || charts.length === 0) return;

  var i18nEl = document.getElementById('stat-charts-i18n');
  var labelTotal = 'total';
  try { if (i18nEl) labelTotal = JSON.parse(i18nEl.textContent) || labelTotal; } catch (_) {}

  /* ── MMCI-inspired colour palette ──────────────────────────────────────── */
  var PALETTE = [
    '#53c0d7',  /* mmci-cyan    */
    '#f04600',  /* mmci-orange  */
    '#007fc8',  /* mmci-blue    */
    '#f59e0b',  /* amber       */
    '#10b981',  /* emerald     */
    '#8b5cf6',  /* violet      */
    '#ec4899',  /* pink        */
    '#6366f1',  /* indigo      */
    '#14b8a6',  /* teal        */
    '#ef4444',  /* red         */
    '#84cc16',  /* lime        */
    '#0ea5e9',  /* sky         */
    '#d946ef',  /* fuchsia     */
    '#f97316',  /* orange      */
    '#22d3ee',  /* cyan        */
    '#a3e635',  /* lime-light  */
  ];

  var MAX_LEGEND_ITEMS = 8;

  function pickColors(n) {
    var out = [];
    for (var i = 0; i < n; i++) out.push(PALETTE[i % PALETTE.length]);
    return out;
  }

  /* ── Plugin: total count in the doughnut centre ───────────────────────── */
  var centerTotalPlugin = {
    id: 'centerTotal',
    afterDraw: function (chart) {
      var ds = chart.data.datasets[0];
      if (!ds) return;
      var total = ds.data.reduce(function (a, b) { return a + b; }, 0);
      var ctx = chart.ctx;
      var cx = (chart.chartArea.left + chart.chartArea.right) / 2;
      var cy = (chart.chartArea.top  + chart.chartArea.bottom) / 2;

      ctx.save();
      ctx.textAlign    = 'center';
      ctx.textBaseline = 'middle';

      ctx.font      = 'bold 17px Inter, system-ui, sans-serif';
      ctx.fillStyle = '#374151';  /* mmci txt */
      ctx.fillText(total.toLocaleString(), cx, cy - 7);

      ctx.font      = '10px Inter, system-ui, sans-serif';
      ctx.fillStyle = '#4b5563';  /* mmci txt-muted */
      ctx.fillText(labelTotal, cx, cy + 10);

      ctx.restore();
    },
  };

  /* ── Build a custom HTML legend under each canvas ─────────────────────── */
  function buildLegend(legendEl, labels, values, colors, total) {
    var fragment = document.createDocumentFragment();

    labels.forEach(function (label, i) {
      if (i >= MAX_LEGEND_ITEMS) return;

      var row   = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;gap:7px;min-width:0;';

      var dot   = document.createElement('span');
      dot.style.cssText = 'flex-shrink:0;width:10px;height:10px;border-radius:2px;background:' + colors[i] + ';';

      var text  = document.createElement('span');
      text.style.cssText = [
        'flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;',
        'font-family:\'JetBrains Mono\',monospace;font-size:11px;color:#374151;',
      ].join('');
      text.textContent = label;       /* textContent is XSS-safe */

      var badge = document.createElement('span');
      badge.style.cssText = [
        'flex-shrink:0;font-family:\'JetBrains Mono\',monospace;',
        'font-size:11px;color:#374151;font-variant-numeric:tabular-nums;font-weight:500;',
      ].join('');
      badge.textContent = values[i].toLocaleString();

      row.appendChild(dot);
      row.appendChild(text);
      row.appendChild(badge);
      fragment.appendChild(row);
    });

    if (labels.length > MAX_LEGEND_ITEMS) {
      var more = document.createElement('div');
      more.style.cssText = 'font-size:10px;color:#9ca3af;margin-top:2px;';
      more.textContent   = '+' + (labels.length - MAX_LEGEND_ITEMS) + ' more';
      fragment.appendChild(more);
    }

    legendEl.appendChild(fragment);
  }

  /* ── Render each chart ────────────────────────────────────────────────── */
  charts.forEach(function (entry, idx) {
    var n      = idx + 1;
    var canvas = document.getElementById('stat-chart-' + n);
    var legEl  = document.getElementById('stat-chart-legend-' + n);
    if (!canvas || !entry.data || Object.keys(entry.data).length === 0) return;

    var labels = Object.keys(entry.data);
    var values = labels.map(function (k) { return entry.data[k]; });
    var colors = pickColors(labels.length);
    var total  = values.reduce(function (a, b) { return a + b; }, 0);

    new Chart(canvas, {
      type: 'doughnut',
      plugins: [centerTotalPlugin],
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderWidth: 2,
          borderColor: '#fff',
          hoverBorderColor: '#fff',
          hoverOffset: 4,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,  /* canvas fills its CSS-sized container */
        cutout: '60%',
        plugins: {
          legend: { display: false },  /* replaced by custom HTML legend below */
          tooltip: {
            callbacks: {
              label: function (ctx) {
                var pct = total > 0
                  ? ((ctx.parsed / total) * 100).toFixed(1)
                  : '0.0';
                return ' ' + ctx.label + ': ' + ctx.parsed.toLocaleString() + ' (' + pct + '%)';
              },
            },
          },
        },
        animation: { duration: 500, easing: 'easeInOutQuart' },
      },
    });

    if (legEl) buildLegend(legEl, labels, values, colors, total);
  });
})();
