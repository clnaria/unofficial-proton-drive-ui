"""Parsing of CLI output into the app's data model."""

from conftest import node
from proton_drive_ui import app as ui


def test_file_and_folder_are_addressed_by_uid():
    entries = [
        node("vol~f", "report.pdf", mediaType="application/pdf", activeRevision={"claimedSize": 1234}),
        node("vol~d", "Photos", kind="folder"),
    ]
    file, folder = ui.parse_entries("/my-files", entries)

    assert (file.name, file.kind, file.path, file.size) == ("report.pdf", "file", "/my-files/vol~f", 1234)
    assert (folder.kind, folder.path, folder.size) == ("folder", "/my-files/vol~d", None)
    assert folder.is_container and not file.is_container


def test_media_type_parameters_are_stripped():
    (parsed,) = ui.parse_entries("/my-files", [node("vol~f", "a.txt", mediaType="text/plain;charset=utf-8")])
    assert parsed.media_type == "text/plain"


def test_size_falls_back_to_storage_size():
    (parsed,) = ui.parse_entries("/my-files", [node("vol~f", "a.bin", activeRevision={"storageSize": 77})])
    assert parsed.size == 77


def test_unreadable_name_gets_a_placeholder_and_keeps_the_uid_path():
    entry = {"uid": "vol~abcdefgh12345678", "name": {"ok": False, "error": "decryption failed"}, "type": "file"}
    (parsed,) = ui.parse_entries("/my-files", [entry])

    assert parsed.path == "/my-files/vol~abcdefgh12345678"
    assert parsed.name.endswith("12345678")


def test_device_uses_its_escaped_name():
    entry = {"uid": "dev1", "type": "Windows", "rootFolderUid": "vol~root", "name": {"ok": True, "value": "PC/Home"}}
    (parsed,) = ui.parse_entries("/devices", [entry])

    assert (parsed.kind, parsed.path) == ("device", "/devices/PC\\/Home")
    assert parsed.is_container


def test_trash_addresses_items_by_name_and_flags_duplicates():
    entries = [node("vol~1", "same"), node("vol~2", "same"), node("vol~3", "a/b")]
    first, second, third = ui.parse_entries("/trash", entries)

    assert first.path == second.path == "/trash/same"
    assert first.ambiguous and second.ambiguous
    assert third.path == "/trash/a\\/b" and not third.ambiguous


def test_non_list_output_yields_no_nodes():
    assert ui.parse_entries("/my-files", None) == []
    assert ui.parse_entries("/my-files", {"unexpected": True}) == []


def test_failures_text_reports_failed_items_only():
    assert ui.failures_text([{"uid": "a", "ok": True}]) == ""
    assert "boom" in ui.failures_text([{"uid": "a", "ok": True}, {"uid": "b", "ok": False, "error": "boom"}])
    assert ui.failures_text({"failedItems": 0, "failures": []}) == ""
    assert "broken" in ui.failures_text({"failedItems": 1, "failures": [{"error": "broken"}]})
    assert ui.failures_text(None) == ""


def test_escape_name_escapes_slashes_only():
    assert ui.escape_name("a/b c") == "a\\/b c"
