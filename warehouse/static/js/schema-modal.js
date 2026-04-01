'use strict';

/* Global schema data — populated by each page that uses ⓘ buttons */
let SCHEMA_DATA = {};

function loadSchemaData(jsonElementId) {
  try {
    const el = document.getElementById(jsonElementId);
    if (el) SCHEMA_DATA = JSON.parse(el.textContent);
  } catch (e) { console.warn('Could not parse schema data', e); }
}

function showSchemaModal(semantics) {
  const s = SCHEMA_DATA[semantics];
  if (!s) return;

  document.getElementById('sm-prefix').textContent   = s.prefix + ':';
  document.getElementById('sm-label').textContent    = s.label || s.local_name;
  document.getElementById('sm-name').textContent     = s.prefix + ':' + s.local_name;
  document.getElementById('sm-desc').textContent     = s.description;
  document.getElementById('sm-uri').href             = s.uri;
  document.getElementById('sm-uri-text').textContent = s.uri;

  const reqEl  = document.getElementById('sm-req');
  const cardEl = document.getElementById('sm-card');
  const reqMap = {
    mandatory:   ['Mandatory',   'bg-green-50 text-green-800 border-green-200'],
    recommended: ['Recommended', 'bg-amber-50 text-amber-800 border-amber-200'],
    optional:    ['Optional',    'bg-gray-100 text-gray-500 border-gray-200'],
    deprecated:  ['Deprecated',  'bg-red-50 text-red-700 border-red-200'],
  };
  const [rlabel, cls] = reqMap[s.requirement] || reqMap.optional;
  reqEl.innerHTML = `<span class="inline-flex items-center gap-1.5 font-mono text-[10px] px-2.5 py-1 rounded border ${cls}">
    <span class="w-1.5 h-1.5 rounded-full inline-block" style="background:currentColor;opacity:.7"></span>
    ${rlabel}
  </span>`;

  if (s.cardinality) {
    cardEl.textContent = s.cardinality;
    cardEl.style.display = '';
  } else {
    cardEl.style.display = 'none';
  }

  document.getElementById('schema-modal').showModal();
}

/* Auto-init: load schema data if #schema-data element is present on the page */
document.addEventListener('DOMContentLoaded', function () {
  if (document.getElementById('schema-data')) {
    loadSchemaData('schema-data');
  }
});
