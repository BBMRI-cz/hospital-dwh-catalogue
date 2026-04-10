'use strict';

(function () {
  let schemaData = {};

  function loadSchemaData(jsonElementId) {
    try {
      const el = document.getElementById(jsonElementId);
      if (el) {
        schemaData = JSON.parse(el.textContent);
      }
    } catch (e) {
      console.warn('Could not parse schema data', e);
    }
  }

  function showSchemaModal(semantics) {
    const schemaTerm = schemaData[semantics];
    if (!schemaTerm) {
      return;
    }

    document.getElementById('sm-prefix').textContent = schemaTerm.prefix + ':';
    document.getElementById('sm-label').textContent = schemaTerm.label || schemaTerm.local_name;
    document.getElementById('sm-name').textContent =
      schemaTerm.prefix + ':' + schemaTerm.local_name;
    document.getElementById('sm-desc').textContent = schemaTerm.description;
    document.getElementById('sm-uri').href = schemaTerm.uri;
    document.getElementById('sm-uri-text').textContent = schemaTerm.uri;

    const reqEl = document.getElementById('sm-req');
    const cardEl = document.getElementById('sm-card');
    const reqMap = {
      mandatory: ['Mandatory', 'bg-green-50 text-green-800 border-green-200'],
      recommended: ['Recommended', 'bg-amber-50 text-amber-800 border-amber-200'],
      optional: ['Optional', 'bg-gray-100 text-gray-500 border-gray-200'],
      deprecated: ['Deprecated', 'bg-red-50 text-red-700 border-red-200'],
    };
    const [label, cls] = reqMap[schemaTerm.requirement] || reqMap.optional;
    reqEl.innerHTML = `<span class="inline-flex items-center gap-1.5 font-mono text-[10px] px-2.5 py-1 rounded border ${cls}">
    <span class="w-1.5 h-1.5 rounded-full inline-block" style="background:currentColor;opacity:.7"></span>
    ${label}
  </span>`;

    if (schemaTerm.cardinality) {
      cardEl.textContent = schemaTerm.cardinality;
      cardEl.style.display = '';
    } else {
      cardEl.style.display = 'none';
    }

    document.getElementById('schema-modal').showModal();
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (document.getElementById('schema-data')) {
      loadSchemaData('schema-data');
    }
  });

  document.addEventListener('click', function (event) {
    const trigger = event.target.closest('[data-schema-button]');
    if (trigger) {
      if (trigger.hasAttribute('data-schema-stop')) {
        event.preventDefault();
      }
      showSchemaModal(trigger.dataset.semantics);
      return;
    }

    const modal = event.target.closest('[data-schema-modal]');
    if (modal && event.target === modal) {
      modal.close();
    }
  });
})();
