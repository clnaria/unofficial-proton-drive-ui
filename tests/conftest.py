"""Shared test setup: offscreen Qt, English texts, isolated settings and a fake CLI.

The environment is prepared before the app module is imported, because the
app picks its language and settings location at import time.
"""

import json
import os
import stat
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="proton-drive-ui-tests-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PROTON_DRIVE_UI_LANG"] = "en"
os.environ["XDG_CONFIG_HOME"] = str(_TMP / "config")
os.environ["XDG_CACHE_HOME"] = str(_TMP / "cache")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from helpers import wait_until  # noqa: E402
from proton_drive_ui import app as ui  # noqa: E402

FAKE_CLI = r"""#!/usr/bin/env bash
# Fake proton-drive CLI for the tests. Its state lives in $FAKE_CLI_DIR:
#   session              exists while "signed in"
#   listing<path>.json   answer for `filesystem list` ("/" replaced by "_")
#   calls.log            one line per call
state="$FAKE_CLI_DIR"
echo "$*" >> "$state/calls.log"
case "$1 $2" in
  "auth logout") rm -f "$state/session"; exit 0 ;;
  "auth login") touch "$state/session"; echo "Authentication successful"; exit 0 ;;
esac
if [ ! -f "$state/session" ]; then echo "You need to login first" >&2; exit 1; fi
case "$1 $2" in
  "filesystem list")
    path="${@: -1}"
    file="$state/listing$(printf '%s' "$path" | tr '/' '_').json"
    if [ -f "$file" ]; then cat "$file"; exit 0; fi
    echo "Node not found: $path" >&2; exit 1 ;;
  "filesystem upload") exec sleep 30 ;;
  "filesystem create-folder"|"filesystem rename"|"filesystem trash"|"filesystem restore")
    echo '[{"uid":"vol~x","ok":true}]'; exit 0 ;;
esac
echo "unexpected call: $*" >&2
exit 2
"""


def node(uid, name, kind="file", **extra):
    """Builds one entry the way `proton-drive filesystem list -j` prints it."""
    entry = {"uid": uid, "name": {"ok": True, "value": name}, "type": kind}
    entry.update(extra)
    return entry


class FakeCli:
    def __init__(self, directory: Path):
        self.dir = directory
        self.script = directory / "proton-drive"
        self.script.write_text(FAKE_CLI, encoding="utf-8")
        self.script.chmod(self.script.stat().st_mode | stat.S_IXUSR)
        self.sign_in()

    def sign_in(self):
        (self.dir / "session").touch()

    def sign_out(self):
        (self.dir / "session").unlink(missing_ok=True)

    def set_listing(self, path: str, entries: list):
        (self.dir / f"listing{path.replace('/', '_')}.json").write_text(json.dumps(entries), encoding="utf-8")

    def calls(self) -> list[str]:
        log = self.dir / "calls.log"
        return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def fake_cli(tmp_path, monkeypatch):
    cli = FakeCli(tmp_path)
    cli.set_listing(
        "/my-files",
        [
            node("vol~file", "notes.txt", mediaType="text/plain;charset=utf-8", activeRevision={"claimedSize": 2048}),
            node("vol~folder", "Folder A", kind="folder"),
        ],
    )
    cli.set_listing("/my-files/vol~folder", [node("vol~inner", "inner.txt")])
    cli.set_listing("/trash", [])
    monkeypatch.setenv("FAKE_CLI_DIR", str(tmp_path))
    monkeypatch.setattr(ui, "find_cli", lambda: str(cli.script))
    return cli


@pytest.fixture
def make_window(qapp, fake_cli):
    """Returns a function that opens a main window and waits for its first load."""
    windows = []

    def make():
        window = ui.MainWindow()
        window.show()
        wait_until(lambda: window._busy == 0)
        windows.append(window)
        return window

    yield make
    for window in windows:
        window.cli.shutdown()
        window.deleteLater()


@pytest.fixture
def window(make_window):
    return make_window()
