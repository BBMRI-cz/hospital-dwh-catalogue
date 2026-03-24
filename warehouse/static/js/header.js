'use strict';

function switchLang(code) {
  document.getElementById('lang-input').value = code;
  document.getElementById('lang-form').submit();
}

function toggleCatMenu() {
  document.getElementById('cat-user-panel').classList.toggle('hidden');
}

document.addEventListener('click', function (e) {
  const menu = document.getElementById('cat-user-menu');
  if (menu && !menu.contains(e.target)) {
    document.getElementById('cat-user-panel')?.classList.add('hidden');
  }
});
