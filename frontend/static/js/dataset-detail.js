'use strict';

(function () {
  function toggleDistCard(id) {
    const body = document.getElementById('dist-body-' + id);
    const chev = document.getElementById('dist-chev-' + id);
    const card = body?.closest('[data-dist-card]');
    if (!body) return;
    const isOpen = !body.classList.contains('hidden');
    if (isOpen) {
      body.classList.add('hidden');
      chev?.classList.remove('rotate-180');
      card?.classList.remove('border-mou-orange');
      card?.classList.add('border-site-border');
    } else {
      body.classList.remove('hidden');
      chev?.classList.add('rotate-180');
      card?.classList.remove('border-site-border');
      card?.classList.add('border-mou-orange');
    }
  }

  function setExportMenuState(isOpen) {
    const menu = document.getElementById('export-menu');
    const toggle = document.querySelector('[data-export-action="toggle-menu"]');
    if (!menu || !toggle) return;
    menu.classList.toggle('hidden', !isOpen);
    toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  }

  function toggleExportMenu() {
    const menu = document.getElementById('export-menu');
    if (!menu) return;
    setExportMenuState(menu.classList.contains('hidden'));
  }

  function downloadJsonLd(filename) {
    const payload = document.getElementById('jsonld-data')?.textContent;
    if (!payload) return;

    const blob = new Blob([payload], { type: 'application/ld+json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename || 'dataset.jsonld';
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 0);
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (location.hash) {
      var el = document.querySelector(location.hash);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });

  document.addEventListener('click', function (event) {
    const exportButton = event.target.closest('[data-export-action]');
    if (exportButton) {
      if (exportButton.dataset.exportAction === 'toggle-menu') {
        toggleExportMenu();
      } else if (exportButton.dataset.exportAction === 'download-jsonld') {
        downloadJsonLd(exportButton.dataset.exportFilename);
        setExportMenuState(false);
      }
      return;
    }

    const distToggle = event.target.closest('[data-dist-toggle]');
    if (distToggle) {
      if (event.target.closest('[data-card-ignore-toggle]')) {
        return;
      }
      toggleDistCard(distToggle.dataset.distId);
      return;
    }

    const container = document.getElementById('export-split-btn');
    if (container && !container.contains(event.target)) {
      setExportMenuState(false);
    }
  });
})();
