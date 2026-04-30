"""Tests for toolkit/files.py — open_output_folder helper."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import pytest

from toolkit.files import open_output_folder

# ---------------------------------------------------------------------------
# open_output_folder — platform behaviour
# ---------------------------------------------------------------------------


def test_open_output_folder_uses_string_form_on_win32(monkeypatch: pytest.MonkeyPatch) -> None:
    """Critical regression — see CLAUDE.md OneDrive gotcha.

    On win32, subprocess.Popen must receive a STRING (not a list) so
    explorer's /select parser handles paths with spaces (e.g. OneDrive paths).
    The list form triggers Python's list2cmdline, which explorer does not
    recognise, causing it to fall back to opening the default Documents folder.
    """
    captured: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: captured.append((a, kw)))
    p = Path("C:/Users/test/OneDrive - Org/file with spaces.xlsx")
    monkeypatch.setattr(Path, "exists", lambda self: True)  # bypass existence check

    open_output_folder(p)

    assert captured, "Popen never called"
    args, kwargs = captured[0]
    cmd = args[0]
    assert isinstance(cmd, str), (
        f"Bug regression: subprocess.Popen must receive a STRING (not list) "
        f'so explorer parses /select,"<path>" correctly when path has spaces; '
        f"got {type(cmd).__name__}: {cmd!r}"
    )
    assert '/select,"' in cmd, f"Expected '/select,\"' in command, got: {cmd!r}"
    assert str(p) in cmd, f"Expected path {str(p)!r} in command, got: {cmd!r}"


def test_open_output_folder_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    """macOS path uses ``open -R <path>`` as a list form."""
    captured: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: captured.append((a, kw)))
    p = Path("/Users/test/Documents/file.xlsx")
    monkeypatch.setattr(Path, "exists", lambda self: True)

    open_output_folder(p)

    assert captured, "Popen never called on macOS"
    args, _ = captured[0]
    cmd = args[0]
    assert isinstance(cmd, list), f"macOS cmd should be a list, got {type(cmd).__name__}"
    assert cmd[:2] == ["open", "-R"], f"macOS cmd should start with ['open', '-R'], got {cmd!r}"
    assert str(p) in cmd, f"Path {str(p)!r} should appear in cmd {cmd!r}"


def test_open_output_folder_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    """Linux path uses ``xdg-open <parent>`` — no 'select' verb available."""
    captured: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: captured.append((a, kw)))
    p = Path("/home/test/Documents/file.xlsx")
    monkeypatch.setattr(Path, "exists", lambda self: True)

    open_output_folder(p)

    assert captured, "Popen never called on Linux"
    args, _ = captured[0]
    cmd = args[0]
    assert isinstance(cmd, list), f"Linux cmd should be a list, got {type(cmd).__name__}"
    assert cmd[0] == "xdg-open", f"Linux cmd should use xdg-open, got {cmd!r}"
    # Linux opens the parent directory, not the file itself
    assert str(p.parent) in cmd, f"Parent {str(p.parent)!r} should appear in cmd {cmd!r}"


def test_open_output_folder_swallows_oserror(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """OSError from Popen must be caught and logged at WARNING — never re-raised."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(Path, "exists", lambda self: True)

    def exploding_popen(*a: object, **kw: object) -> None:
        raise OSError("xdg-open not found")

    monkeypatch.setattr(subprocess, "Popen", exploding_popen)

    with caplog.at_level(logging.WARNING, logger="toolkit.files"):
        open_output_folder(Path("/tmp/file.xlsx"))  # should not raise

    assert any("open_output_folder failed" in r.message for r in caplog.records), (
        "Expected a WARNING log record containing 'open_output_folder failed'"
    )


def test_open_output_folder_returns_silently_when_path_missing(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """When the path does not exist, return without calling Popen and log a warning."""
    called: list[object] = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: called.append(a))
    monkeypatch.setattr(Path, "exists", lambda self: False)

    with caplog.at_level(logging.WARNING, logger="toolkit.files"):
        open_output_folder(Path("/tmp/does_not_exist.xlsx"))

    assert not called, "Popen must not be called when path does not exist"
    assert any("does not exist" in r.message for r in caplog.records), (
        "Expected a WARNING log record mentioning 'does not exist'"
    )
