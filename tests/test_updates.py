"""Tests for ``toolkit.updates`` — Microsoft Store update check.

Round 30. The module's whole job is to fail silently in every branch
that isn't "Windows + MSIX-installed-from-Store + update available",
so most tests exercise the silent-fail paths. The happy path is
exercised via a mocked ``StoreContext``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from toolkit import updates
from toolkit.updates import UpdateInfo, check_for_store_updates


def test_returns_none_when_api_unavailable() -> None:
    """On non-Windows / no winrt installed, the function returns None
    without raising."""
    with patch.object(updates, "HAVE_STORE_API", False):
        result = check_for_store_updates()
    assert result is None


def test_returns_none_when_storecontext_raises() -> None:
    """If StoreContext.get_default() raises (e.g. side-loaded install,
    Store client wedged), the function returns None silently."""

    fake_context_cls = MagicMock()
    fake_context_cls.get_default.side_effect = RuntimeError("no Store identity")

    with (
        patch.object(updates, "HAVE_STORE_API", True),
        patch.object(updates, "_StoreContext", fake_context_cls),
    ):
        result = check_for_store_updates(timeout_seconds=1.0)

    assert result is None


def test_returns_none_when_no_updates_pending() -> None:
    """Empty update list → None (the user is on the latest version)."""

    fake_context = MagicMock()

    async def _no_updates() -> list[object]:
        return []

    fake_context.get_app_and_optional_store_package_updates_async = _no_updates

    fake_context_cls = MagicMock()
    fake_context_cls.get_default.return_value = fake_context

    with (
        patch.object(updates, "HAVE_STORE_API", True),
        patch.object(updates, "_StoreContext", fake_context_cls),
    ):
        result = check_for_store_updates(timeout_seconds=1.0)

    assert result is None


def test_returns_update_info_when_updates_pending() -> None:
    """One pending non-mandatory update → UpdateInfo(count=1, mandatory=False)."""

    pkg = MagicMock()
    pkg.mandatory = False

    fake_context = MagicMock()

    async def _one_update() -> list[object]:
        return [pkg]

    fake_context.get_app_and_optional_store_package_updates_async = _one_update

    fake_context_cls = MagicMock()
    fake_context_cls.get_default.return_value = fake_context

    with (
        patch.object(updates, "HAVE_STORE_API", True),
        patch.object(updates, "_StoreContext", fake_context_cls),
    ):
        result = check_for_store_updates(timeout_seconds=1.0)

    assert isinstance(result, UpdateInfo)
    assert result.package_count == 1
    assert result.is_mandatory is False


def test_mandatory_flag_propagates_when_any_update_is_mandatory() -> None:
    """Two updates, one marked mandatory → UpdateInfo.is_mandatory == True."""

    pkg_a = MagicMock()
    pkg_a.mandatory = False
    pkg_b = MagicMock()
    pkg_b.mandatory = True

    fake_context = MagicMock()

    async def _two_updates() -> list[object]:
        return [pkg_a, pkg_b]

    fake_context.get_app_and_optional_store_package_updates_async = _two_updates

    fake_context_cls = MagicMock()
    fake_context_cls.get_default.return_value = fake_context

    with (
        patch.object(updates, "HAVE_STORE_API", True),
        patch.object(updates, "_StoreContext", fake_context_cls),
    ):
        result = check_for_store_updates(timeout_seconds=1.0)

    assert result is not None
    assert result.package_count == 2
    assert result.is_mandatory is True


def test_returns_none_on_timeout() -> None:
    """If the WinRT call exceeds ``timeout_seconds`` the function
    returns None instead of hanging."""
    import asyncio

    fake_context = MagicMock()

    async def _slow_check() -> list[object]:
        await asyncio.sleep(2.0)
        return []

    fake_context.get_app_and_optional_store_package_updates_async = _slow_check

    fake_context_cls = MagicMock()
    fake_context_cls.get_default.return_value = fake_context

    with (
        patch.object(updates, "HAVE_STORE_API", True),
        patch.object(updates, "_StoreContext", fake_context_cls),
    ):
        result = check_for_store_updates(timeout_seconds=0.1)

    assert result is None


def test_update_info_dataclass_is_frozen() -> None:
    """UpdateInfo is frozen — guards accidental mutation by callers."""
    from dataclasses import FrozenInstanceError

    info = UpdateInfo(package_count=1, is_mandatory=False)
    with pytest.raises(FrozenInstanceError):
        info.package_count = 2  # type: ignore[misc]
