'use strict';

document.addEventListener('click', function (event) {
  const dismissButton = event.target.closest('[data-toast-dismiss]');
  if (!dismissButton) {
    return;
  }
  dismissButton.closest('[role=alert]')?.remove();
});

setTimeout(function () {
  const c = document.getElementById('toast-container');
  if (c) c.style.transition = 'opacity .4s ease';
  if (c) c.style.opacity    = '0';
  setTimeout(function () { if (c) c.remove(); }, 400);
}, 5000);
