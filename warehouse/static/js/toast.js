'use strict';

setTimeout(function () {
  const c = document.getElementById('toast-container');
  if (c) c.style.transition = 'opacity .4s ease';
  if (c) c.style.opacity    = '0';
  setTimeout(function () { if (c) c.remove(); }, 400);
}, 5000);
