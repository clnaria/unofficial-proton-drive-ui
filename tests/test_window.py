"""The main window, driven against the fake CLI from conftest.py."""

from PySide6.QtWidgets import QInputDialog, QMessageBox

from conftest import node
from helpers import select, visible_names, wait_until
from proton_drive_ui import app as ui


def idle(window) -> bool:
    return window._busy == 0 and not window.transfers.busy()


def test_lists_folders_before_files(window):
    assert visible_names(window) == ["Folder A", "notes.txt"]
    assert window.statusBar().currentMessage().startswith("1 folders, 1 files")
    assert window.windowTitle() == "My files – Proton Drive UI (unofficial)"


def test_open_folder_and_go_back(window):
    select(window, "Folder A")
    window.open_selected()
    wait_until(lambda: idle(window) and len(window.location) == 2)

    assert visible_names(window) == ["inner.txt"]
    assert window.act_back.isEnabled() and window.act_up.isEnabled()

    window.go_back()
    wait_until(lambda: idle(window))
    assert visible_names(window) == ["Folder A", "notes.txt"]


def test_filter_narrows_the_list(window):
    window.filter_edit.setText("note")
    assert visible_names(window) == ["notes.txt"]


def test_missing_folder_shows_the_message_page(window):
    window.navigate([ui.Crumb("Gone", "/my-files/does-not-exist")])
    wait_until(lambda: idle(window))

    assert window.stack.currentIndex() == 1
    assert "could not be loaded" in window.message_label.text()
    assert "Node not found" in window.message_label.text()


def test_signed_in_offers_only_sign_out(window):
    assert window.logged_in is True
    assert window.act_logout.isVisible() and not window.act_login.isVisible()


def test_signed_out_at_start_offers_only_sign_in(fake_cli, make_window):
    fake_cli.sign_out()
    window = make_window()

    assert window.logged_in is False
    assert window.act_login.isVisible() and not window.act_logout.isVisible()
    assert "not signed in" in window.message_label.text()
    assert not window.act_upload_files.isEnabled()


def test_sign_out_then_sign_in(window, fake_cli, monkeypatch):
    questions = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: questions.append(args[2]) or QMessageBox.Yes)

    window.logout()
    wait_until(lambda: idle(window) and window.logged_in is False)

    assert questions and questions[0].startswith("Sign out of Proton Drive?")
    assert "auth logout" in fake_cli.calls()
    assert window.act_login.isVisible() and not window.act_logout.isVisible()
    assert visible_names(window) == [] and window.stack.currentIndex() == 1
    assert not window.act_upload_files.isEnabled()

    window.login()  # the dialog closes itself once the fake CLI reports success
    wait_until(lambda: idle(window) and window.logged_in is True)

    assert window.act_logout.isVisible() and not window.act_login.isVisible()
    assert visible_names(window) == ["Folder A", "notes.txt"]


def test_new_folder_calls_the_cli_and_reloads(window, fake_cli, monkeypatch):
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("-Reports", True))
    fake_cli.set_listing("/my-files", [node("vol~new", "-Reports", kind="folder")])

    window.new_folder()
    wait_until(lambda: idle(window) and visible_names(window) == ["-Reports"])

    # "--" keeps a name that starts with a dash from being read as an option.
    assert "filesystem create-folder -j -- /my-files -Reports" in fake_cli.calls()
    assert visible_names(window) == ["-Reports"]


def test_cancel_stops_the_running_upload_without_a_selection(window, tmp_path):
    local_file = tmp_path / "upload.bin"
    local_file.write_bytes(b"x" * 10)
    panel = window.transfers
    assert not panel.cancel_btn.isEnabled()

    window.upload_paths([str(local_file)])
    wait_until(lambda: panel.current is not None)
    transfer = panel.transfers[-1]
    assert transfer.state == "running" and panel.cancel_btn.isEnabled()
    assert panel.tree.selectedItems() == []

    panel.cancel_btn.click()
    wait_until(lambda: transfer.state == "cancelled")

    assert transfer.state == "cancelled" and transfer.item.text(2) == "Cancelled"
    assert not panel.busy() and not panel.cancel_btn.isEnabled()


def test_duplicate_names_in_trash_ask_before_restoring(window, fake_cli, monkeypatch):
    fake_cli.set_listing("/trash", [node("vol~1", "same"), node("vol~2", "same")])
    questions = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: questions.append(args[2]) or QMessageBox.No)

    window.sidebar.setCurrentRow(4)
    wait_until(lambda: idle(window) and visible_names(window) == ["same", "same"])
    select(window, "same")
    window.restore_selected()

    assert len(questions) == 1 and "more than once in the trash" in questions[0]
    assert not any(call.startswith("filesystem restore") for call in fake_cli.calls())


def test_unique_name_in_trash_restores_by_name(window, fake_cli):
    fake_cli.set_listing("/trash", [node("vol~1", "old.txt")])

    window.sidebar.setCurrentRow(4)
    wait_until(lambda: idle(window) and visible_names(window) == ["old.txt"])
    select(window, "old.txt")
    window.restore_selected()
    wait_until(lambda: any(call.startswith("filesystem restore") for call in fake_cli.calls()))

    assert "filesystem restore -j -- /trash/old.txt" in fake_cli.calls()
