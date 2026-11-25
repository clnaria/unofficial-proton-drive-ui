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

mkdir -p "$apps"
cat > "$entry" <<EOF
[Desktop Entry]
Type=Application
Name=Proton Drive UI (unofficial)
Name[de]=Proton Drive UI (inoffiziell)
GenericName=Cloud File Manager
GenericName[de]=Cloud-Dateimanager
Comment=Unofficial graphical front end for the Proton Drive CLI
Comment[de]=Inoffizielle grafische Oberfläche für die Proton Drive CLI
Exec="$exec_path"
Icon=$dir/icon.svg
Terminal=false
Categories=Network;FileTransfer;Qt;
Keywords=proton;drive;cloud;files;upload;download;unofficial;
Keywords[de]=proton;drive;cloud;dateien;upload;download;unofficial;inoffiziell;
StartupNotify=true
StartupWMClass=proton-drive-ui
EOF
refresh
echo "Created: $entry"
