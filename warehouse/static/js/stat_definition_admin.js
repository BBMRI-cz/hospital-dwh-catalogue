/**
 * Cascading table → column dropdown for StatDefinition admin.
 *
 * When a MOLGENIS table is selected, this script filters the column dropdown
 * to show only columns belonging to that table.  The full schema is embedded
 * in the column choices' display text as "table → column", so we parse that.
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var tableField = document.getElementById('id_molgenis_table');
    var columnField = document.getElementById('id_molgenis_column');
    if (!tableField || !columnField) return;

    // Snapshot all original column options.
    var allOptions = Array.prototype.slice.call(columnField.options);

    function filterColumns() {
      var selectedTable = tableField.value;
      var currentVal = columnField.value;

      // Remove all options.
      while (columnField.options.length > 0) {
        columnField.remove(0);
      }

      // Re-add matching options.
      allOptions.forEach(function (opt) {
        if (!opt.value) {
          // Keep the empty/placeholder option.
          columnField.add(opt.cloneNode(true));
          return;
        }
        // Options are formatted as "table → column" in the display text.
        var parts = opt.text.split(' \u2192 ');
        var optTable = parts.length > 1 ? parts[0] : '';
        if (!selectedTable || optTable === selectedTable) {
          var cloned = opt.cloneNode(true);
          // Show just the column name when filtered.
          if (selectedTable && parts.length > 1) {
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
