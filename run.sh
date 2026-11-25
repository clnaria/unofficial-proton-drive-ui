#!/usr/bin/env bash
# Startet die Proton Drive UI aus der projektlokalen Umgebung.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
exec .venv/bin/python proton_drive_ui.py "$@"
