/** Shared Alpine-powered site UI hooks. */
(function () {
  'use strict';

  function readJsonScript(id, fallback) {
    var el = document.getElementById(id);
    if (!el) return fallback;
    try {
      return JSON.parse(el.textContent) || fallback;
    } catch (_) {
      return fallback;
    }
  }

  function ensureToastContainer() {
    var container = document.getElementById('toast-container');
    if (container) return container;

    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'fixed top-20 right-4 z-50 flex flex-col gap-3 pointer-events-none';
    document.body.appendChild(container);
    return container;
  }

  function dismissToast(toast) {
    toast.style.transition = 'opacity .4s';
    toast.style.opacity = '0';
    window.setTimeout(function () {
      toast.remove();
    }, 400);
  }

  function buildErrorToast(title, statusCode) {
    var toast = document.createElement('div');
    toast.setAttribute('role', 'alert');
    toast.className = 'toast-item pointer-events-auto slide-in flex items-start gap-3 rounded-2xl bg-red-50 border border-red-200 shadow-xl px-4 py-3.5 min-w-80 max-w-sm';

    var iconWrap = document.createElement('div');
    iconWrap.className = 'shrink-0 flex items-center justify-center w-8 h-8 rounded-full bg-red-100 mt-0.5';
    iconWrap.innerHTML = [
      '<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24"',
      ' fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"',
      ' stroke-linejoin="round" class="text-red-700">',
      '<circle cx="12" cy="12" r="10"></circle>',
      '<line x1="15" y1="9" x2="9" y2="15"></line>',
      '<line x1="9" y1="9" x2="15" y2="15"></line>',
      '</svg>',
    ].join('');

    var content = document.createElement('div');
    content.className = 'flex-1 min-w-0';

    var heading = document.createElement('p');
    heading.className = 'text-sm font-semibold leading-tight text-red-800';
    heading.textContent = title;

    var body = document.createElement('p');
    body.className = 'text-xs leading-snug mt-0.5 text-red-600';
    body.textContent = '#' + String(statusCode || '');

    content.appendChild(heading);
    content.appendChild(body);

    var closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'shrink-0 mt-0.5 flex items-center justify-center w-6 h-6 rounded-full transition-colors text-red-400 hover:text-red-700 hover:bg-red-100';
    closeButton.setAttribute('aria-label', title);
    closeButton.innerHTML = [
      '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24"',
      ' fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round">',
      '<line x1="18" y1="6" x2="6" y2="18"></line>',
      '<line x1="6" y1="6" x2="18" y2="18"></line>',
      '</svg>',
    ].join('');
    closeButton.addEventListener('click', function () {
      toast.remove();
    });

    toast.appendChild(iconWrap);
    toast.appendChild(content);
    toast.appendChild(closeButton);

    window.setTimeout(function () {
      dismissToast(toast);
    }, 5000);

    return toast;
  }

  document.addEventListener('alpine:init', function () {
    Alpine.data('siteUi', function () {
      return {
        init() {
          if (this._siteUiBound) return;
          this._siteUiBound = true;

          var errorTitle = readJsonScript('site-ui-error-title', 'Error');
          this.$el.addEventListener('htmx:responseError', function (event) {
            var container = ensureToastContainer();
            container.appendChild(buildErrorToast(errorTitle, event.detail.xhr.status));
          });
        },
      };
    });
  });
})();
