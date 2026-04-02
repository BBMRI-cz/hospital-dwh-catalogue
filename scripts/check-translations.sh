#!/bin/bash
# Translation Completeness Check
# Usage: ./scripts/check-translations.sh

set -e

TRANSLATION_ISSUES=false

# Check for fuzzy translations
echo "Checking for fuzzy translations..."
if grep -r "^#, fuzzy" locale/*/LC_MESSAGES/django.po 2>/dev/null; then
    echo "FAILED: Fuzzy translations found - please review and update translations"
    TRANSLATION_ISSUES=true
fi

# Check for empty translations
echo "Checking for empty translations..."
for po_file in locale/*/LC_MESSAGES/django.po; do
    if [ -f "$po_file" ]; then
        # Find msgid followed by msgstr "" with no continuation (truly empty)
        EMPTY_FOUND=$(awk '
            /^msgid "[^"]/ {
                msgid=$0
                line=NR
                getline
                if (/^msgstr ""$/) {
                    getline
                    # Empty if next line is blank, a comment, or another msgid
                    if ($0 ~ /^$/ || $0 ~ /^#/ || $0 ~ /^msgid/) {
                        print FILENAME ":" line ":" msgid
                        found++
                    }
                }
            }
            END { exit (found > 0) }
        ' "$po_file" 2>&1)
        
        if [ $? -ne 0 ]; then
            echo "FAILED: Empty translations found in $po_file"
            echo "$EMPTY_FOUND"
            TRANSLATION_ISSUES=true
        fi
    fi
done

# Check that .mo files exist and are not older than their .po files
echo "Checking that .mo files are compiled and up to date..."
for po_file in locale/*/LC_MESSAGES/django.po; do
    if [ -f "$po_file" ]; then
        mo_file="${po_file%.po}.mo"
        if [ ! -f "$mo_file" ]; then
            echo "FAILED: Missing compiled translation: $mo_file"
            echo "  Run: python manage.py compilemessages"
            TRANSLATION_ISSUES=true
        elif [ "$po_file" -nt "$mo_file" ]; then
            echo "FAILED: Stale compiled translation: $mo_file is older than $po_file"
            echo "  Run: python manage.py compilemessages"
            TRANSLATION_ISSUES=true
        fi
    fi
done

if [ "$TRANSLATION_ISSUES" = false ]; then
    echo "PASSED: All translations complete and compiled"
else
    exit 1
fi
