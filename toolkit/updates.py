"""Microsoft Store update check.

Round 30 — On app startup, ask the Microsoft Store whether any package
updates are available for our MSIX bundle. If yes, ``app.py`` shows a
modal dialog offering to open the Store for the user to install the
update.

Privacy posture
---------------
* Per CLAUDE.md the free tools are "100% offline, zero server calls".
  This module makes a single network call AT STARTUP through the
  Microsoft Store client (already running on every Windows machine).
  No request goes to our backend; no telemetry is sent. The call is
  initiated by ``StoreContext.get_default()`` and routes via
  ``Windows.Services.Store`` — same path the Store app itself uses
  when it auto-checks for updates. From a privacy standpoint this is
  equivalent to the OS-level update check Windows already performs.
* Failure modes (non-Windows, non-MSIX install, network down, API
  unavailable, timeout) all return ``None`` silently — no error
  surfaced to the user, no banner, no log noise.
* The check runs on a background thread so it cannot block the UI
  thread. ``app.py`` schedules the dialog onto the Tk main loop via
  ``root.after`` once the result is in.

Microsoft Store API
-------------------
The ``Windows.Services.Store.StoreContext`` class is a Windows
Runtime (WinRT) API. We use the ``winrt`` PyPI package (released by
Microsoft) to invoke it from Python. The relevant call is:

    context = StoreContext.get_default()
    updates = await context.get_app_and_optional_store_package_updates_async()

``updates`` is an ``IVectorView<StorePackageUpdate>`` — empty when no
updates are pending, populated otherwise. Each update has a
``.mandatory`` flag we surface as ``UpdateInfo.is_mandatory``.

This API only returns updates for apps installed via MSIX from the
Microsoft Store. Sideloaded MSIX bundles, dev-installed builds, and
PyInstaller .exes return no updates because Windows can't correlate
them to a Store listing — those installs see ``None`` from this
function and fall through silently.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UpdateInfo:
    """Result of a successful Store update check.

    ``package_count`` is the number of packages waiting to be installed
    (almost always 1 for our app — the main MSIX bundle — but the
    Store API supports optional / framework dependencies so we report
    the count for completeness).

    ``is_mandatory`` mirrors the ``mandatory`` flag on any of the
    pending updates. Microsoft uses this to mark security or compat
    updates that the user shouldn't be able to skip; the dialog text
    in ``app.py`` adjusts wording accordingly.
    """

    package_count: int
    is_mandatory: bool


# ---------------------------------------------------------------------------
# Guarded WinRT import — Windows-only, gracefully degrades elsewhere.
# ---------------------------------------------------------------------------

# Pre-declare so the rest of the module typechecks without ``winrt`` stubs.
_StoreContext: Any = None
HAVE_STORE_API: bool = False

if sys.platform == "win32":
    try:
        # ``winrt`` is the Microsoft-published Python ↔ WinRT bridge.
        # Each WinRT namespace ships as its own pip package (e.g.
        # ``winrt-Windows.Services.Store``) and is imported as
        # ``winrt.windows.services.store``.
        from winrt.windows.services.store import (
            StoreContext as _StoreContext,  # type: ignore[import-not-found]
        )

        HAVE_STORE_API = True
    except ImportError:
        # The winrt deps aren't installed (e.g. dev environment without
        # the Windows-only optional deps, or PyInstaller bundle that
        # didn't include them). Function returns None silently.
        HAVE_STORE_API = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_for_store_updates(timeout_seconds: float = 5.0) -> UpdateInfo | None:
    """Synchronously check the Microsoft Store for app updates.

    Returns
    -------
    UpdateInfo | None
        ``UpdateInfo`` when at least one update is pending. ``None``
        in every other case — non-Windows, non-MSIX install, network
        failure, timeout, or unexpected API error. The caller does
        not need to handle exceptions.

    Notes
    -----
    Call this from a background thread — the WinRT call itself is
    async and we drive it via a short-lived event loop. The 5-second
    timeout guarantees the check can never hang the calling thread
    indefinitely (e.g. on a machine with a wedged Store client).
    """
    if not HAVE_STORE_API:
        return None

    try:
        # Each call gets its own event loop so we don't disturb any
        # asyncio state the host app might have. ``new_event_loop``
        # + ``close`` is safe on a worker thread.
        loop = asyncio.new_event_loop()
        try:
            updates = loop.run_until_complete(
                asyncio.wait_for(_check_async(), timeout=timeout_seconds),
            )
        finally:
            loop.close()
    except Exception as exc:  # noqa: BLE001 — defensive: never raise
        logger.debug("Store update check failed: %s", exc)
        return None

    if updates is None:
        return None

    # ``updates`` is an IVectorView; len() works in winrt's binding.
    try:
        count = len(updates)
    except TypeError:
        count = sum(1 for _ in updates)

    if count == 0:
        return None

    # ``mandatory`` is a bool on each StorePackageUpdate. Any one
    # mandatory update flips the whole prompt to mandatory wording.
    is_mandatory = False
    try:
        for u in updates:
            if bool(getattr(u, "mandatory", False)):
                is_mandatory = True
                break
    except Exception as exc:  # noqa: BLE001 — defensive: API surface drift
        logger.debug("Could not inspect store update mandatory flag: %s", exc)

    return UpdateInfo(package_count=count, is_mandatory=is_mandatory)


async def _check_async() -> Any:
    """Driver for the WinRT async API.

    Kept as a tiny coroutine so ``check_for_store_updates`` stays
    synchronous from the caller's view. ``StoreContext.get_default``
    is sync; the ``get_app_and_optional_store_package_updates_async``
    call returns an ``IAsyncOperation`` that the winrt binding
    converts to a Python awaitable.
    """
    if _StoreContext is None:
        return None
    context = _StoreContext.get_default()
    return await context.get_app_and_optional_store_package_updates_async()
