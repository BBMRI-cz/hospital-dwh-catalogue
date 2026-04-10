'use strict';

(function () {
  function filterTableList(input) {
    const value = input.value.toLowerCase();
    input.closest('.card').querySelectorAll('.tbl-row').forEach(row => {
      row.style.display = row.dataset.tbl.includes(value) ? '' : 'none';
    });
  }

  function filterTableModalCols(input, modalId) {
    const value = input.value.toLowerCase();
    document.getElementById(modalId).querySelectorAll('.tbl-col-row').forEach(row => {
      row.style.display = row.dataset.col.includes(value) ? '' : 'none';
    });
  }

  function toggleColDesc(id) {
    const row = document.getElementById(id);
    const chevId = id.replace('tbl-col-desc-', 'tbl-chev-');
    const chev = document.getElementById(chevId);
    if (!row) {
      return;
    }
    const hidden = row.classList.contains('hidden');
    row.classList.toggle('hidden', !hidden);
    if (chev) {
      chev.style.transform = hidden ? 'rotate(180deg)' : '';
    }
  }

  function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.showModal();
    }
  }

  document.addEventListener('input', function (event) {
    const tableFilter = event.target.closest('[data-table-filter]');
    if (tableFilter) {
      filterTableList(tableFilter);
      return;
    }

    const modalFilter = event.target.closest('[data-table-modal-filter]');
    if (modalFilter) {
      filterTableModalCols(modalFilter, modalFilter.dataset.modalId);
    }
  });

  document.addEventListener('click', function (event) {
    const trigger = event.target.closest('[data-modal-trigger]');
    if (trigger) {
      openModal(trigger.dataset.modalId);
      return;
    }

    const modal = event.target.closest('[data-modal-dismiss]');
    if (modal && event.target === modal) {
      modal.close();
      return;
    }

    const toggle = event.target.closest('[data-col-toggle]');
    if (!toggle) {
      return;
    }
    if (event.target.closest('[data-col-ignore-toggle]')) {
      return;
    }
    toggleColDesc(toggle.dataset.descId);
  });

  document.addEventListener('keydown', function (event) {
    const trigger = event.target.closest('[data-modal-trigger]');
    if (!trigger) {
      return;
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openModal(trigger.dataset.modalId);
    }
  });
})();
