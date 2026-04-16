#!/bin/sh

[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"
# Translation Completeness Check
# Usage: ./scripts/check-translations.sh

set -e

TRANSLATION_ISSUES=false

translation_file_is_dirty() {
    [ -n "$(git status --porcelain -- "$1" 2>/dev/null)" ]
}

# Check for fuzzy translations
echo "Checking for fuzzy translations..."
for po_file in locale/*/LC_MESSAGES/django.po; do
    if [ -f "$po_file" ]; then
        FUZZY_FOUND=$(grep "^#, fuzzy" "$po_file" 2>/dev/null || true)
        if [ -n "$FUZZY_FOUND" ]; then
            if translation_file_is_dirty "$po_file"; then
                echo "FAILED: Fuzzy translations found in changed file $po_file"
                echo "$FUZZY_FOUND"
                TRANSLATION_ISSUES=true
            else
                echo "WARN: Existing fuzzy translations in clean file $po_file (not failing)"
            fi
        fi
    fi
done

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
        ' "$po_file" 2>&1 || true)
        
        if [ -n "$EMPTY_FOUND" ]; then
            if translation_file_is_dirty "$po_file"; then
                echo "FAILED: Empty translations found in changed file $po_file"
                echo "$EMPTY_FOUND"
                TRANSLATION_ISSUES=true
            else
                echo "WARN: Existing empty translations in clean file $po_file (not failing)"
            fi
        fi
    fi
done

# Check that .mo files exist and are not older than their .po files.
# Strategy:
#   - If the .po file has uncommitted local changes (or is untracked), use
#     filesystem mtime — the developer may have just edited it without committing.
#   - Otherwise compare the last git commit timestamps, which is reliable after
#     a fresh git checkout where all file mtimes are reset to the current time.
echo "Checking that .mo files are compiled and up to date..."
for po_file in locale/*/LC_MESSAGES/django.po; do
    if [ -f "$po_file" ]; then
        mo_file="${po_file%.po}.mo"
        if [ ! -f "$mo_file" ]; then
            if translation_file_is_dirty "$po_file"; then
                echo "FAILED: Missing compiled translation for changed file: $mo_file"
                echo "  Run: python manage.py compilemessages"
                TRANSLATION_ISSUES=true
            else
                echo "WARN: Missing compiled translation for clean file $po_file (not failing)"
            fi
        else
            stale=false
            # Check whether the .po has uncommitted or untracked changes in git.
            po_dirty=$(git status --porcelain "$po_file" 2>/dev/null)
            po_commit=$(git log -1 --format="%ct" -- "$po_file" 2>/dev/null)
            mo_commit=$(git log -1 --format="%ct" -- "$mo_file" 2>/dev/null)

            if [ -n "$po_dirty" ] || [ -z "$po_commit" ] || [ -z "$mo_commit" ]; then
                # .po is dirty / untracked, or we're outside a git repo — use filesystem mtime.
                if [ "$po_file" -nt "$mo_file" ]; then
                    stale=true
                fi
            else
                # Both files are clean in git — compare commit timestamps.
                if [ "$po_commit" -gt "$mo_commit" ]; then
                    stale=true
                fi
            fi

            if [ "$stale" = true ]; then
                if translation_file_is_dirty "$po_file"; then
                    echo "FAILED: Stale compiled translation: $mo_file is older than changed file $po_file"
                    echo "  Run: python manage.py compilemessages"
                    TRANSLATION_ISSUES=true
                else
                    echo "WARN: Existing stale compiled translation for clean file $po_file (not failing)"
                fi
            fi
        fi
    fi
done

if [ "$TRANSLATION_ISSUES" = false ]; then
    echo "PASSED: All translations complete and compiled"
else
    exit 1
fi
