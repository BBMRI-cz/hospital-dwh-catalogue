'use strict';

function filterTableList(inp) {
  const v = inp.value.toLowerCase();
  inp.closest('.card').querySelectorAll('.tbl-row').forEach(row => {
    row.style.display = row.dataset.tbl.includes(v) ? '' : 'none';
  });
}

function filterTableModalCols(inp, modalId) {
  const v = inp.value.toLowerCase();
  document.getElementById(modalId).querySelectorAll('.tbl-col-row').forEach(row => {
    row.style.display = row.dataset.col.includes(v) ? '' : 'none';
  });
}

function toggleColDesc(id) {
  const row  = document.getElementById(id);
  const chevId = id.replace('tbl-col-desc-', 'tbl-chev-');
  const chev = document.getElementById(chevId);
  const hidden = row.classList.contains('hidden');
  row.classList.toggle('hidden', !hidden);
  if (chev) chev.style.transform = hidden ? 'rotate(180deg)' : '';
}
