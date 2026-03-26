'use strict';

(function () {
  const CART_ICON_ADD    = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/></svg>';
  const CART_ICON_REMOVE = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';

  function getCartConfig() {
    try {
      const el = document.getElementById('cart-config');
      return el ? JSON.parse(el.textContent) : {};
    } catch (e) { return {}; }
  }

  function getCsrf() {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  function ajaxCartToggle(btn, event) {
    event.stopPropagation();
    const cfg   = getCartConfig();
    const app   = btn.dataset.app;
    const name  = btn.dataset.name;
    const title = btn.dataset.title;
    const body  = new URLSearchParams({ app, name, title });
    btn.disabled = true;
    fetch(cfg.cartAddUrl, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCsrf(),
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: body.toString(),
    })
    .then(r => r.json())
    .then(json => {
      if (!json.success) return;
      const nowInCart = json.in_cart;
      document.querySelectorAll(`button[data-name="${name}"]`).forEach(b => {
        b.dataset.inCart = nowInCart ? 'true' : 'false';
        if (b.dataset.cartHero) {
          const labelAdd    = b.dataset.labelAdd    || cfg.labelAdd    || 'Add to cart';
          const labelRemove = b.dataset.labelRemove || cfg.labelRemove || 'Remove from cart';
          b.innerHTML        = (nowInCart ? CART_ICON_REMOVE : CART_ICON_ADD) + ' ' + (nowInCart ? labelRemove : labelAdd);
          b.title            = nowInCart ? labelRemove : labelAdd;
          b.style.background = nowInCart ? '#dc2626' : '#f04600';
        } else {
          b.innerHTML = nowInCart ? CART_ICON_REMOVE : CART_ICON_ADD;
          b.title     = nowInCart ? (cfg.labelRemove || 'Remove from cart') : (cfg.labelAdd || 'Add to cart');
          ['text-txt-muted', 'text-red-400', 'text-mou-cyan',
           'hover:text-orange-500', 'hover:text-red-600', 'hover:text-cyan-600',
           'hover:bg-orange-50', 'hover:bg-red-50', 'hover:bg-cyan-50'].forEach(c => b.classList.remove(c));
          if (nowInCart) {
            b.classList.add('text-red-400', 'hover:text-red-600', 'hover:bg-red-50');
          } else {
            b.classList.add('text-mou-cyan', 'hover:text-orange-500', 'hover:bg-orange-50');
          }
        }
      });
      const badge = document.getElementById('cart-badge');
      if (badge) {
        badge.textContent = json.cart_count;
        if (json.cart_count > 0) badge.classList.remove('hidden');
        else badge.classList.add('hidden');
      }
    })
    .catch(() => {})
    .finally(() => { btn.disabled = false; });
  }

  function ajaxCartAdd(form, event) {
    event.preventDefault();
    event.stopPropagation();
    const data = new FormData(form);
    fetch(form.action, {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      body: data,
    })
    .then(r => r.json())
    .then(json => {
      if (!json.success) return;
      const badge = document.getElementById('cart-badge');
      if (badge) {
        badge.textContent = json.cart_count;
        if (json.cart_count > 0) badge.classList.remove('hidden');
        else badge.classList.add('hidden');
      }
      const btn = form.querySelector('button[type="submit"]');
      if (btn) {
        btn.classList.add('text-orange-500');
        setTimeout(() => btn.classList.remove('text-orange-500'), 800);
      }
    })
    .catch(() => {});
    return false;
  }

  window.getCsrf        = getCsrf;
  window.ajaxCartToggle = ajaxCartToggle;
  window.ajaxCartAdd    = ajaxCartAdd;
})();
