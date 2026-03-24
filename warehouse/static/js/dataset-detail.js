'use strict';

function toggleDistCard(id) {
  const body = document.getElementById('dist-body-' + id);
  const chev = document.getElementById('dist-chev-' + id);
  const card = body?.closest('[data-dist-card]');
  if (!body) return;
  const isOpen = !body.classList.contains('hidden');
  if (isOpen) {
    body.classList.add('hidden');
    chev?.classList.remove('rotate-180');
    card?.style.setProperty('border-color', '#e5e7eb');
  } else {
    body.classList.remove('hidden');
    chev?.classList.add('rotate-180');
    card?.style.setProperty('border-color', '#f04600');
  }
}

function downloadJsonLd() {
  const data     = document.getElementById('jsonld-data').textContent;
  const btn      = document.querySelector('[data-jsonld-filename]');
  const filename = btn ? btn.dataset.jsonldFilename : 'dataset.jsonld';
  const blob = new Blob([data], { type: 'application/ld+json' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

document.addEventListener('DOMContentLoaded', function () {
  if (location.hash) {
    const el = document.querySelector(location.hash);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
});
