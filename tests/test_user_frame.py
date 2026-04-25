"""Tests for toolkit.user_frame.UserFrame.

Skips cleanly when tkinter is not available (CI without a display).
Mocks toolkit.account and toolkit.licence via unittest.mock.patch so
tests run before P5 lands.
"""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Skip guard — must appear before any tkinter import
# ---------------------------------------------------------------------------

try:
    import tkinter as tk
except ImportError as _tk_exc:
    pytest.skip(f"tkinter not installed: {_tk_exc}", allow_module_level=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_account_state(is_signed_in: bool = False) -> MagicMock:
    state = MagicMock()
    state.is_signed_in = is_signed_in
    state.email = "test@school.edu.au" if is_signed_in else None
    state.first_name = "Test" if is_signed_in else None
    state.last_name = "User" if is_signed_in else None
    state.school_name = "Example Secondary College" if is_signed_in else None
    state.school_abn = "12345678901" if is_signed_in else None
    return state


def _make_licence_status(
    state: str = "none",
    expires_at: datetime.datetime | None = None,
    devices: list[str] | None = None,
) -> MagicMock:
    lic = MagicMock()
    lic.state = state
    lic.expires_at = expires_at
    lic.devices = devices or []
    return lic


# ---------------------------------------------------------------------------
# Fixture: headless Tk root
# ---------------------------------------------------------------------------


@pytest.fixture()
def tk_root() -> Any:
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError as exc:
        pytest.skip(f"No display available for Tk: {exc}")
        return

    yield root
    root.destroy()


# ---------------------------------------------------------------------------
# Helper: build a UserFrame with controlled mocks
# ---------------------------------------------------------------------------


def _build_frame(
    root: tk.Tk,
    *,
    is_signed_in: bool = False,
    licence_state: str = "none",
    expires_at: datetime.datetime | None = None,
) -> Any:
    """Import UserFrame and build it inside root with mocked P5 modules."""
    account_state = _make_account_state(is_signed_in=is_signed_in)
    licence_status = _make_licence_status(
        state=licence_state,
        expires_at=expires_at,
    )

    account_mod = MagicMock()
    account_mod.load_state.return_value = account_state
    account_mod.login = MagicMock()
    account_mod.logout = MagicMock()
    account_mod.register = MagicMock()
    account_mod.request_password_reset = MagicMock()
    account_mod.change_password = MagicMock()

    licence_mod = MagicMock()
    licence_mod.read_status.return_value = licence_status
    licence_mod.refresh.return_value = licence_status

    with (
        patch.dict("sys.modules", {
            "toolkit.account": account_mod,
            "toolkit.licence": licence_mod,
        }),
    ):
        from toolkit.user_frame import UserFrame  # noqa: PLC0415

        frame = UserFrame(root)  # type: ignore[arg-type]
        frame.pack(fill="both", expand=True)
        root.update_idletasks()
        return frame


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_user_frame_constructs(tk_root: tk.Tk) -> None:
    """UserFrame should build without raising when P5 modules are mocked."""
    frame = _build_frame(tk_root)
    assert frame is not None
    tk_root.update_idletasks()


def test_pre_signin_sign_in_button_visible(tk_root: tk.Tk) -> None:
    """Pre-sign-in state: a 'Sign in' button must exist in the widget tree."""
    frame = _build_frame(tk_root, is_signed_in=False)
    tk_root.update_idletasks()

    found = _find_buttons(frame, "Sign in")
    assert found, "Expected a 'Sign in' button in the pre-sign-in state"


def test_pre_signin_change_password_not_visible(tk_root: tk.Tk) -> None:
    """Pre-sign-in state: 'Change password' button must not be present."""
    frame = _build_frame(tk_root, is_signed_in=False)
    tk_root.update_idletasks()

    found = _find_buttons(frame, "Change password")
    assert not found, "Expected no 'Change password' button in the pre-sign-in state"


def test_post_signin_sign_in_button_hidden(tk_root: tk.Tk) -> None:
    """Post-sign-in state: 'Sign in' button must not be present."""
    frame = _build_frame(tk_root, is_signed_in=True)
    tk_root.update_idletasks()

    found = _find_buttons(frame, "Sign in")
    assert not found, "Expected no 'Sign in' button in the post-sign-in state"


def test_post_signin_change_password_visible(tk_root: tk.Tk) -> None:
    """Post-sign-in state: 'Change password' button must be present."""
    frame = _build_frame(tk_root, is_signed_in=True)
    tk_root.update_idletasks()

    found = _find_buttons(frame, "Change password")
    assert found, "Expected 'Change password' button in the post-sign-in state"


def test_active_licence_pill(tk_root: tk.Tk) -> None:
    """Active licence: status pill text should contain 'Active until YYYY-MM-DD'."""
    expires = datetime.datetime(2027, 5, 1, 0, 0, 0)
    frame = _build_frame(
        tk_root,
        is_signed_in=True,
        licence_state="active",
        expires_at=expires,
    )
    tk_root.update_idletasks()

    pill_text = _find_pill_text(frame)
    assert pill_text is not None, "Could not locate the status pill label"
    assert "Active until 2027-05-01" in pill_text, (
        f"Expected 'Active until 2027-05-01' in pill text, got: {pill_text!r}"
    )


# ---------------------------------------------------------------------------
# Recursive widget-search utilities
# ---------------------------------------------------------------------------


def _find_buttons(widget: tk.Widget, text: str) -> list[Any]:
    """Recursively find all ttk.Button / tk.Button widgets with the given text."""
    import tkinter.ttk as ttk

    found: list[Any] = []

    def _walk(w: tk.Widget) -> None:
        if isinstance(w, (ttk.Button, tk.Button)):
            try:
                btn_text = str(w.cget("text"))
                if btn_text == text:
                    found.append(w)
            except Exception:
                pass
        for child in w.winfo_children():
            if isinstance(child, tk.Widget):
                _walk(child)

    _walk(widget)
    return found


def _find_pill_text(widget: tk.Widget) -> str | None:
    """Return the text of the status pill label (identified by it being a
    tk.Label whose text starts with 'Active' or 'No licence' etc.)."""
    from toolkit.user_frame import _STATE_LABELS  # noqa: PLC0415

    known_starts = list(_STATE_LABELS.values()) + ["Active until", "Expired (grace"]

    def _walk(w: tk.Widget) -> str | None:
        if isinstance(w, tk.Label):
            try:
                t = str(w.cget("text"))
                for prefix in known_starts:
                    if t.startswith(prefix):
                        return t
            except Exception:
                pass
        for child in w.winfo_children():
            if isinstance(child, tk.Widget):
                result = _walk(child)
                if result is not None:
                    return result
        return None

    return _walk(widget)
