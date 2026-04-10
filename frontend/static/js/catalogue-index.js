'use strict';

(function () {
  const SKIP = new Set(['page']);
  const openCards = new Set();

  function getLabels() {
    try {
      const el = document.getElementById('chip-labels');
      return el ? JSON.parse(el.textContent) : {};
    } catch (e) { return {}; }
  }

  function removeFilter(key, val) {
    const params   = new URLSearchParams(window.location.search);
    const existing = params.getAll(key).filter(v => v !== val);
    params.delete(key);
    existing.forEach(v => params.append(key, v));
    params.set('page', '1');
    window.location.search = params.toString();
  }

  function buildChips() {
    const container = document.getElementById('active-chips');
    if (!container) return;
    const LABELS = getLabels();
    const params  = new URLSearchParams(window.location.search);
    container.innerHTML = '';
    let count = 0;
    params.forEach(function (val, key) {
      if (SKIP.has(key) || !val) return;
      const label = LABELS[key] || key;
      const chip  = document.createElement('span');
      chip.className  = 'inline-flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-full border font-medium bg-mou-cyan-light text-cyan-700 border-mou-cyan-border';
      const text = document.createElement('span');
      text.textContent = label + ': ' + val;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.setAttribute('data-key', key);
      btn.setAttribute('data-val', val);
      btn.setAttribute('aria-label', 'Remove filter');
      btn.className  = 'ml-0.5 hover:opacity-70 transition-opacity cursor-pointer';
      btn.innerHTML  = '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
      btn.addEventListener('click', function () {
        removeFilter(this.dataset.key, this.dataset.val);
      });
      chip.appendChild(text);
      chip.appendChild(btn);
      container.appendChild(chip);
      count++;
    });
    if (count > 0) {
      container.classList.remove('hidden');
      container.classList.add('flex');
    }
  }

  function toggleCard(idx) {
    const body = document.getElementById('body-' + idx);
    const chev = document.getElementById('chev-' + idx);
    const card = body?.closest('[data-card]');
    if (!body) return;
    const isOpen = !body.classList.contains('hidden');
    if (isOpen) {
      body.classList.add('hidden');
      chev?.classList.remove('rotate-180');
      card?.classList.remove('border-mou-cyan');
      card?.classList.add('border-site-border');
      openCards.delete(idx);
    } else {
      body.classList.remove('hidden');
      chev?.classList.add('rotate-180');
      card?.classList.remove('border-site-border');
      card?.classList.add('border-mou-cyan');
      openCards.add(idx);
    }
  }

  function filterList(input, listId) {
    const value = input.value.toLowerCase();
    document.querySelectorAll('#' + listId + ' .chk-item').forEach(el => {
      el.style.display = el.textContent.toLowerCase().includes(value) ? '' : 'none';
    });
  }

  document.addEventListener('DOMContentLoaded', buildChips);

  document.addEventListener('click', function (event) {
    const toggle = event.target.closest('[data-card-toggle]');
    if (!toggle) {
      return;
    }
    if (event.target.closest('[data-card-ignore-toggle]')) {
      return;
    }
    toggleCard(toggle.dataset.cardId);
  });

  document.addEventListener('input', function (event) {
    const input = event.target.closest('[data-filter-list]');
    if (!input) {
      return;
    }
    filterList(input, input.dataset.listId);
  });
})();
