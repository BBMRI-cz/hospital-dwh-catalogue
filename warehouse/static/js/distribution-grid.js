'use strict';

function toggleDistTile(idx) {
  const body = document.getElementById('distbody-' + idx);
  const tile = document.getElementById('dtile-det-' + idx);
  if (!body) return;
  const isOpen = !body.classList.contains('hidden');
  if (isOpen) {
    body.classList.add('hidden');
    tile?.classList.remove('expanded');
  } else {
    body.classList.remove('hidden');
    tile?.classList.add('expanded');
  }
}
