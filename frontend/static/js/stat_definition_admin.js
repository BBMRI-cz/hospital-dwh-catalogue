/**
 * Cascading dropdowns for StatDefinition admin:
 *   1. dataset → distribution
 *   2. molgenis_table → molgenis_column
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {

    // -------------------------------------------------------------------------
    // 1. dataset → distribution cascade
    // -------------------------------------------------------------------------
    var datasetField = document.getElementById('id_dataset');
    var distField = document.getElementById('id_distribution');

    if (datasetField && distField && distField.options) {
      // Mapping: distribution pk → dataset pk, embedded by the form as JSON.
      var distMap = {};
      try {
        distMap = JSON.parse(distField.getAttribute('data-dist-map') || '{}');
      } catch (e) { /* ignore parse errors */ }

      // Snapshot all distribution options.
      var allDistOptions = Array.prototype.slice.call(distField.options);

      function filterDistributions() {
        var selectedDataset = datasetField.value;
        var currentVal = distField.value;

        while (distField.options.length > 0) {
          distField.remove(0);
        }

        // No dataset selected: show all distributions with full labels.
        if (!selectedDataset) {
          allDistOptions.forEach(function (opt) {
            distField.add(opt.cloneNode(true));
          });
          distField.value = currentVal;
          if (distField.selectedIndex < 0 && distField.options.length > 0) {
            distField.selectedIndex = 0;
          }
          return;
        }

        allDistOptions.forEach(function (opt) {
          if (!opt.value) {
            distField.add(opt.cloneNode(true));
            return;
          }
          if (distMap[opt.value] === selectedDataset) {
            var cloned = opt.cloneNode(true);
            // Strip the "Dataset → " prefix; show only the distribution title.
            var parts = cloned.text.split(' \u2192 ');
            if (parts.length > 1) {
              cloned.text = parts.slice(1).join(' \u2192 ');
            }
            distField.add(cloned);
          }
        });

        distField.value = currentVal;
        if (distField.selectedIndex < 0 && distField.options.length > 0) {
          distField.selectedIndex = 0;
        }
      }

      datasetField.addEventListener('change', filterDistributions);
      filterDistributions();
    }

    // -------------------------------------------------------------------------
    // 2. molgenis_table → molgenis_column cascade
    // -------------------------------------------------------------------------
    var tableField = document.getElementById('id_molgenis_table');
    var columnField = document.getElementById('id_molgenis_column');
    // Guard: fields may not exist on this page, or may be plain text inputs
    // (when MOLGENIS is unreachable and no fallback choices are available).
    if (!tableField || !columnField || !columnField.options) return;

    // Snapshot all original column options.
    var allOptions = Array.prototype.slice.call(columnField.options);

    function filterColumns() {
      var selectedTable = tableField.value;
      var currentVal = columnField.value;

      // Remove all options.
      while (columnField.options.length > 0) {
        columnField.remove(0);
      }

      // If no table is selected, show only the placeholder — forces the user
      // to pick a table before seeing column choices.
      if (!selectedTable) {
        var placeholder = allOptions.find(function (opt) { return !opt.value; });
        if (placeholder) columnField.add(placeholder.cloneNode(true));
        return;
      }

      // Re-add options that belong to the selected table.
      allOptions.forEach(function (opt) {
        if (!opt.value) {
          // Keep the empty/placeholder option.
          columnField.add(opt.cloneNode(true));
          return;
        }
        // Options are formatted as "table → column" in the display text.
        var parts = opt.text.split(' \u2192 ');
        var optTable = parts.length > 1 ? parts[0] : '';
        if (optTable === selectedTable) {
          var cloned = opt.cloneNode(true);
          // Show just the column name when a table is selected.
          if (parts.length > 1) {
            cloned.text = parts[1];
          }
          columnField.add(cloned);
        }
      });

      // Restore previous selection if it's still valid.
      columnField.value = currentVal;
      if (columnField.selectedIndex < 0 && columnField.options.length > 0) {
        columnField.selectedIndex = 0;
      }
    }

    tableField.addEventListener('change', filterColumns);
    // Run once on page load to set the initial filter state.
    filterColumns();
  });
})();
