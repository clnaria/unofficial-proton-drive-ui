#!/usr/bin/env bash
# Starts Proton Drive UI from the project-local environment.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
exec .venv/bin/python -m proton_drive_ui "$@"
