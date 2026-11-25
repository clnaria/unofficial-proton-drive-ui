"""The German translation table must cover exactly the texts the app uses."""

import ast
import string
from pathlib import Path

from proton_drive_ui.translations import GERMAN

APP_SOURCE = Path(__file__).resolve().parent.parent / "proton_drive_ui" / "app.py"


def used_texts() -> set[str]:
    """All string literals passed to T(...) in the app."""
    texts = set()
    for call in ast.walk(ast.parse(APP_SOURCE.read_text(encoding="utf-8"))):
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "T":
            argument = call.args[0]
            assert isinstance(argument, ast.Constant), f"T() needs a literal text (line {call.lineno})"
            texts.add(argument.value)
    return texts


def placeholders(text: str) -> list[str]:
    return sorted(name for _, name, _, _ in string.Formatter().parse(text) if name)


def test_every_text_has_a_german_translation():
    assert used_texts() - set(GERMAN) == set()


def test_no_stale_translations():
    assert set(GERMAN) - used_texts() == set()


def test_placeholders_match():
    mismatched = [english for english, german in GERMAN.items() if placeholders(english) != placeholders(german)]
    assert mismatched == []
