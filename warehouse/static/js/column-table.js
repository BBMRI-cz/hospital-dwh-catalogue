'use strict';

function filterColumns(inp) {
  const v = inp.value.toLowerCase();
  inp.closest('.card').querySelectorAll('.col-row').forEach(row => {
    row.style.display = row.dataset.col.includes(v) ? '' : 'none';
  });
}

function toggleColDesc(id) {
  const row    = document.getElementById(id);
  const chev   = document.getElementById('chev-' + id);
  const hidden = row.classList.contains('hidden');
  row.classList.toggle('hidden', !hidden);
  if (chev) chev.style.transform = hidden ? 'rotate(180deg)' : '';
}
