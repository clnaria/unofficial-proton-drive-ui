#!/usr/bin/env python3
"""Proton Drive UI (unofficial) – a graphical front end for the proton-drive CLI.

This project is not affiliated with Proton AG.

The app runs the CLI for every action (`proton-drive … -j`) and reads its JSON
output. Signing in and encryption stay entirely with the CLI.

Source texts are English; German translations live in translations.py.
"""

from __future__ import annotations

import configparser
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QCollator,
    QDate,
    QDateTime,
    QElapsedTimer,
    QLibraryInfo,
    QLocale,
    QMimeDatabase,
    QObject,
    QProcess,
    QSettings,
    QSortFilterProxyModel,
    QStandardPaths,
    Qt,
    QTimer,
    QTranslator,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QDesktopServices,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStyle,
    QToolBar,
    QToolButton,
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

APP_NAME = "proton-drive-ui"

# --------------------------------------------------------------------------
# Language
# --------------------------------------------------------------------------

try:
    from translations import GERMAN
except ImportError:  # without the file the app still works, in English
    GERMAN = {}


def system_language() -> str:
    return "de" if QLocale.system().language() == QLocale.German else "en"


def detect_language() -> str:
    """Returns "de" or "en": environment variable first, then the saved setting, then the system."""
    forced = os.environ.get("PROTON_DRIVE_UI_LANG", "")
    if forced not in ("de", "en"):
        forced = str(QSettings(APP_NAME, APP_NAME).value("language", "") or "")
    return forced if forced in ("de", "en") else system_language()


LANGUAGE = detect_language()


def T(text: str) -> str:
    """Translates an English source text into the active language."""
    if LANGUAGE == "de":
        return GERMAN.get(text, text)
    return text


APP_TITLE = T("Proton Drive UI (unofficial)")
NODE_ROLE = Qt.UserRole + 1
SORT_ROLE = Qt.UserRole + 2
PATH_ROLE = Qt.UserRole + 3
LOADED_ROLE = Qt.UserRole + 4

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
URL_RE = re.compile(r"https?://[^\s\"'<>\\]+")
# Messages the CLI prints when there is no session.
AUTH_RE = re.compile(r"need to login|login first|no session loaded|not logged in", re.IGNORECASE)

# (CLI path, display name, icon name)
SECTIONS = [
    ("/my-files", T("My files"), "folder-cloud"),
    ("/devices", "Computer", "computer"),
    ("/shared-by-me", T("Shared by me"), "folder-publicshare"),
    ("/shared-with-me", T("Shared with me"), "folder-remote"),
    ("/trash", T("Trash"), "user-trash"),
]

# Conflict strategies of the CLI: (value, label)
UPLOAD_FILE_STRATEGIES = [
    ("create-new-revision", T("Create new revision")),
    ("rename", T("Rename")),
    ("skip", T("Skip")),
    ("replace", T("Replace (old file goes to trash)")),
]
UPLOAD_FOLDER_STRATEGIES = [
    ("merge", T("Merge")),
    ("rename", T("Rename")),
    ("skip", T("Skip")),
    ("replace", T("Replace (old folder goes to trash)")),
]
DOWNLOAD_FILE_STRATEGIES = [
    ("rename", T("Rename")),
    ("skip", T("Skip")),
    ("remove", T("Replace local file")),
]
DOWNLOAD_FOLDER_STRATEGIES = [
    ("merge", T("Merge")),
    ("rename", T("Rename")),
    ("skip", T("Skip")),
    ("remove", T("Replace local folder")),
]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def find_cli() -> str:
    return shutil.which("proton-drive") or str(Path.home() / ".local/bin/proton-drive")


def clean_text(raw: bytes | bytearray) -> str:
    return ANSI_RE.sub("", bytes(raw).decode("utf-8", errors="replace")).replace("\r", "")


def human_size(size: int | None) -> str:
    if size is None:
        return ""
    return QLocale().formattedDataSize(int(size))


def parse_time(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def format_time(value: datetime | None) -> str:
    if value is None:
        return ""
    qdt = QDateTime.fromSecsSinceEpoch(int(value.timestamp()))
    return QLocale().toString(qdt, QLocale.ShortFormat)


def escape_name(name: str) -> str:
    """Slashes in names must be escaped for CLI paths."""
    return name.replace("/", "\\/")


def themed_icon(name: str, fallback: QStyle.StandardPixmap | None = None) -> QIcon:
    icon = QIcon.fromTheme(name)
    if icon.isNull() and fallback is not None:
        icon = QApplication.style().standardIcon(fallback)
    return icon


def app_icon() -> QIcon:
    icon = QIcon(str(Path(__file__).resolve().parent / "icon.svg"))
    if icon.isNull() or not icon.availableSizes() and icon.pixmap(32).isNull():
        icon = themed_icon("folder-cloud", QStyle.SP_DriveNetIcon)
    return icon


def setup_icon_theme() -> None:
    """The bundled Qt does not always pick up the KDE icon theme by itself."""
    paths = QIcon.themeSearchPaths()
    missing = [p for p in (str(Path.home() / ".local/share/icons"), "/usr/share/icons") if p not in paths]
    if missing:
        QIcon.setThemeSearchPaths(missing + paths)
    if QIcon.themeName() not in ("", "hicolor"):
        return
    candidates = []
    try:
        cfg = configparser.ConfigParser(strict=False, interpolation=None)
        cfg.read(Path.home() / ".config/kdeglobals", encoding="utf-8")
        candidates.append(cfg.get("Icons", "Theme", fallback=""))
    except (configparser.Error, OSError, UnicodeError):
        pass
    dark = QGuiApplication.palette().window().color().lightness() < 128
    candidates += ["breeze-dark", "breeze"] if dark else ["breeze", "breeze-dark"]
    candidates += ["Adwaita"]
    for theme in candidates:
        if theme and any(
            (Path(base) / theme / "index.theme").exists()
            for base in ("/usr/share/icons", str(Path.home() / ".local/share/icons"))
        ):
            QIcon.setThemeName(theme)
            return


# --------------------------------------------------------------------------
# CLI access
# --------------------------------------------------------------------------


@dataclass
class Result:
    ok: bool
    data: object = None
    out: str = ""
    err: str = ""
    auth_error: bool = False  # the CLI reports: not signed in

    @property
    def message(self) -> str:
        return self.err.strip() or self.out.strip() or T("Unknown error")


class Cli(QObject):
    """Runs proton-drive asynchronously and delivers the result through a callback."""

    # True: a call succeeded (signed in); False: the CLI asks for a sign-in.
    authChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.program = find_cli()
        self._procs: set[QProcess] = set()
        self.closing = False
        self.epoch = 0  # raised on sign-out; calls started earlier no longer count

    def invalidate_session(self):
        self.epoch += 1

    def run(self, args, callback, parse_json=True, on_output=None, keep_stdin=False) -> QProcess:
        proc = QProcess(self)
        proc.setProgram(self.program)
        proc.setArguments(list(args))
        out, err = bytearray(), bytearray()
        state = {"done": False}
        epoch = self.epoch
        is_logout = list(args[:2]) == ["auth", "logout"]

        def read_out():
            chunk = proc.readAllStandardOutput().data()
            out.extend(chunk)
            if on_output:
                on_output(clean_text(chunk))

        def read_err():
            chunk = proc.readAllStandardError().data()
            err.extend(chunk)
            if on_output:
                on_output(clean_text(chunk))

        def finish(ok: bool, start_failed=False):
            if state["done"]:
                return
            state["done"] = True
            self._procs.discard(proc)
            proc.deleteLater()
            if self.closing:
                return
            text, errtext = clean_text(out), clean_text(err)
            if start_failed:
                errtext = T("“{program}” could not be started. Is the Proton Drive CLI installed?").format(program=self.program)
            data = None
            if ok and parse_json:
                stripped = text.strip()
                if stripped and stripped != "undefined":
                    try:
                        data = json.loads(stripped)
                    except ValueError:
                        data = None
            auth_error = not ok and not start_failed and bool(AUTH_RE.search(errtext or text))
            if epoch == self.epoch and not is_logout:
                if ok:
                    self.authChanged.emit(True)
                elif auth_error:
                    self.authChanged.emit(False)
            callback(Result(ok, data, text, errtext, auth_error))

        def on_finished(code, status):
            read_out()
            read_err()
            finish(status == QProcess.NormalExit and code == 0)

        def on_error(error):
            if error == QProcess.FailedToStart:
                finish(False, start_failed=True)

        proc.readyReadStandardOutput.connect(read_out)
        proc.readyReadStandardError.connect(read_err)
        proc.finished.connect(on_finished)
        proc.errorOccurred.connect(on_error)
        self._procs.add(proc)
        proc.start()
        if not keep_stdin:
            # No terminal: prompts from the CLI get EOF right away.
            proc.closeWriteChannel()
        return proc

    def shutdown(self):
        self.closing = True
        for proc in list(self._procs):
            proc.kill()
            proc.waitForFinished(1500)


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------


@dataclass
class Crumb:
    name: str
    path: str


@dataclass
class Node:
    name: str
    kind: str  # file, folder, album, photo, device
    path: str  # path for the CLI
    uid: str = ""
    size: int | None = None
    mtime: datetime | None = None
    ctime: datetime | None = None
    media_type: str = ""
    shared: bool = False
    shared_url: bool = False
    owner: str = ""
    role: str = ""
    ambiguous: bool = False  # same name more than once in the trash
    raw: dict = field(default_factory=dict)

    @property
    def is_container(self) -> bool:
        return self.kind in ("folder", "device", "album")


def _entry_name(entry: dict):
    raw_name = entry.get("name")
    if isinstance(raw_name, dict):
        return raw_name.get("value") if raw_name.get("ok") else None
    return raw_name


def parse_entries(parent_path: str, entries) -> list[Node]:
    nodes: list[Node] = []
    if not isinstance(entries, list):
        return nodes
    # In the trash the CLI (as of 0.9.0) only understands names, not UIDs.
    by_name = parent_path == "/trash"
    name_counts: dict[str, int] = {}
    if by_name:
        for entry in entries:
            if isinstance(entry, dict):
                key = _entry_name(entry)
                if key:
                    name_counts[key] = name_counts.get(key, 0) + 1
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = _entry_name(entry)
        uid = entry.get("uid", "") or ""

        if "rootFolderUid" in entry:  # entry below /devices
            if name and "\\" not in name:
                segment = escape_name(name)
            else:
                segment = entry.get("rootFolderUid") or uid
            nodes.append(
                Node(
                    name=name or uid,
                    kind="device",
                    path=f"{parent_path}/{segment}",
                    uid=uid,
                    ctime=parse_time(entry.get("creationTime")),
                    media_type=str(entry.get("type", "")),
                    raw=entry,
                )
            )
            continue

        kind = entry.get("type", "file")
        revision = entry.get("activeRevision") if isinstance(entry.get("activeRevision"), dict) else {}
        size = None
        if kind != "folder":
            for candidate in (revision.get("claimedSize"), revision.get("storageSize"), entry.get("totalStorageSize")):
                if isinstance(candidate, (int, float)):
                    size = int(candidate)
                    break
        owner = entry.get("ownedBy") if isinstance(entry.get("ownedBy"), dict) else {}
        # The UID as a path segment is unique and needs no escaping.
        if by_name and name:
            segment = escape_name(name)
        else:
            segment = uid or escape_name(name or "")
        nodes.append(
            Node(
                name=name or T("(name unreadable) {uid}").format(uid=uid[-8:]),
                kind=kind,
                path=f"{parent_path}/{segment}",
                uid=uid,
                size=size,
                mtime=parse_time(revision.get("claimedModificationTime")) or parse_time(entry.get("modificationTime")),
                ctime=parse_time(entry.get("creationTime")),
                # The MIME database does not know parameters such as ";charset=utf-8".
                media_type=str(entry.get("mediaType", "") or "").split(";")[0].strip(),
                shared=bool(entry.get("isShared")),
                shared_url=bool(entry.get("isSharedByUrl")),
                owner=str(owner.get("email", "") or ""),
                role=str(entry.get("directRole", "") or ""),
                ambiguous=by_name and name_counts.get(name or "", 0) > 1,
                raw=entry,
            )
        )
    return nodes


def failures_text(data) -> str:
    """Extracts failure messages from a JSON response, if there are any."""
    if isinstance(data, list):  # e.g. [{"uid": …, "ok": false, "error": …}]
        failed = [entry for entry in data if isinstance(entry, dict) and entry.get("ok") is False]
        return json.dumps(failed, indent=2, ensure_ascii=False) if failed else ""
    if not isinstance(data, dict):
        return ""
    failures = data.get("failures")
    if failures:
        return json.dumps(failures, indent=2, ensure_ascii=False)
    if data.get("failedItems"):
        return T("{count} item(s) failed.").format(count=data["failedItems"])
    return ""


class NodeProxy(QSortFilterProxyModel):
    """Always sorts folders before files, and names in natural numeric order."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.collator = QCollator()
        self.collator.setNumericMode(True)
        self.collator.setCaseSensitivity(Qt.CaseInsensitive)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setFilterKeyColumn(0)

    def lessThan(self, left, right):
        model = self.sourceModel()
        lnode = model.item(left.row(), 0).data(NODE_ROLE)
        rnode = model.item(right.row(), 0).data(NODE_ROLE)
        if lnode.is_container != rnode.is_container:
            ascending = self.sortOrder() == Qt.AscendingOrder
            return lnode.is_container if ascending else not lnode.is_container
        lkey = model.data(left, SORT_ROLE)
        rkey = model.data(right, SORT_ROLE)
        if isinstance(lkey, str) and isinstance(rkey, str):
            if lkey == rkey:
                return self.collator.compare(lnode.name, rnode.name) < 0
            return self.collator.compare(lkey, rkey) < 0
        lnum = lkey if isinstance(lkey, (int, float)) else -1
        rnum = rkey if isinstance(rkey, (int, float)) else -1
        if lnum == rnum:
            return self.collator.compare(lnode.name, rnode.name) < 0
        return lnum < rnum


# --------------------------------------------------------------------------
# Widgets
# --------------------------------------------------------------------------


class DropTreeView(QTreeView):
    """File list that accepts local files by drag and drop."""

    filesDropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.drop_enabled = True
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)

    @staticmethod
    def _local_paths(event) -> list[str]:
        mime = event.mimeData()
        if not mime.hasUrls():
            return []
        return [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]

    def _handle_drag(self, event):
        if self.drop_enabled and self._local_paths(event):
            # Always copy: the source must not delete anything.
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragEnterEvent(self, event):
        self._handle_drag(event)

    def dragMoveEvent(self, event):
        self._handle_drag(event)

    def dropEvent(self, event):
        paths = self._local_paths(event)
        if self.drop_enabled and paths:
            event.setDropAction(Qt.CopyAction)
            event.accept()
            self.filesDropped.emit(paths)
        else:
            event.ignore()


@dataclass
class Transfer:
    title: str
    detail: str
    args: list
    item: QTreeWidgetItem
    on_done: object = None
    state: str = "queued"
    cancelled: bool = False
    proc: QProcess | None = None
    clock: QElapsedTimer = field(default_factory=QElapsedTimer)


class TransferPanel(QWidget):
    """Queue for uploads and downloads; only one runs at a time."""

    changed = Signal()

    def __init__(self, cli: Cli, parent=None):
        super().__init__(parent)
        self.cli = cli
        self.transfers: list[Transfer] = []
        self.queue: list[Transfer] = []
        self.current: Transfer | None = None

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([T("Task"), "Details", "Status"])
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setColumnWidth(0, 130)
        self.tree.setColumnWidth(1, 380)

        self.cancel_btn = QPushButton(T("Cancel"))
        self.cancel_btn.setToolTip(T("Cancels the selected transfers, or the running one if none is selected."))
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_selected)
        self.changed.connect(lambda: self.cancel_btn.setEnabled(self.busy()))
        clear_btn = QPushButton(T("Clear finished"))
        clear_btn.clicked.connect(self.clear_finished)
        buttons = QVBoxLayout()
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(clear_btn)
        buttons.addStretch(1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.tree, 1)
        layout.addLayout(buttons)

        self.tick = QTimer(self)
        self.tick.setInterval(1000)
        self.tick.timeout.connect(self._update_running)

    def busy(self) -> bool:
        return self.current is not None or bool(self.queue)

    def add(self, title: str, detail: str, args: list, on_done=None):
        item = QTreeWidgetItem([title, detail, T("Waiting")])
        item.setToolTip(1, detail)
        self.tree.addTopLevelItem(item)
        self.tree.scrollToItem(item)
        transfer = Transfer(title, detail, args, item, on_done)
        self.transfers.append(transfer)
        self.queue.append(transfer)
        self._next()
        self.changed.emit()

    def _next(self):
        if self.current is not None or not self.queue:
            return
        transfer = self.queue.pop(0)
        self.current = transfer
        transfer.state = "running"
        transfer.clock.start()
        transfer.item.setText(2, T("Running …"))
        transfer.proc = self.cli.run(transfer.args, lambda res, t=transfer: self._finished(t, res))
        self.tick.start()

    def _update_running(self):
        if self.current is None:
            return
        secs = self.current.clock.elapsed() // 1000
        self.current.item.setText(2, T("Running … {time}").format(time=f"{secs // 60}:{secs % 60:02d}"))

    def _finished(self, transfer: Transfer, res: Result):
        self.current = None
        transfer.proc = None
        item = transfer.item
        if transfer.cancelled:
            transfer.state = "cancelled"
            item.setText(2, T("Cancelled"))
        elif not res.ok:
            transfer.state = "failed"
            item.setText(2, T("Failed: ") + res.message.splitlines()[0])
            item.setToolTip(2, res.message)
        else:
            transfer.state = "done"
            text, tooltip = self._summary(res.data)
            item.setText(2, text)
            item.setToolTip(2, tooltip)
        if not self.queue:
            self.tick.stop()
        if transfer.on_done:
            transfer.on_done(transfer.state == "done", res)
        self._next()
        self.changed.emit()

    @staticmethod
    def _summary(data) -> tuple[str, str]:
        if not isinstance(data, dict):
            return T("Done"), ""
        parts = [T("{count} item(s), {size}").format(count=data.get("transferredItems", 0), size=human_size(data.get("transferredBytes", 0)))]
        if data.get("skippedItems"):
            parts.append(T("{count} skipped").format(count=data["skippedItems"]))
        if data.get("failedItems"):
            parts.append(T("{count} failed").format(count=data["failedItems"]))
        prefix = T("Finished with errors") if data.get("failedItems") else T("Done")
        return f"{prefix} – " + ", ".join(parts), failures_text(data)

    def cancel_selected(self):
        """Cancels the selected queued/running transfers, otherwise the running one."""
        selected = self.tree.selectedItems()
        targets = [
            t for t in self.transfers if t.state in ("queued", "running") and any(t.item is item for item in selected)
        ]
        if not targets and self.current is not None:
            targets = [self.current]
        for transfer in targets:
            if transfer.state == "queued":
                self.queue.remove(transfer)
                transfer.state = "cancelled"
                transfer.item.setText(2, T("Cancelled"))
            elif transfer.state == "running" and transfer.proc is not None:
                transfer.cancelled = True
                transfer.proc.kill()
        self.changed.emit()

    def clear_finished(self):
        keep = []
        for transfer in self.transfers:
            if transfer.state in ("queued", "running"):
                keep.append(transfer)
            else:
                self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(transfer.item))
        self.transfers = keep


class FolderPicker(QDialog):
    """Picks a target folder in "My files" (loads subfolders on demand)."""

    def __init__(self, cli: Cli, title: str, parent=None):
        super().__init__(parent)
        self.cli = cli
        self.setWindowTitle(title)
        self.resize(460, 480)
        self._open = True

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemExpanded.connect(self._load_children)
        self.tree.itemDoubleClicked.connect(lambda *_: None)

        root = QTreeWidgetItem([T("My files")])
        root.setIcon(0, themed_icon("folder-cloud", QStyle.SP_DirIcon))
        root.setData(0, PATH_ROLE, "/my-files")
        root.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
        self.tree.addTopLevelItem(root)
        self.tree.setCurrentItem(root)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(T("Select"))
        buttons.button(QDialogButtonBox.Cancel).setText(T("Cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tree)
        layout.addWidget(buttons)
        root.setExpanded(True)

    def done(self, result):
        self._open = False
        super().done(result)

    def _load_children(self, item: QTreeWidgetItem):
        if item.data(0, LOADED_ROLE):
            return
        item.setData(0, LOADED_ROLE, True)
        path = item.data(0, PATH_ROLE)
        item.setText(0, item.text(0) + T("  (loading …)"))

        def loaded(res: Result):
            if not self._open:
                return
            item.setText(0, item.text(0).replace(T("  (loading …)"), ""))
            if not res.ok:
                error = QTreeWidgetItem([T("Error: {message}").format(message=res.message.splitlines()[0])])
                error.setFlags(Qt.NoItemFlags)
                item.addChild(error)
                return
            folders = [n for n in parse_entries(path, res.data) if n.kind == "folder"]
            folders.sort(key=lambda n: n.name.casefold())
            if not folders:
                item.setChildIndicatorPolicy(QTreeWidgetItem.DontShowIndicator)
            for node in folders:
                child = QTreeWidgetItem([node.name])
                child.setIcon(0, themed_icon("folder", QStyle.SP_DirIcon))
                child.setData(0, PATH_ROLE, node.path)
                child.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
                item.addChild(child)

        self.cli.run(["filesystem", "list", "-j", "-t", "folder", "--", path], loaded)

    def selected_path(self) -> str | None:
        item = self.tree.currentItem()
        return item.data(0, PATH_ROLE) if item else None


class ShareDialog(QDialog):
    """Manages the public link of a file or folder."""

    def __init__(self, cli: Cli, node: Node, parent=None):
        super().__init__(parent)
        self.cli = cli
        self.node = node
        self.changed = False
        self._open = True
        self.setWindowTitle(T("Sharing – {name}").format(name=node.name))
        self.resize(560, 520)

        self.status_label = QLabel(T("Loading sharing status …"))
        self.status_label.setWordWrap(True)
        self.url_edit = QLineEdit()
        self.url_edit.setReadOnly(True)
        self.url_edit.setPlaceholderText(T("No public link"))
        self.copy_btn = QPushButton(T("Copy"))
        self.copy_btn.setIcon(themed_icon("edit-copy"))
        self.copy_btn.clicked.connect(self._copy_url)
        url_row = QHBoxLayout()
        url_row.addWidget(self.url_edit, 1)
        url_row.addWidget(self.copy_btn)

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText(T("Details from the CLI appear here."))

        self.role_combo = QComboBox()
        self.role_combo.addItem(T("Viewer"), "viewer")
        self.role_combo.addItem(T("Editor"), "editor")
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("optional")
        self.expiry_check = QCheckBox(T("Expires on"))
        self.expiry_edit = QDateEdit(QDate.currentDate().addDays(7))
        self.expiry_edit.setCalendarPopup(True)
        self.expiry_edit.setMinimumDate(QDate.currentDate().addDays(1))
        self.expiry_edit.setEnabled(False)
        self.expiry_check.toggled.connect(self.expiry_edit.setEnabled)
        expiry_row = QHBoxLayout()
        expiry_row.addWidget(self.expiry_check)
        expiry_row.addWidget(self.expiry_edit, 1)

        form = QFormLayout()
        form.addRow(T("Role:"), self.role_combo)
        form.addRow(T("Link password:"), self.password_edit)
        form.addRow(expiry_row)

        self.set_btn = QPushButton(T("Create / update link"))
        self.set_btn.clicked.connect(self._set_url)
        self.remove_btn = QPushButton(T("Remove link"))
        self.remove_btn.clicked.connect(self._remove_url)
        close_btn = QPushButton(T("Close"))
        close_btn.clicked.connect(self.accept)
        button_row = QHBoxLayout()
        button_row.addWidget(self.set_btn)
        button_row.addWidget(self.remove_btn)
        button_row.addStretch(1)
        button_row.addWidget(close_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addLayout(url_row)
        layout.addWidget(self.details, 1)
        layout.addLayout(form)
        layout.addLayout(button_row)
        self.refresh()

    def done(self, result):
        self._open = False
        super().done(result)

    def _set_busy(self, busy: bool):
        self.set_btn.setEnabled(not busy)
        self.remove_btn.setEnabled(not busy)

    def refresh(self):
        self._set_busy(True)

        def loaded(res: Result):
            if not self._open:
                return
            self._set_busy(False)
            if not res.ok:
                self.status_label.setText(T("Could not load the status: {message}").format(message=res.message))
                return
            if res.data is None:
                self.remove_btn.setEnabled(False)
                self.status_label.setText(T("This item is not shared."))
                self.details.setPlainText(res.out.strip() if res.out.strip() != "undefined" else "")
                self.url_edit.clear()
                return
            text = json.dumps(res.data, indent=2, ensure_ascii=False)
            self.details.setPlainText(text)
            self._show_url(text)
            self.status_label.setText(
                T("Public link is active.") if self.url_edit.text() else T("Shared (no public link found).")
            )

        self.cli.run(["sharing", "status", "-j", "--", self.node.path], loaded)

    def _show_url(self, text: str):
        match = URL_RE.search(text)
        if match:
            self.url_edit.setText(match.group(0))

    def _copy_url(self):
        if self.url_edit.text():
            QGuiApplication.clipboard().setText(self.url_edit.text())
            self.status_label.setText(T("Link copied to the clipboard."))

    def _set_url(self):
        args = ["sharing", "set-url", "-j", "--role", self.role_combo.currentData()]
        if self.password_edit.text():
            args += ["--password", self.password_edit.text()]
        if self.expiry_check.isChecked():
            args += ["--expiration", self.expiry_edit.date().toString("yyyy-MM-dd")]
        args += ["--", self.node.path]
        self._set_busy(True)
        self.status_label.setText(T("Creating link …"))

        def finished(res: Result):
            if not self._open:
                return
            self.changed = True
            if not res.ok:
                self._set_busy(False)
                self.status_label.setText(T("Could not create the link: {message}").format(message=res.message))
                return
            self._show_url(res.out)
            self.refresh()

        self.cli.run(args, finished)

    def _remove_url(self):
        answer = QMessageBox.question(
            self,
            T("Remove link"),
            T("Remove the public link for “{name}”?\nThe existing link will stop working.").format(name=self.node.name),
        )
        if answer != QMessageBox.Yes:
            return
        self._set_busy(True)
        self.status_label.setText(T("Removing link …"))

        def finished(res: Result):
            if not self._open:
                return
            self.changed = True
            if not res.ok:
                self._set_busy(False)
                self.status_label.setText(T("Could not remove the link: {message}").format(message=res.message))
                return
            self.url_edit.clear()
            self.refresh()

        self.cli.run(["sharing", "remove-url", "-j", "--", self.node.path], finished)


class LoginDialog(QDialog):
    """Runs `proton-drive auth login`; the sign-in itself happens in the browser."""

    def __init__(self, cli: Cli, parent=None):
        super().__init__(parent)
        self.setWindowTitle(T("Sign in to Proton"))
        self.resize(560, 320)
        self._open = True
        self._url = ""

        info = QLabel(
            T("The CLI opens your browser for signing in. This window closes as soon as sign-in is complete.")
        )
        info.setWordWrap(True)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.open_btn = QPushButton(T("Open link in browser"))
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self._url)))
        cancel_btn = QPushButton(T("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addWidget(self.open_btn)
        row.addStretch(1)
        row.addWidget(cancel_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(info)
        layout.addWidget(self.output, 1)
        layout.addLayout(row)

        self.proc = cli.run(["auth", "login"], self._finished, parse_json=False, on_output=self._on_output, keep_stdin=True)

    def _on_output(self, text: str):
        if not self._open:
            return
        self.output.moveCursor(self.output.textCursor().MoveOperation.End)
        self.output.insertPlainText(text)
        match = URL_RE.search(self.output.toPlainText())
        if match:
            self._url = match.group(0)
            self.open_btn.setEnabled(True)

    def _finished(self, res: Result):
        self.proc = None
        if not self._open:
            return
        if res.ok:
            self.accept()
        else:
            self.output.appendPlainText(T("\nSign-in failed: {message}").format(message=res.message))

    def done(self, result):
        self._open = False
        if self.proc is not None:
            self.proc.kill()
        super().done(result)


# --------------------------------------------------------------------------
# Main window
# --------------------------------------------------------------------------


class MainWindow(QMainWindow):
    COLUMNS = ["Name", T("Size"), T("Type"), T("Modified"), T("Sharing")]

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(app_icon())
        self.resize(1100, 700)

        self.cli = Cli(self)
        self.settings = QSettings(APP_NAME, APP_NAME)
        self.mime_db = QMimeDatabase()
        self.icon_cache: dict[str, QIcon] = {}
        self.cache: dict[str, list[Node]] = {}
        self.location: list[Crumb] = []
        self.back_stack: list[list[Crumb]] = []
        self.forward_stack: list[list[Crumb]] = []
        self._load_token = 0
        self._busy = 0
        self.logged_in: bool | None = None  # None: not known yet
        self.cli.authChanged.connect(self._set_logged_in)
        cache_root = QStandardPaths.writableLocation(QStandardPaths.CacheLocation) or str(Path.home() / ".cache" / APP_NAME)
        self.open_cache = Path(cache_root) / "open"
        shutil.rmtree(self.open_cache, ignore_errors=True)

        self._build_actions()
        self._build_ui()
        self._build_menus()
        self._restore_state()
        self.navigate([Crumb(SECTIONS[0][1], SECTIONS[0][0])], push=False)

    # ----- Setup ---------------------------------------------------------

    def _action(self, text, icon_name, slot, shortcut=None, fallback=None) -> QAction:
        action = QAction(themed_icon(icon_name, fallback), text, self)
        action.triggered.connect(lambda _checked=False: slot())
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        self.addAction(action)
        return action

    def _build_actions(self):
        S = QStyle
        self.act_back = self._action(T("Back"), "go-previous", self.go_back, "Alt+Left", S.SP_ArrowBack)
        self.act_forward = self._action(T("Forward"), "go-next", self.go_forward, "Alt+Right", S.SP_ArrowForward)
        self.act_up = self._action(T("Parent folder"), "go-up", self.go_up, "Alt+Up", S.SP_ArrowUp)
        self.act_reload = self._action(T("Refresh"), "view-refresh", self.reload, "F5", S.SP_BrowserReload)
        self.act_upload_files = self._action(T("Upload files …"), "document-send", self.upload_files, "Ctrl+U", S.SP_ArrowUp)
        self.act_upload_folder = self._action(T("Upload folder …"), "folder-upload", self.upload_folder, None, S.SP_DirIcon)
        self.act_new_folder = self._action(T("New folder …"), "folder-new", self.new_folder, "Ctrl+Shift+N", S.SP_FileDialogNewFolder)
        self.act_download = self._action(T("Download …"), "download", self.download_selected, "Ctrl+D", S.SP_ArrowDown)
        self.act_open = self._action(T("Open"), "document-open", self.open_selected, None, S.SP_DialogOpenButton)
        self.act_rename = self._action(T("Rename …"), "edit-rename", self.rename_selected, "F2")
        self.act_move = self._action(T("Move to …"), "edit-move", self.move_selected)
        self.act_copy = self._action(T("Copy to …"), "edit-copy", self.copy_selected)
        self.act_trash = self._action(T("Move to trash"), "user-trash", self.trash_selected, "Delete", S.SP_TrashIcon)
        self.act_share = self._action(T("Share link …"), "document-share", self.share_selected)
        self.act_properties = self._action(T("Properties"), "document-properties", self.show_properties, "Alt+Return")
        self.act_restore = self._action(T("Restore"), "edit-undo", self.restore_selected)
        self.act_delete = self._action(T("Delete permanently …"), "edit-delete", self.delete_selected, None, S.SP_DialogDiscardButton)
        self.act_empty_trash = self._action(T("Empty trash …"), "trash-empty", self.empty_trash, None, S.SP_TrashIcon)
        self.act_login = self._action(T("Sign in …"), "system-users", self.login)
        self.act_logout = self._action(T("Sign out"), "system-log-out", self.logout)
        self.act_login.setVisible(False)
        self.act_logout.setVisible(False)
        self.act_filter = self._action(T("Filter in folder"), "view-filter", lambda: self.filter_edit.setFocus(), "Ctrl+F")
        self.act_quit = self._action(T("Quit"), "application-exit", self.close, "Ctrl+Q")

    def _build_ui(self):
        nav = QToolBar("Navigation")
        nav.setObjectName("nav")
        nav.setMovable(False)
        for action in (self.act_back, self.act_forward, self.act_up, self.act_reload):
            nav.addAction(action)
        self.addToolBar(nav)

        tools = QToolBar(T("Actions"))
        tools.setObjectName("actions")
        tools.setMovable(False)
        tools.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        for action in (self.act_upload_files, self.act_upload_folder, self.act_new_folder, self.act_download, self.act_share):
            tools.addAction(action)
        tools.addAction(self.act_empty_trash)
        self.addToolBar(tools)

        # Sidebar
        self.sidebar = QListWidget()
        self.sidebar.setMinimumWidth(170)
        self.sidebar.setMaximumWidth(260)
        for path, title, icon_name in SECTIONS:
            item = QListWidgetItem(themed_icon(icon_name, QStyle.SP_DirIcon), title)
            item.setData(PATH_ROLE, path)
            self.sidebar.addItem(item)
        self.sidebar.currentRowChanged.connect(self._sidebar_changed)

        # Breadcrumb bar and filter
        self.crumb_bar = QWidget()
        self.crumb_layout = QHBoxLayout(self.crumb_bar)
        self.crumb_layout.setContentsMargins(0, 0, 0, 0)
        self.crumb_layout.setSpacing(0)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText(T("Filter …"))
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setMaximumWidth(240)
        top_row = QHBoxLayout()
        top_row.addWidget(self.crumb_bar, 1)
        top_row.addWidget(self.filter_edit)

        # File list
        self.model = QStandardItemModel(0, len(self.COLUMNS), self)
        self.model.setHorizontalHeaderLabels(self.COLUMNS)
        self.proxy = NodeProxy(self)
        self.proxy.setSourceModel(self.model)
        self.filter_edit.textChanged.connect(self.proxy.setFilterFixedString)

        self.view = DropTreeView()
        self.view.setModel(self.proxy)
        self.view.setRootIsDecorated(False)
        self.view.setUniformRowHeights(True)
        self.view.setAlternatingRowColors(True)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(0, Qt.AscendingOrder)
        self.view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._context_menu)
        self.view.activated.connect(lambda _index: self.open_selected())
        self.view.filesDropped.connect(self.upload_paths)
        self.view.selectionModel().selectionChanged.connect(lambda *_: self._update_actions())
        header = self.view.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        self.view.setColumnWidth(1, 100)
        self.view.setColumnWidth(2, 190)
        self.view.setColumnWidth(3, 140)
        self.view.setColumnWidth(4, 90)

        # Message page (errors, sign-in)
        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        retry_btn = QPushButton(T("Try again"))
        retry_btn.clicked.connect(self.reload)
        self.message_login_btn = QPushButton(T("Sign in …"))
        self.message_login_btn.clicked.connect(self.login)
        message_buttons = QHBoxLayout()
        message_buttons.addStretch(1)
        message_buttons.addWidget(retry_btn)
        message_buttons.addWidget(self.message_login_btn)
        message_buttons.addStretch(1)
        message_page = QWidget()
        message_layout = QVBoxLayout(message_page)
        message_layout.addStretch(1)
        message_layout.addWidget(self.message_label)
        message_layout.addLayout(message_buttons)
        message_layout.addStretch(1)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.view)
        self.stack.addWidget(message_page)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(6, 6, 6, 0)
        right_layout.addLayout(top_row)
        right_layout.addWidget(self.stack, 1)

        splitter = QSplitter()
        splitter.addWidget(self.sidebar)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([190, 900])
        self.setCentralWidget(splitter)

        # Transfers
        self.transfers = TransferPanel(self.cli)
        self.transfers.changed.connect(self._transfers_changed)
        self.transfer_dock = QDockWidget(T("Transfers"), self)
        self.transfer_dock.setObjectName("transfers")
        self.transfer_dock.setWidget(self.transfers)
        self.transfer_dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.transfer_dock)
        self.transfer_dock.hide()

        # Status bar
        self.busy_bar = QProgressBar()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setMaximumWidth(140)
        self.busy_bar.setTextVisible(False)
        self.busy_bar.hide()
        self.statusBar().addPermanentWidget(self.busy_bar)

    def _build_menus(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu(T("&File"))
        for action in (self.act_upload_files, self.act_upload_folder, self.act_new_folder, None, self.act_download, None, self.act_login, self.act_logout, None, self.act_quit):
            file_menu.addSeparator() if action is None else file_menu.addAction(action)

        edit_menu = menubar.addMenu(T("&Edit"))
        for action in (self.act_open, self.act_rename, self.act_move, self.act_copy, self.act_trash, None, self.act_share, self.act_properties, None, self.act_restore, self.act_delete, self.act_empty_trash):
            edit_menu.addSeparator() if action is None else edit_menu.addAction(action)

        view_menu = menubar.addMenu(T("&View"))
        for action in (self.act_back, self.act_forward, self.act_up, self.act_reload, None, self.act_filter):
            view_menu.addSeparator() if action is None else view_menu.addAction(action)
        view_menu.addSeparator()
        view_menu.addAction(self.transfer_dock.toggleViewAction())
        language_menu = view_menu.addMenu(T("Language"))
        language_group = QActionGroup(language_menu)
        saved_language = str(self.settings.value("language", "") or "")
        for value, label in (("", T("System default")), ("de", "Deutsch"), ("en", "English")):
            action = language_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(value == saved_language)
            action.triggered.connect(lambda _checked=False, v=value: self._set_language(v))
            language_group.addAction(action)

        conflict_menu = menubar.addMenu(T("&Conflicts"))
        self._strategy_menu(conflict_menu, T("Upload: existing file"), "upload_file", UPLOAD_FILE_STRATEGIES)
        self._strategy_menu(conflict_menu, T("Upload: existing folder"), "upload_folder", UPLOAD_FOLDER_STRATEGIES)
        conflict_menu.addSeparator()
        self._strategy_menu(conflict_menu, T("Download: existing file"), "download_file", DOWNLOAD_FILE_STRATEGIES)
        self._strategy_menu(conflict_menu, T("Download: existing folder"), "download_folder", DOWNLOAD_FOLDER_STRATEGIES)

    def _strategy_menu(self, parent: QMenu, title: str, key: str, options):
        menu = parent.addMenu(title)
        group = QActionGroup(menu)
        current = self.strategy(key, options)
        for value, label in options:
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(value == current)
            action.triggered.connect(lambda _checked=False, k=key, v=value: self.settings.setValue(f"conflict/{k}", v))
            group.addAction(action)

    def strategy(self, key: str, options=None) -> str:
        defaults = {
            "upload_file": UPLOAD_FILE_STRATEGIES,
            "upload_folder": UPLOAD_FOLDER_STRATEGIES,
            "download_file": DOWNLOAD_FILE_STRATEGIES,
            "download_folder": DOWNLOAD_FOLDER_STRATEGIES,
        }
        options = options or defaults[key]
        valid = [value for value, _ in options]
        value = self.settings.value(f"conflict/{key}", valid[0])
        return value if value in valid else valid[0]

    def _set_language(self, value: str):
        self.settings.setValue("language", value)
        self.settings.sync()
        QMessageBox.information(self, T("Language"), T("The new language is used after restarting the app."))

    def _restore_state(self):
        geometry = self.settings.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    # ----- State --------------------------------------------------------

    @property
    def section(self) -> str:
        return self.location[0].path if self.location else ""

    @property
    def current_path(self) -> str:
        return self.location[-1].path if self.location else ""

    def in_trash(self) -> bool:
        return self.section == "/trash"

    def can_write_here(self) -> bool:
        """May files be uploaded or a folder be created in the current folder?"""
        if not self.location or self.in_trash():
            return False
        if self.section != "/my-files" and len(self.location) == 1:
            return False
        return True

    def can_modify_items(self) -> bool:
        if not self.location or self.in_trash():
            return False
        if self.section in ("/devices", "/shared-with-me") and len(self.location) == 1:
            return False
        return True

    def selected_nodes(self) -> list[Node]:
        nodes = []
        for index in self.view.selectionModel().selectedRows(0):
            source = self.proxy.mapToSource(index)
            nodes.append(self.model.item(source.row(), 0).data(NODE_ROLE))
        return nodes

    def _update_actions(self):
        nodes = self.selected_nodes()
        count = len(nodes)
        trash = self.in_trash()
        modify = self.can_modify_items()
        write = self.can_write_here() and self.logged_in is not False
        plain = count > 0 and all(n.kind != "device" for n in nodes)

        self.act_back.setEnabled(bool(self.back_stack))
        self.act_forward.setEnabled(bool(self.forward_stack))
        self.act_up.setEnabled(len(self.location) > 1)
        self.act_upload_files.setEnabled(write)
        self.act_upload_folder.setEnabled(write)
        self.act_new_folder.setEnabled(write)
        self.view.drop_enabled = write
        self.act_download.setEnabled(plain and not trash)
        self.act_open.setEnabled(count == 1 and not (trash and nodes[0].is_container))
        self.act_rename.setEnabled(count == 1 and modify and plain)
        self.act_move.setEnabled(modify and plain)
        self.act_copy.setEnabled(plain and not trash)
        self.act_trash.setEnabled(modify and plain)
        self.act_share.setEnabled(count == 1 and plain and not trash)
        self.act_properties.setEnabled(count == 1)
        self.act_restore.setEnabled(trash and count > 0)
        self.act_delete.setEnabled(trash and count > 0)
        self.act_empty_trash.setVisible(trash)
        self.act_empty_trash.setEnabled(trash and self.model.rowCount() > 0)

    def _set_logged_in(self, state: bool):
        """Switches between "Sign in …" and "Sign out"."""
        self.logged_in = state
        self.act_login.setVisible(not state)
        self.act_logout.setVisible(state)
        self.message_login_btn.setVisible(not state)
        self._update_actions()

    def begin_busy(self, message: str = ""):
        self._busy += 1
        self.busy_bar.show()
        if message:
            self.statusBar().showMessage(message)

    def end_busy(self):
        self._busy = max(0, self._busy - 1)
        if self._busy == 0:
            self.busy_bar.hide()

    def show_error(self, title: str, message: str):
        QMessageBox.warning(self, title, message)

    # ----- Navigation -----------------------------------------------------

    def navigate(self, location: list[Crumb], push: bool = True):
        if push and self.location:
            self.back_stack.append(self.location)
            self.forward_stack.clear()
        self.location = list(location)
        self.filter_edit.clear()
        self.load()

    def go_back(self):
        if self.back_stack:
            self.forward_stack.append(self.location)
            self.location = self.back_stack.pop()
            self.load()

    def go_forward(self):
        if self.forward_stack:
            self.back_stack.append(self.location)
            self.location = self.forward_stack.pop()
            self.load()

    def go_up(self):
        if len(self.location) > 1:
            self.navigate(self.location[:-1])

    def reload(self):
        self.cache.pop(self.current_path, None)
        self.load()

    def _sidebar_changed(self, row: int):
        if row < 0:
            return
        path, title, _ = SECTIONS[row]
        if self.location and self.section == path and len(self.location) == 1:
            return
        self.navigate([Crumb(title, path)])

    def _sync_chrome(self):
        # Sidebar
        for row, (path, _, _) in enumerate(SECTIONS):
            if path == self.section:
                self.sidebar.blockSignals(True)
                self.sidebar.setCurrentRow(row)
                self.sidebar.blockSignals(False)
        # Breadcrumb bar
        while self.crumb_layout.count():
            widget = self.crumb_layout.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        for index, crumb in enumerate(self.location):
            if index:
                separator = QLabel("›")
                separator.setContentsMargins(2, 0, 2, 0)
                self.crumb_layout.addWidget(separator)
            button = QToolButton()
            button.setText(crumb.name)
            button.setAutoRaise(True)
            if index == len(self.location) - 1:
                font = button.font()
                font.setBold(True)
                button.setFont(font)
            button.clicked.connect(lambda _checked=False, i=index: self._crumb_clicked(i))
            self.crumb_layout.addWidget(button)
        self.crumb_layout.addStretch(1)
        self.setWindowTitle(f"{self.location[-1].name} – {APP_TITLE}")

    def _crumb_clicked(self, index: int):
        if index == len(self.location) - 1:
            self.reload()
        else:
            self.navigate(self.location[: index + 1])

    def load(self):
        self._sync_chrome()
        self._load_token += 1
        token = self._load_token
        path = self.current_path
        if path in self.cache:
            self._populate(self.cache[path])
            return
        self.model.removeRows(0, self.model.rowCount())
        self.stack.setCurrentIndex(0)
        self._update_actions()
        self.begin_busy(T("Loading {name} …").format(name=self.location[-1].name))

        def loaded(res: Result):
            self.end_busy()
            if token != self._load_token:
                return
            if not res.ok:
                if res.auth_error:
                    self.statusBar().showMessage(T("Not signed in"), 8000)
                    self.message_label.setText(
                        T("<b>You are not signed in.</b><br><br>Use “Sign in” to sign in. The sign-in itself happens in your browser.")
                    )
                else:
                    if self.logged_in is None:
                        # State unclear (e.g. no network): offer sign-in anyway.
                        self.act_login.setVisible(True)
                    hint = "" if self.logged_in else T("<br><br>If you are not signed in, use “Sign in”.")
                    self.statusBar().showMessage(T("Loading failed"), 8000)
                    self.message_label.setText(
                        T("<b>“{name}” could not be loaded.</b><br><br>{message}").format(name=self.location[-1].name, message=res.message.replace(chr(10), "<br>"))
                        + hint
                    )
                self.stack.setCurrentIndex(1)
                return
            nodes = parse_entries(path, res.data)
            self.cache[path] = nodes
            self._populate(nodes)

        self.cli.run(["filesystem", "list", "-j", "--", path], loaded)

    def _node_icon(self, node: Node) -> QIcon:
        if node.kind == "device":
            return themed_icon("computer", QStyle.SP_ComputerIcon)
        if node.kind == "folder":
            return themed_icon("folder", QStyle.SP_DirIcon)
        if node.kind == "album":
            return themed_icon("folder-pictures", QStyle.SP_DirIcon)
        key = node.media_type or Path(node.name).suffix.lower()
        if key not in self.icon_cache:
            mime = self.mime_db.mimeTypeForName(node.media_type) if node.media_type else None
            if mime is None or not mime.isValid():
                mime = self.mime_db.mimeTypeForFile(node.name, QMimeDatabase.MatchExtension)
            icon = QIcon.fromTheme(mime.iconName())
            if icon.isNull():
                icon = QIcon.fromTheme(mime.genericIconName())
            if icon.isNull():
                icon = self.style().standardIcon(QStyle.SP_FileIcon)
            self.icon_cache[key] = icon
        return self.icon_cache[key]

    def _type_text(self, node: Node) -> str:
        if node.kind == "folder":
            return T("Folder")
        if node.kind == "device":
            return f"Computer ({node.media_type})" if node.media_type else "Computer"
        if node.kind == "album":
            return "Album"
        if node.media_type:
            mime = self.mime_db.mimeTypeForName(node.media_type)
            if mime.isValid() and mime.comment():
                return mime.comment()
            return node.media_type
        return T("File")

    def _populate(self, nodes: list[Node]):
        self.stack.setCurrentIndex(0)
        self.model.removeRows(0, self.model.rowCount())
        for node in nodes:
            name_item = QStandardItem(self._node_icon(node), node.name)
            name_item.setData(node, NODE_ROLE)
            name_item.setData(node.name, SORT_ROLE)
            size_item = QStandardItem(human_size(node.size))
            size_item.setData(node.size if node.size is not None else -1, SORT_ROLE)
            size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            type_text = self._type_text(node)
            type_item = QStandardItem(type_text)
            type_item.setData(type_text, SORT_ROLE)
            time_item = QStandardItem(format_time(node.mtime or node.ctime))
            stamp = node.mtime or node.ctime
            time_item.setData(stamp.timestamp() if stamp else -1, SORT_ROLE)
            share_text = "Link" if node.shared_url else (T("Shared") if node.shared else "")
            share_item = QStandardItem(share_text)
            share_item.setData(share_text, SORT_ROLE)
            self.model.appendRow([name_item, size_item, type_item, time_item, share_item])
        folders = sum(1 for n in nodes if n.is_container)
        files = len(nodes) - folders
        total = sum(n.size or 0 for n in nodes)
        if nodes:
            self.statusBar().showMessage(T("{folders} folders, {files} files ({size})").format(folders=folders, files=files, size=human_size(total)))
        else:
            self.statusBar().showMessage(T("This folder is empty."))
        self._update_actions()

    # ----- Actions -------------------------------------------------------

    def _context_menu(self, pos):
        menu = QMenu(self)
        if self.in_trash():
            actions = [self.act_restore, self.act_delete, None, self.act_properties, None, self.act_empty_trash]
        elif self.selected_nodes():
            actions = [self.act_open, self.act_download, None, self.act_rename, self.act_move, self.act_copy, self.act_trash, None, self.act_share, self.act_properties]
        else:
            actions = [self.act_upload_files, self.act_upload_folder, self.act_new_folder, None, self.act_reload]
        for action in actions:
            menu.addSeparator() if action is None else menu.addAction(action)
        menu.exec(self.view.viewport().mapToGlobal(pos))

    def run_operation(self, args: list, what: str):
        """Runs a modifying CLI action and reloads afterwards."""
        self.begin_busy(f"{what} …")

        def finished(res: Result):
            self.end_busy()
            self.cache.clear()
            if not res.ok:
                self.statusBar().showMessage(T("{what}: failed").format(what=what), 8000)
                self.show_error(what, res.message)
            else:
                problems = failures_text(res.data)
                if problems:
                    self.show_error(what, T("Not everything worked:\n\n{problems}").format(problems=problems))
                self.statusBar().showMessage(T("{what}: done").format(what=what), 5000)
            self.load()

        self.cli.run(args, finished)

    def open_selected(self):
        nodes = self.selected_nodes()
        if len(nodes) != 1:
            return
        node = nodes[0]
        if node.is_container:
            if not self.in_trash():
                self.navigate(self.location + [Crumb(node.name, node.path)])
            return
        if self.in_trash():
            return
        if (node.size or 0) > 100 * 1024 * 1024:
            answer = QMessageBox.question(
                self, T("Open file"), T("“{name}” is {size} and will be downloaded to open it. Continue?").format(name=node.name, size=human_size(node.size))
            )
            if answer != QMessageBox.Yes:
                return
        target = self.open_cache / re.sub(r"[^A-Za-z0-9_-]", "_", node.uid or node.name)
        shutil.rmtree(target, ignore_errors=True)
        target.mkdir(parents=True, exist_ok=True)

        def downloaded(ok: bool, _res: Result):
            if not ok:
                return
            files = [p for p in target.iterdir() if p.is_file()]
            if files:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(files[0])))

        self._show_transfers()
        self.transfers.add(
            T("Open"), node.name, ["filesystem", "download", "-j", "-f", "rename", "-d", "merge", "--", node.path, str(target)], downloaded
        )

    def _show_transfers(self):
        self.transfer_dock.show()

    def _transfers_changed(self):
        if self.transfers.busy():
            self.transfer_dock.setWindowTitle(T("Transfers (running)"))
        else:
            self.transfer_dock.setWindowTitle(T("Transfers"))

    def upload_files(self):
        start = self.settings.value("paths/upload", str(Path.home()))
        paths, _ = QFileDialog.getOpenFileNames(self, T("Upload files"), start)
        if paths:
            self.settings.setValue("paths/upload", str(Path(paths[0]).parent))
            self.upload_paths(paths)

    def upload_folder(self):
        start = self.settings.value("paths/upload", str(Path.home()))
        path = QFileDialog.getExistingDirectory(self, T("Upload folder"), start)
        if path:
            self.settings.setValue("paths/upload", str(Path(path).parent))
            self.upload_paths([path])

    def upload_paths(self, paths: list[str]):
        if not self.can_write_here() or not paths:
            return
        target_path = self.current_path
        target_name = self.location[-1].name
        detail = Path(paths[0]).name if len(paths) == 1 else T("{count} items").format(count=len(paths))
        args = ["filesystem", "upload", "-j", "-f", self.strategy("upload_file"), "-d", self.strategy("upload_folder"), "--", *paths, target_path]

        def uploaded(_ok: bool, _res: Result):
            self.cache.pop(target_path, None)
            if self.current_path == target_path:
                self.load()

        self._show_transfers()
        self.transfers.add("Upload", f"{detail} → {target_name}", args, uploaded)

    def download_selected(self):
        nodes = [n for n in self.selected_nodes() if n.kind != "device"]
        if not nodes:
            return
        start = self.settings.value("paths/download", QStandardPaths.writableLocation(QStandardPaths.DownloadLocation))
        folder = QFileDialog.getExistingDirectory(self, T("Download to"), start)
        if not folder:
            return
        self.settings.setValue("paths/download", folder)
        detail = nodes[0].name if len(nodes) == 1 else T("{count} items").format(count=len(nodes))
        args = ["filesystem", "download", "-j", "-f", self.strategy("download_file"), "-d", self.strategy("download_folder"), "--", *[n.path for n in nodes], folder]
        self._show_transfers()
        self.transfers.add("Download", f"{detail} → {folder}", args)

    def new_folder(self):
        if not self.can_write_here():
            return
        name, ok = QInputDialog.getText(self, T("New folder"), T("Folder name:"))
        name = name.strip()
        if ok and name:
            self.run_operation(["filesystem", "create-folder", "-j", "--", self.current_path, name], T("Create folder"))

    def rename_selected(self):
        nodes = self.selected_nodes()
        if len(nodes) != 1 or not self.can_modify_items():
            return
        node = nodes[0]
        name, ok = QInputDialog.getText(self, T("Rename"), T("New name:"), text=node.name)
        name = name.strip()
        if ok and name and name != node.name:
            self.run_operation(["filesystem", "rename", "-j", "--", node.path, name], T("Rename"))

    def _pick_target(self, title: str) -> str | None:
        dialog = FolderPicker(self.cli, title, self)
        if dialog.exec() == QDialog.Accepted:
            return dialog.selected_path()
        return None

    def move_selected(self):
        nodes = self.selected_nodes()
        if not nodes or not self.can_modify_items():
            return
        target = self._pick_target(T("Move to"))
        if target and target != self.current_path:
            self.run_operation(["filesystem", "move", "-j", "--", *[n.path for n in nodes], target], T("Move"))

    def copy_selected(self):
        nodes = [n for n in self.selected_nodes() if n.kind != "device"]
        if not nodes or self.in_trash():
            return
        target = self._pick_target(T("Copy to"))
        if target:
            self.run_operation(["filesystem", "copy", "-j", "--", *[n.path for n in nodes], target], T("Copy"))

    def trash_selected(self):
        nodes = self.selected_nodes()
        if not nodes or not self.can_modify_items() or not self.view.hasFocus() and self.filter_edit.hasFocus():
            return
        self.run_operation(["filesystem", "trash", "-j", "--", *[n.path for n in nodes]], T("Moving to trash"))

    @staticmethod
    def _ambiguity_note(nodes: list[Node]) -> str:
        names = sorted({n.name for n in nodes if n.ambiguous})
        if not names:
            return ""
        listed = ", ".join(T("“{name}”").format(name=name) for name in names)
        return (
            T("\n\nWarning: {listed} exists more than once in the trash. The CLI cannot address items with the same name individually there and picks one of them itself.").format(listed=listed)
        )

    def restore_selected(self):
        nodes = self.selected_nodes()
        if not nodes or not self.in_trash():
            return
        note = self._ambiguity_note(nodes)
        if note and QMessageBox.question(self, T("Restore"), T("Restore the selection?") + note) != QMessageBox.Yes:
            return
        paths = list(dict.fromkeys(n.path for n in nodes))
        self.run_operation(["filesystem", "restore", "-j", "--", *paths], T("Restore"))

    def delete_selected(self):
        nodes = self.selected_nodes()
        if not nodes or not self.in_trash():
            return
        label = T("“{name}”").format(name=nodes[0].name) if len(nodes) == 1 else T("{count} items").format(count=len(nodes))
        answer = QMessageBox.warning(
            self,
            T("Delete permanently"),
            T("Permanently delete {label}?\nThis cannot be undone.").format(label=label) + self._ambiguity_note(nodes),
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer == QMessageBox.Yes:
            paths = list(dict.fromkeys(n.path for n in nodes))
            self.run_operation(["filesystem", "delete", "-j", "--", *paths], T("Delete permanently"))

    def empty_trash(self):
        answer = QMessageBox.warning(
            self,
            T("Empty trash"),
            T("Permanently delete all items in the trash?\nThis cannot be undone."),
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer == QMessageBox.Yes:
            self.run_operation(["filesystem", "empty-trash", "-j"], T("Empty trash"))

    def share_selected(self):
        nodes = self.selected_nodes()
        if len(nodes) != 1 or nodes[0].kind == "device":
            return
        dialog = ShareDialog(self.cli, nodes[0], self)
        dialog.exec()
        if dialog.changed:
            self.cache.clear()
            self.load()

    def show_properties(self):
        nodes = self.selected_nodes()
        if len(nodes) != 1:
            return
        node = nodes[0]
        dialog = QDialog(self)
        dialog.setWindowTitle(T("Properties – {name}").format(name=node.name))
        form = QFormLayout()

        def row(label: str, value: str) -> QLabel:
            widget = QLabel(value or "–")
            widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
            widget.setWordWrap(True)
            form.addRow(label, widget)
            return widget

        row("Name:", node.name)
        row(T("Type:"), self._type_text(node))
        size_label = row(T("Size:"), human_size(node.size) if node.size is not None else T("calculating …"))
        row(T("Modified:"), format_time(node.mtime))
        row(T("Created:"), format_time(node.ctime))
        row(T("Owner:"), node.owner)
        row(T("My role:"), node.role)
        row(T("Sharing:"), T("Public link") if node.shared_url else (T("Shared") if node.shared else T("Not shared")))
        row(T("ID:"), node.uid)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText(T("Close"))
        buttons.rejected.connect(dialog.reject)
        layout = QVBoxLayout(dialog)
        layout.addLayout(form)
        layout.addWidget(buttons)
        dialog.setMinimumWidth(460)
        state = {"open": True}
        dialog.finished.connect(lambda _code: state.update(open=False))

        if node.size is None:
            if node.kind == "device" or self.in_trash():
                size_label.setText("–")
            else:

                def sized(res: Result):
                    if not state["open"]:
                        return
                    if res.ok and isinstance(res.data, dict):
                        count = res.data.get("numberOfDescendants", 0)
                        size_label.setText(T("{size} in {count} items (incl. trash)").format(size=human_size(res.data.get("size", 0)), count=count))
                    else:
                        size_label.setText(T("unknown"))

                self.cli.run(["filesystem", "size", "-j", "--", node.path], sized)
        dialog.exec()

    def login(self):
        dialog = LoginDialog(self.cli, self)
        if dialog.exec() == QDialog.Accepted:
            self.cache.clear()
            self.load()

    def logout(self):
        if self.transfers.busy():
            QMessageBox.information(self, T("Sign out"), T("Transfers are still running. Wait until they finish, or cancel them."))
            return
        answer = QMessageBox.question(
            self,
            T("Sign out"),
            T("Sign out of Proton Drive?\nThe CLI deletes its local credentials and caches. Your files in the Drive stay unchanged."),
        )
        if answer != QMessageBox.Yes:
            return
        self.begin_busy(T("Signing out …"))

        def finished(res: Result):
            self.end_busy()
            if not res.ok:
                self.statusBar().showMessage(T("Signing out failed"), 8000)
                self.show_error(T("Sign out"), res.message)
                return
            # Calls still in flight must not flip the state back to signed in.
            self.cli.invalidate_session()
            self._load_token += 1
            self.cache.clear()
            self.model.removeRows(0, self.model.rowCount())
            self._set_logged_in(False)
            self.message_label.setText(T("<b>You are signed out.</b><br><br>Use “Sign in” to sign in again."))
            self.stack.setCurrentIndex(1)
            self.statusBar().showMessage(T("Signed out"), 5000)

        self.cli.run(["auth", "logout"], finished, parse_json=False)

    # ----- Quit --------------------------------------------------------

    def closeEvent(self, event):
        if self.transfers.busy():
            answer = QMessageBox.question(
                self, T("Quit"), T("Transfers are still running. Quit anyway and cancel them?")
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.cli.shutdown()
        shutil.rmtree(self.open_cache, ignore_errors=True)
        event.accept()


def main() -> int:
    if LANGUAGE != system_language():
        # Numbers, sizes and dates follow the chosen language as well.
        QLocale.setDefault(QLocale(QLocale.German if LANGUAGE == "de" else QLocale.English))
    app = QApplication(sys.argv)
    qt_translator = QTranslator(app)  # Qt's own texts, e.g. the Yes/No buttons
    if LANGUAGE == "de" and qt_translator.load("qtbase_de", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(qt_translator)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_TITLE)
    # Ties the window to the launcher entry proton-drive-ui.desktop.
    app.setDesktopFileName(APP_NAME)
    setup_icon_theme()
    app.setWindowIcon(app_icon())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
