'use strict';

(function () {
  function submitLanguage(code) {
    const input = document.getElementById('lang-input');
    const form = document.getElementById('lang-form');
    if (!input || !form) {
      return;
    }
    input.value = code;
    form.submit();
  }

  function setUserMenuOpen(isOpen) {
    const panel = document.getElementById('cat-user-panel');
    const toggle = document.querySelector('[data-user-menu-toggle]');
    if (!panel || !toggle) {
      return;
    }
    panel.classList.toggle('hidden', !isOpen);
    toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  }

  function toggleUserMenu() {
    const panel = document.getElementById('cat-user-panel');
    if (!panel) {
      return;
    }
    setUserMenuOpen(panel.classList.contains('hidden'));
  }

  document.addEventListener('click', function (event) {
    const languageButton = event.target.closest('[data-lang-switch]');
    if (languageButton) {
      submitLanguage(languageButton.dataset.languageCode);
      return;
    }

    const userMenuButton = event.target.closest('[data-user-menu-toggle]');
    if (userMenuButton) {
      toggleUserMenu();
      return;
    }

    const menu = document.getElementById('cat-user-menu');
    if (menu && !menu.contains(event.target)) {
      setUserMenuOpen(false);
    }
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      setUserMenuOpen(false);
    }
  });
})();
