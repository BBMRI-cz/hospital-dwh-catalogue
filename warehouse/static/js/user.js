document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing...');

    // --- Core Functionality for Dataset Display ---

// Toggle tables display
const tableToggleLinks = document.querySelectorAll('.table-toggle-link');
tableToggleLinks.forEach(link => {
    link.addEventListener('click', function() {
        const dataclassId = this.getAttribute('data-dataclass-id');
        const tablesContainer = document.querySelector(`.tables-container[data-parent-dataclass="${dataclassId}"]`);

        if (tablesContainer) {
            // Toggle display of tables container
            const isCurrentlyHidden = tablesContainer.style.display === 'none' || tablesContainer.style.display === '';
            tablesContainer.style.display = isCurrentlyHidden ? 'block' : 'none';

            // Change icon
            const icon = this.querySelector('i');
            if (icon) {
                if (isCurrentlyHidden) {
                    if (icon.classList.contains('bx-list-ul')) {
                        icon.classList.replace('bx-list-ul', 'bx-x');
                        this.setAttribute('title', 'Skrýt tabulky');
                    }
                } else {
                    if (icon.classList.contains('bx-x')) {
                        icon.classList.replace('bx-x', 'bx-list-ul');
                        this.setAttribute('title', 'Zobrazit tabulky');
                    }
                }
            }
        }
    });
});

document.querySelectorAll('.dataset-footer[role="button"]').forEach(button => {
    button.addEventListener('click', function() {
        const toggleType = this.dataset.toggleType;
        const datasetId = this.dataset.datasetId;
        const icon = this.querySelector('i');
        const text = this.querySelector('span');
        this.classList.toggle('expanded');

        if (toggleType === 'tables') {
            // Hledá tabulkový kontejner podle datasetId
            const tablesContainer = document.getElementById(`tables-${datasetId}`);
            if (tablesContainer) {
                const isHidden = tablesContainer.style.display === 'none' || tablesContainer.style.display === '';
                tablesContainer.style.display = isHidden ? 'block' : 'none';
                if (icon && text) {
                    icon.classList.toggle('fa-angles-down', !isHidden);
                    icon.classList.toggle('fa-xmark', isHidden);
                    text.textContent = isHidden ? 'Skrýt tabulky' : 'Zobrazit tabulky';
                }
            } else {
                // Alternativní selektor, pokud tabulky jsou členěny na více prvků (např. podle classIdx)
                const tableContainers = document.querySelectorAll(`[id^="tables-${datasetId}-"]`);
                if (tableContainers.length > 0) {
                    tableContainers.forEach(tc => {
                        const isHidden = tc.style.display === 'none' || tc.style.display === '';
                        tc.style.display = isHidden ? 'block' : 'none';
                    });
                    if (icon && text) {
                        const anyHidden = Array.from(tableContainers).some(tc => tc.style.display === 'none' || tc.style.display === '');
                        icon.classList.toggle('fa-angles-down', anyHidden);
                        icon.classList.toggle('fa-xmark', !anyHidden);
                        text.textContent = anyHidden ? 'Zobrazit tabulky' : 'Skrýt tabulky';
                    }
                }
            }
        }

        if (toggleType === 'classes') {
            const dataclassDiv = document.getElementById(`dataclasses-${datasetId}`);
            if (dataclassDiv) {
                const isHidden = dataclassDiv.style.display === 'none' || dataclassDiv.style.display === '';
                dataclassDiv.style.display = isHidden ? 'block' : 'none';

                // Přidaná funkcionalita pro změnu ikony a textu u datových tříd
                if (icon && text) {
                    icon.classList.toggle('fa-angles-down', !isHidden);
                    icon.classList.toggle('fa-xmark', isHidden);
                    text.textContent = isHidden ? 'Skrýt dostupná data' : 'Zobrazit dostupná data';
                }
            }
        }
    });
});


    // --- Advanced Search and Filtering ---

    // Initialize variables
    const searchInput = document.getElementById('searchInput');
    const dataSetCards = document.querySelectorAll('.data-set-card, .dataset-card'); // Support both selectors
    const filterCheckboxes = document.querySelectorAll('.filter-box input[type="checkbox"]');
    const filterCard = document.getElementById('filterCard');
    const filterToggle = document.getElementById('filterToggle');
    const clearFiltersButton = document.getElementById('clearFiltersButton');
    const scopeRadioButtons = document.querySelectorAll('input[name="scope"]');
    const searchForm = document.querySelector('form');
    const filterSearchInputs = document.querySelectorAll('.filter-search');

    // Function to filter items in a filter list
    function filterItems(input, listId) {
        const filterValue = input.value.toLowerCase();
        const list = document.getElementById(listId);
        if (!list) return;

        const items = list.getElementsByTagName('li');

        for (let i = 0; i < items.length; i++) {
            const label = items[i].getElementsByTagName('label')[0];
            if (label) {
                const txtValue = label.textContent || label.innerText;
                if (txtValue.toLowerCase().indexOf(filterValue) > -1) {
                    items[i].style.display = "";
                } else {
                    items[i].style.display = "none";
                }
            }
        }
    }

    // Add event listeners to filter search fields
    filterSearchInputs.forEach(input => {
        const filterBox = input.closest('.filter-box');
        if (filterBox) {
            const filterList = filterBox.querySelector('.filter-list');
            if (filterList) {
                const listId = filterList.id;
                input.addEventListener('keyup', () => filterItems(input, listId));
            }
        }
    });

    // Helper function to get checked values by checkbox name
    function getCheckedValues(name) {
        const checkboxes = document.querySelectorAll(`input[name="${name}"]:checked`);
        return Array.from(checkboxes).map(cb => cb.getAttribute('data-tag') || cb.getAttribute('data-holder') || cb.getAttribute('data-availability') || cb.value);
    }

    // Function to update filter toggle button text
    function updateFilterToggleText() {
        if (!filterToggle) return;

        const totalSelected = document.querySelectorAll('.filter-box input[type="checkbox"]:checked').length;
        if (totalSelected > 0) {
            filterToggle.innerHTML = `<i class="fa fa-filter filtrovano"></i> Filtry (${totalSelected})`;
            filterToggle.classList.add('filtrovano');
        } else {
            filterToggle.innerHTML = '<i class="fa fa-filter"></i> Filtry';
            filterToggle.classList.remove('filtrovano');
        }
    }

    // Function to apply filters to child elements
function applyFilters() {
    document.querySelectorAll('.data-set-card').forEach(datasetCard => {
        const datasetId = datasetCard.id.replace('dataset-', '');
        const isDatasetVisible = !datasetCard.classList.contains('hidden') && datasetCard.style.display !== 'none';

        // 1. Aktualizace viditelnosti hlavního kontejneru datasetu
        datasetCard.style.display = isDatasetVisible ? '' : 'none';

        // 2. Získání a aktualizace kontejneru tabulek (pokud existuje)
        const tablesContainer = document.getElementById(`tables-${datasetId}`);
        if (tablesContainer) {
            tablesContainer.style.display = 'none'; // Skryjeme tabulky, pokud je skrytý dataset
            const tablesToggle = datasetCard.querySelector('.dataset-footer[data-toggle-type="tables"]');
            if (tablesToggle) {
                const icon = tablesToggle.querySelector('i');
                const text = tablesToggle.querySelector('span');
                if (icon && text) {
                    icon.classList.remove('fa-xmark');
                    icon.classList.add('fa-angles-down');
                    text.textContent = 'Zobrazit tabulky';
                    tablesToggle.classList.remove('expanded');
                }
            }
        }

        // 3. Získání a aktualizace kontejneru datových tříd (pokud existuje)
        const dataclassesContainer = document.getElementById(`dataclasses-${datasetId}`);
        if (dataclassesContainer) {
            dataclassesContainer.style.display = 'none'; // Skryjeme datové třídy, pokud je skrytý dataset
            const dataclassToggle = datasetCard.querySelector('.dataset-footer[data-toggle-type="classes"]');
            if (dataclassToggle) {
                const icon = dataclassToggle.querySelector('i');
                const text = dataclassToggle.querySelector('span');
                if (icon && text) {
                    icon.classList.remove('fa-xmark');
                    icon.classList.add('fa-angles-down');
                    text.textContent = 'Zobrazit dostupná data';
                    dataclassToggle.classList.remove('expanded');
                }
            }
        }
    });
}


    // Function to filter datasets by search term
    function filterDatasetsBySearch() {
        if (!searchInput) return;

        const query = searchInput.value.toLowerCase();
        const selectedScope = document.querySelector('input[name="scope"]:checked')?.value || 'first';

        console.log("Search query:", query, "Scope:", selectedScope);

        dataSetCards.forEach(card => {
            const title = card.querySelector('.dataset-title, .dataset-name')?.textContent.toLowerCase() || '';
            const description = card.querySelector('.dataset-description')?.textContent.toLowerCase() || '';
            const subjectTags = card.querySelector('.keywords')?.textContent.toLowerCase() || '';
            const dataSource = card.querySelector('.source')?.textContent.toLowerCase() || '';
            const rightsHolder = card.querySelector('.rights-holder')?.textContent.toLowerCase() || '';

            const dataClassNames = card.querySelector('.data-class-names')?.textContent.toLowerCase() || '';
            const dataclassSubjects = card.querySelector('.dataclass-subjects')?.textContent.toLowerCase() || '';
            const dataclassDescriptions = card.querySelector('.dataclass-descriptions')?.textContent.toLowerCase() || '';
            const dbTableNames = card.querySelector('.db-table-names')?.textContent.toLowerCase() || '';
            const dbTableDescriptions = card.querySelector('.db-table-descriptions')?.textContent.toLowerCase() || '';

            let matchesSearch = true;

            if (query) {
                if (selectedScope === 'first') {
                    matchesSearch = title.includes(query) || description.includes(query) || subjectTags.includes(query);
                } else if (selectedScope === 'second') {
                    matchesSearch = title.includes(query) || description.includes(query) || subjectTags.includes(query) ||
                                    dataSource.includes(query) || rightsHolder.includes(query) ||
                                    dataClassNames.includes(query) || dataclassSubjects.includes(query) || dataclassDescriptions.includes(query);
                } else {
                    matchesSearch = title.includes(query) || description.includes(query) || subjectTags.includes(query) ||
                                    dataSource.includes(query) || rightsHolder.includes(query) ||
                                    dataClassNames.includes(query) || dataclassSubjects.includes(query) || dataclassDescriptions.includes(query) ||
                                    dbTableNames.includes(query) || dbTableDescriptions.includes(query);
                }
            }

            card.dataset.matchesSearch = matchesSearch ? 'true' : 'false';
            card.style.display = matchesSearch ? '' : 'none';
            card.classList.toggle('hidden', !matchesSearch);
        });

        // Update available filters after filtering by search
        updateAvailableFilters();
        applyFilters();
    }

    // Function to filter datasets by checkboxes
    function filterDatasetsByCheckboxes() {
        const selectedSubjects = getCheckedValues('subject_tags');
        const selectedSources = getCheckedValues('data_source');
        const selectedHolders = getCheckedValues('rights_holders');
        const selectedAvailability = getCheckedValues('data_availability');

        updateFilterToggleText();

        dataSetCards.forEach(card => {
            const cardSubjects = (card.getAttribute('data-subject') || '').split(', ').filter(s => s.trim() !== '');
            const cardSource = card.getAttribute('data-data-source') || '';
            const cardHolder = card.getAttribute('data-rights-holder') || '';

            // Determine data availability from icon in card
            let cardAvailability = 'none'; // default value
            const availabilityIcon = card.querySelector('.card-header .fa-circle-check, .card-header .fa-circle-question, .card-header .fa-circle-xmark');

            if (availabilityIcon) {
                if (availabilityIcon.classList.contains('fa-circle-check')) {
                    cardAvailability = 'tables';
                } else if (availabilityIcon.classList.contains('fa-circle-question')) {
                    cardAvailability = 'classes';
                }
            }

            // Add data-attribute for availability
            card.setAttribute('data-availability', cardAvailability);

            let matchesSubjects = selectedSubjects.length === 0 ||
                                 selectedSubjects.some(subject => cardSubjects.includes(subject));
            let matchesSource = selectedSources.length === 0 ||
                               selectedSources.includes(cardSource);
            let matchesHolder = selectedHolders.length === 0 ||
                               selectedHolders.includes(cardHolder);
            let matchesAvailability = selectedAvailability.length === 0 ||
                                     selectedAvailability.includes(cardAvailability);

            const matchesFilters = matchesSubjects && matchesSource && matchesHolder && matchesAvailability;
            card.dataset.matchesFilters = matchesFilters ? 'true' : 'false';

            // Show card only when it matches both filters and search
            const matchesSearch = card.dataset.matchesSearch === 'true' || card.dataset.matchesSearch === undefined;
            const visible = matchesFilters && matchesSearch;

            card.style.display = visible ? '' : 'none';
            card.classList.toggle('hidden', !visible);
        });

        // Apply display to child elements
        applyFilters();

        // Update available filters
        updateAvailableFilters();
    }

    // Function to update available filters based on visible cards
    function updateAvailableFilters() {
        // Get all visible cards (matching search)
        const visibleCards = Array.from(document.querySelectorAll('.data-set-card')).filter(card =>
            card.style.display !== 'none' && !card.classList.contains('hidden')
        );

        // Collect unique values from visible cards
        const availableSubjects = new Set();
        const availableSources = new Set();
        const availableHolders = new Set();
        const availableAvailability = new Set();

        visibleCards.forEach(card => {
            // Get data from card attributes
            const subjects = (card.getAttribute('data-subject') || '').split(', ').filter(s => s.trim() !== '');
            const source = card.getAttribute('data-data-source') || '';
            const holder = card.getAttribute('data-rights-holder') || '';
            const availability = card.getAttribute('data-availability') || '';

            // Add to respective sets
            subjects.forEach(subject => availableSubjects.add(subject));
            if (source) availableSources.add(source);
            if (holder) availableHolders.add(holder);
            if (availability) availableAvailability.add(availability);
        });

        // Update checkboxes for keywords
        document.querySelectorAll('#subject-tags-list input[type="checkbox"]').forEach(checkbox => {
            const subject = checkbox.getAttribute('data-tag');
            const listItem = checkbox.closest('li');

            if (availableSubjects.size === 0 || availableSubjects.has(subject)) {
                listItem.style.display = '';
                listItem.classList.remove('disabled');
                checkbox.disabled = false;
            } else {
                if (checkbox.checked) {
                    listItem.style.display = '';
                    listItem.classList.add('disabled');
                    checkbox.disabled = false;
                } else {
                    listItem.style.display = 'none';
                    checkbox.disabled = true;
                }
            }
        });

        // Update checkboxes for data sources
        document.querySelectorAll('#data-source-list input[type="checkbox"]').forEach(checkbox => {
            const source = checkbox.getAttribute('data-holder');
            const listItem = checkbox.closest('li');

            if (availableSources.size === 0 || availableSources.has(source)) {
                listItem.style.display = '';
                listItem.classList.remove('disabled');
                checkbox.disabled = false;
            } else {
                if (checkbox.checked) {
                    listItem.style.display = '';
                    listItem.classList.add('disabled');
                    checkbox.disabled = false;
                } else {
                    listItem.style.display = 'none';
                    checkbox.disabled = true;
                }
            }
        });

        // Update checkboxes for rights holders
        document.querySelectorAll('#rights-holders-list input[type="checkbox"]').forEach(checkbox => {
            const holder = checkbox.getAttribute('data-holder');
            const listItem = checkbox.closest('li');

            if (availableHolders.size === 0 || availableHolders.has(holder)) {
                listItem.style.display = '';
                listItem.classList.remove('disabled');
                checkbox.disabled = false;
            } else {
                if (checkbox.checked) {
                    listItem.style.display = '';
                    listItem.classList.add('disabled');
                    checkbox.disabled = false;
                } else {
                    listItem.style.display = 'none';
                    checkbox.disabled = true;
                }
            }
        });

        // Update filter counters
        updateFilterCounters();
    }

    // Function to update filter counters
    function updateFilterCounters() {
        //const availabilityVisible = document.querySelectorAll('#data-availability-list li:not([style*="display: none"])').length;
        const subjectVisible = document.querySelectorAll('#subject-tags-list li:not([style*="display: none"])').length;
        const sourceVisible = document.querySelectorAll('#data-source-list li:not([style*="display: none"])').length;
        const holderVisible = document.querySelectorAll('#rights-holders-list li:not([style*="display: none"])').length;

        // Update filter headings with item counts
        const availabilityHeading = document.querySelector('.filter-box:nth-child(1) h5');
        const subjectHeading = document.querySelector('.filter-box:nth-child(2) h5');
        const sourceHeading = document.querySelector('.filter-box:nth-child(3) h5');
        const holderHeading = document.querySelector('.filter-box:nth-child(4) h5');

        // Conditionally update headings if they exist
        if (availabilityHeading) availabilityHeading.textContent = `Dostupnost dat (${availabilityVisible})`;
        if (subjectHeading) subjectHeading.textContent = `Klíčová slova (${subjectVisible})`;
        if (sourceHeading) sourceHeading.textContent = `Zdroj dat (${sourceVisible})`;
        if (holderHeading) holderHeading.textContent = `Držitel práv (${holderVisible})`;
    }

    // Function to clear all filters
    function clearAllFilters() {
        filterCheckboxes.forEach(checkbox => checkbox.checked = false);
        if (searchInput) searchInput.value = '';

        filterSearchInputs.forEach(input => {
            input.value = '';
            const filterBox = input.closest('.filter-box');
            const filterList = filterBox?.querySelector('.filter-list');
            if (filterList) filterItems(input, filterList.id);
        });

        dataSetCards.forEach(card => {
            card.dataset.matchesSearch = 'true';
            card.dataset.matchesFilters = 'true';
            card.classList.remove('hidden');
            card.style.display = '';
        });

        // Restore display of all filter options
        document.querySelectorAll('.filter-box li').forEach(item => {
            item.style.display = '';
            item.classList.remove('disabled');
            const checkbox = item.querySelector('input[type="checkbox"]');
            if (checkbox) checkbox.disabled = false;
        });

        // Reset filter headings to original values
        const availabilityHeading = document.querySelector('.filter-box:nth-child(1) h5');
        const subjectHeading = document.querySelector('.filter-box:nth-child(2) h5');
        const sourceHeading = document.querySelector('.filter-box:nth-child(3) h5');
        const holderHeading = document.querySelector('.filter-box:nth-child(4) h5');

        // Conditionally update headings if they exist
        if (availabilityHeading) availabilityHeading.textContent = 'Dostupnost dat';
        if (subjectHeading) subjectHeading.textContent = 'Klíčová slova';
        if (sourceHeading) sourceHeading.textContent = 'Zdroj dat';
        if (holderHeading) holderHeading.textContent = 'Držitel práv';

        updateFilterToggleText();
        applyFilters();
    }

// Improved function to hide all child elements of a dataset
function hideAllChildren(datasetId) {
    // Skryj kontejner datových tříd
    const dataclassesContainer = document.getElementById(`dataclasses-${datasetId}`);
    if (dataclassesContainer) {
        dataclassesContainer.style.display = 'none';
    }

    // Skryj kontejner tabulek
    const tablesContainer = document.getElementById(`tables-${datasetId}`);
    if (tablesContainer) {
        tablesContainer.style.display = 'none';
    }

    // Alternativní způsob nalezení kontejnerů tabulek (pro více kontejnerů)
    const tableContainers = document.querySelectorAll(`[id^="tables-${datasetId}-"]`);
    tableContainers.forEach(tc => {
        tc.style.display = 'none';
    });

    // Reset ikon v patičce, pokud existují
    const datasetFooter = document.querySelector(`.dataset-footer[data-dataset-id="${datasetId}"]`);
    if (datasetFooter) {
        const footerIcon = datasetFooter.querySelector('i');
        const footerText = datasetFooter.querySelector('span');

        if (footerIcon) {
            if (footerIcon.classList.contains('fa-xmark')) {
                footerIcon.classList.replace('fa-xmark', 'fa-angles-down');
            }
        }

        if (footerText) {
            if (datasetFooter.dataset.toggleType === 'tables') {
                footerText.textContent = 'Zobrazit tabulky';
            } else if (datasetFooter.dataset.toggleType === 'classes') {
                footerText.textContent = 'Zobrazit dostupná data';
            }
        }

        datasetFooter.classList.remove('expanded');
    }
}

    // Clear filters button
    if (clearFiltersButton) {
        clearFiltersButton.addEventListener('click', clearAllFilters);
    }

    // Search input handler
    if (searchInput) {
        searchInput.addEventListener('input', filterDatasetsBySearch);
    }

    // Search form submit handler
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            e.preventDefault();
            filterDatasetsBySearch();
        });
    }

    // Filter checkbox handlers
    filterCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', filterDatasetsByCheckboxes);
    });

    // Scope radio button handlers
    scopeRadioButtons.forEach(radio => {
        radio.addEventListener('change', filterDatasetsBySearch);
    });

    // Initialize dataset cards
    dataSetCards.forEach(card => {
        card.dataset.matchesSearch = 'true';
        card.dataset.matchesFilters = 'true';
    });

    // Initialize filters
    filterDatasetsBySearch();
    filterDatasetsByCheckboxes();

    // Ensure all Bootstrap components are properly initialized
    try {
        document.querySelectorAll('.collapse').forEach(function(el) {
            if (typeof bootstrap !== 'undefined' && !bootstrap.Collapse.getInstance(el)) {
                new bootstrap.Collapse(el, {
                    toggle: false
                });
            }
        });
    } catch (e) {
        console.error('Error initializing Bootstrap components:', e);
    }
});