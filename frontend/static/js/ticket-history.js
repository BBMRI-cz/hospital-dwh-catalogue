'use strict';

function toggleTicket(pk) {
  const row = document.getElementById('items-' + pk);
  const chev = document.getElementById('chev-' + pk);
  const hidden = row.classList.contains('hidden');
  row.classList.toggle('hidden', !hidden);
  chev.style.transform = hidden ? 'rotate(180deg)' : '';
}
