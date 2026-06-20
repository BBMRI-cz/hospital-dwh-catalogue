/**
 * stat-charts.js - Render statistic charts from StatResult distribution data.
 *
 * Reads chart definitions from a <script type="application/json" id="stat-charts-data">
 * data island. Each entry produces a Chart.js chart on a matching <canvas>,
 * plus a custom HTML legend rendered under the canvas. The server-provided
 * chart_type is used as the default, and users can switch each chart in place.
 *
 * Expected JSON structure:
 *   [ { "label": "...", "table_name": "...", "column_name": "...",
 *       "chart_type": "doughnut"|"bar",
 *       "data": { "value1": count, "value2": count, ... } }, ... ]
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

  /* -- MMCI-inspired colour palette ---------------------------------------- */
  var PALETTE = [
    '#53c0d7',  /* mmci-cyan    */
    '#f04600',  /* mmci-orange  */
    '#007fc8',  /* mmci-blue    */
    '#f59e0b',  /* amber        */
    '#10b981',  /* emerald      */
    '#8b5cf6',  /* violet       */
    '#ec4899',  /* pink         */
    '#6366f1',  /* indigo       */
    '#14b8a6',  /* teal         */
    '#ef4444',  /* red          */
    '#84cc16',  /* lime         */
    '#0ea5e9',  /* sky          */
    '#d946ef',  /* fuchsia      */
    '#f97316',  /* orange       */
    '#22d3ee',  /* cyan         */
    '#a3e635',  /* lime-light   */
  ];

  var MAX_LEGEND_ITEMS = 8;
  var chartInstances = {};
  var ACTIVE_BUTTON_CLASSES = ['bg-mmci-blue', 'text-white', 'border-mmci-blue', 'shadow-sm'];
  var INACTIVE_BUTTON_CLASSES = [
    'text-txt-muted',
    'border-transparent',
    'hover:bg-mmci-blue-light',
  ];

  function pickColors(n) {
    var out = [];
    for (var i = 0; i < n; i++) out.push(PALETTE[i % PALETTE.length]);
    return out;
  }

  function normaliseChartType(type) {
    return type === 'bar' ? 'bar' : 'doughnut';
  }

  function chartNumber(entry, fallbackIndex) {
    var parsed = Number(entry.canvas_idx);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallbackIndex + 1;
  }

  function setButtonClasses(button, active) {
    ACTIVE_BUTTON_CLASSES.forEach(function (className) {
      button.classList.toggle(className, active);
    });
    INACTIVE_BUTTON_CLASSES.forEach(function (className) {
      button.classList.toggle(className, !active);
    });
    button.setAttribute('aria-pressed', active ? 'true' : 'false');
  }

  function updateToggleButtons(n, chartType) {
    var buttons = document.querySelectorAll('[data-chart-toggle="' + n + '"]');
    buttons.forEach(function (button) {
      setButtonClasses(button, button.getAttribute('data-chart-type') === chartType);
    });
  }

  /* -- Plugin: total count in the doughnut centre ------------------------- */
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

  function parsedTooltipValue(ctx) {
    if (typeof ctx.parsed === 'number') return ctx.parsed;
    if (ctx.parsed && typeof ctx.parsed.y === 'number') return ctx.parsed.y;
    if (ctx.parsed && typeof ctx.parsed.x === 'number') return ctx.parsed.x;
    return 0;
  }

  function tooltipLabel(total) {
    return function (ctx) {
      var value = parsedTooltipValue(ctx);
      var pct = total > 0
        ? ((value / total) * 100).toFixed(1)
        : '0.0';
      return ' ' + ctx.label + ': ' + value.toLocaleString() + ' (' + pct + '%)';
    };
  }

  function buildDoughnutConfig(labels, values, colors, total) {
    return {
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
        maintainAspectRatio: false,
        cutout: '60%',
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: tooltipLabel(total),
            },
          },
        },
        animation: { duration: 500, easing: 'easeInOutQuart' },
      },
    };
  }

  function buildBarConfig(labels, values, colors, total) {
    return {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderColor: colors,
          borderWidth: 1,
          borderRadius: 3,
          maxBarThickness: 32,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: tooltipLabel(total),
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: '#4b5563',
              font: { size: 10 },
              maxRotation: 35,
              minRotation: 0,
            },
          },
          y: {
            beginAtZero: true,
            grid: { color: '#e5e7eb' },
            ticks: {
              color: '#4b5563',
              font: { size: 10 },
              precision: 0,
            },
          },
        },
        animation: { duration: 500, easing: 'easeInOutQuart' },
      },
    };
  }

  /* -- Build a custom HTML legend under each canvas ----------------------- */
  function buildLegend(legendEl, labels, values, colors) {
    legendEl.textContent = '';
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

  function renderChart(entry, n, chartType) {
    var canvas = document.getElementById('stat-chart-' + n);
    var legEl  = document.getElementById('stat-chart-legend-' + n);
    if (!canvas || !entry.data || Object.keys(entry.data).length === 0) return;

    var labels = Object.keys(entry.data);
    var values = labels.map(function (k) { return Number(entry.data[k]) || 0; });
    var colors = pickColors(labels.length);
    var total  = values.reduce(function (a, b) { return a + b; }, 0);
    var selectedType = normaliseChartType(chartType);

    if (chartInstances[n]) {
      chartInstances[n].destroy();
    }

    chartInstances[n] = new Chart(
      canvas,
      selectedType === 'bar'
        ? buildBarConfig(labels, values, colors, total)
        : buildDoughnutConfig(labels, values, colors, total)
    );

    if (legEl) buildLegend(legEl, labels, values, colors);
    updateToggleButtons(n, selectedType);
  }

  function bindToggleButtons(entry, n) {
    var buttons = document.querySelectorAll('[data-chart-toggle="' + n + '"]');
    buttons.forEach(function (button) {
      button.addEventListener('click', function () {
        var chartType = normaliseChartType(button.getAttribute('data-chart-type'));
        entry.chart_type = chartType;
        renderChart(entry, n, chartType);
      });
    });
  }

  /* -- Render each chart -------------------------------------------------- */
  charts.forEach(function (entry, idx) {
    var n = chartNumber(entry, idx);
    entry.canvas_idx = n;
    renderChart(entry, n, normaliseChartType(entry.chart_type));
    bindToggleButtons(entry, n);
  });
})();
