#!/usr/bin/env bash
# Creates the application launcher entry for Proton Drive UI (unofficial).
# Pass --remove to delete it again.
set -euo pipefail

dir="$(dirname "$(readlink -f "$0")")"
apps="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
entry="$apps/proton-drive-ui.desktop"

refresh() {
    if command -v update-desktop-database >/dev/null; then
        update-desktop-database "$apps" >/dev/null 2>&1 || true
    fi
    if command -v kbuildsycoca6 >/dev/null; then
        kbuildsycoca6 >/dev/null 2>&1 || true
    fi
}

if [[ "${1:-}" == "--remove" ]]; then
    rm -f "$entry"
    refresh
    echo "Removed: $entry"
    exit 0
fi

# Inside the quoted Exec value, \ " ` $ must be escaped and % doubled.
exec_path="$dir/run.sh"
exec_path="${exec_path//\\/\\\\}"
exec_path="${exec_path//\"/\\\"}"
exec_path="${exec_path//\`/\\\`}"
exec_path="${exec_path//\$/\\\$}"
# Second level: in .desktop files every backslash is itself doubled.
exec_path="${exec_path//\\/\\\\}"
exec_path="${exec_path//%/%%}"

# The packaged entry in data/ is the template; only Exec and Icon point into this checkout.
template="$dir/data/proton-drive-ui.desktop"
mkdir -p "$apps"
while IFS= read -r line; do
    case "$line" in
        Exec=*) printf 'Exec="%s"\n' "$exec_path" ;;
        Icon=*) printf 'Icon=%s\n' "$dir/proton_drive_ui/icon.svg" ;;
        *) printf '%s\n' "$line" ;;
    esac
done < "$template" > "$entry"
refresh
echo "Created: $entry"
