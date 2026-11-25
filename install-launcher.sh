#!/usr/bin/env bash
# Legt den Startmenü-Eintrag für die Proton Drive UI an.
# Mit --remove wird er wieder entfernt.
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
    echo "Entfernt: $entry"
    exit 0
fi

# In Exec müssen \ " ` $ innerhalb der Anführungszeichen maskiert und % verdoppelt werden.
exec_path="$dir/run.sh"
exec_path="${exec_path//\\/\\\\}"
exec_path="${exec_path//\"/\\\"}"
exec_path="${exec_path//\`/\\\`}"
exec_path="${exec_path//\$/\\\$}"
# Zweite Ebene: In .desktop-Dateien steht jeder Backslash selbst doppelt.
exec_path="${exec_path//\\/\\\\}"
exec_path="${exec_path//%/%%}"

mkdir -p "$apps"
cat > "$entry" <<EOF
[Desktop Entry]
Type=Application
Name=Proton Drive UI
GenericName=Cloud-Dateimanager
Comment=Grafische Oberfläche für die Proton Drive CLI
Exec="$exec_path"
Icon=$dir/icon.svg
Terminal=false
Categories=Network;FileTransfer;Qt;
Keywords=proton;drive;cloud;dateien;upload;download;
StartupNotify=true
StartupWMClass=proton-drive-ui
EOF
refresh
echo "Angelegt: $entry"
