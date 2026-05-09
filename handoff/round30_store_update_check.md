# Round 30 — Microsoft Store update check on startup

**Date:** 2026-05-02
**Scope:** When the app launches, ask the Microsoft Store whether any
package updates are pending. If yes, show a modal dialog offering to
open the Store. If no / offline / non-Windows / non-MSIX install, do
nothing (silent fail).

---

## User ask

> set it to check updates when opening; show a notice to update if it
> is not the latest version

Decisions captured up-front:

| Q | Choice |
| --- | --- |
| Update source | **Microsoft Store native check** (no GitHub / no backend / no static JSON) |
| Notice UX | **Modal dialog at startup** (askyesno) |
| Network behavior | **Once at startup, fail silently if offline** |

The Microsoft Store choice means the check piggybacks on the OS-level
update mechanism the Store app already uses — no extra backend, no
custom telemetry, and the user's privacy posture (free tools fully
offline, no calls to *our* infrastructure) is preserved. The Store
client itself is the only thing making network calls.

---

## How it works

1. **At app startup**, after `TkShell` is mounted, `app.main()` calls
   `_schedule_update_check(root)` which spawns a daemon thread.
2. The thread calls `toolkit.updates.check_for_store_updates()`,
   which:
   - Checks `HAVE_STORE_API` (the guarded `winrt` import). If False
     → returns `None` immediately.
   - Otherwise creates a short-lived asyncio loop, calls
     `StoreContext.get_default()
       .get_app_and_optional_store_package_updates_async()` with a
     5-second timeout.
   - On any exception (including timeout, network failure, missing
     Store identity) — logs at DEBUG level and returns `None`.
   - Returns `UpdateInfo(package_count, is_mandatory)` when one or
     more updates are pending.
3. If `info` is `None`, the worker exits silently — no UI changes.
4. If `info` is non-None, the worker schedules
   `_show_update_dialog(root, info)` onto the Tk main loop via
   `root.after(0, …)`.
5. The dialog shows:
   ```
   Update available

   A new version of School Tool is available in the Microsoft Store.
   You're on v2.1.1.0.

   Updates ship bug fixes and new features — installing is recommended.
   (or: This is a required update — please install it as soon as you can.)

   Open the Microsoft Store now?
   ```
   with **Yes** / **No** buttons.
6. **Yes** → `webbrowser.open("ms-windows-store://search/?query=Vurctne.VicSchoolFinanceTools")`
   opens the Store on our app's listing.
7. **No** → dialog dismisses; the user can run the same check next
   time they launch the app. Pending update remains pending.

---

## Why these choices

- **Modal at startup** instead of status-bar notice: the user
  explicitly chose this. It guarantees the prompt is seen at least
  once. If they hit No, no further nag — they'll see it again on
  next launch.
- **Microsoft Store native** instead of GitHub releases / static
  JSON: zero extra backend, no version-comparison logic to write
  (the OS does it), works automatically when the app is updated on
  the Store, and the call goes via `Windows.Services.Store` — a
  Microsoft-controlled OS API, not a third party.
- **Worker thread**: the WinRT call is async and may take a couple of
  seconds. Running it on the main thread would freeze the window
  during launch.
- **Silent failure**: the user explicitly chose this. Sideloaded /
  dev installs and offline machines see *nothing* — no banner, no
  log noise, no error dialog. The app behaves as if the check didn't
  happen.

---

## Files touched

```
ADD   toolkit/updates.py
       - UpdateInfo dataclass (frozen)
       - HAVE_STORE_API + guarded winrt import
       - check_for_store_updates(timeout_seconds=5.0) -> UpdateInfo | None
       - _check_async(): the WinRT IAsyncOperation driver

MOD   app.py
       - new imports: logging, threading, messagebox, webbrowser,
         APP_VERSION, STORE_PACKAGE_IDENTITY_NAME, UpdateInfo,
         check_for_store_updates
       - main() schedules _schedule_update_check(root) after shell
         is packed and before root.mainloop()
       - _schedule_update_check: daemon thread → root.after(0, dialog)
       - _show_update_dialog: messagebox.askyesno; mandatory wording
         when applicable
       - _open_store_listing: ms-windows-store:// search URI

ADD   tests/test_updates.py
       - 7 tests covering the silent-fail paths + happy path:
         test_returns_none_when_api_unavailable
         test_returns_none_when_storecontext_raises
         test_returns_none_when_no_updates_pending
         test_returns_update_info_when_updates_pending
         test_mandatory_flag_propagates_when_any_update_is_mandatory
         test_returns_none_on_timeout
         test_update_info_dataclass_is_frozen

MOD   pyproject.toml
       - new Windows-only deps: winrt-runtime, winrt-Windows.Services.Store,
         winrt-Windows.Foundation, winrt-Windows.Foundation.Collections
         (all guarded by ``; platform_system == 'Windows'``)
```

---

## Quality gates

```
ruff format --check .   → 79 files already formatted
ruff check .             → All checks passed!
mypy --strict --cache-dir=/tmp/mypy_cache toolkit/ tools/ tests/
                         → no issues found in 72 source files (+2)
pytest --ignore=tools/operating/tests/test_logic.py
                         → 550 passed, 66 skipped (env)
                           (was 543 — +7 from test_updates)
```

---

## What to manually verify on Windows

The MSIX bundle MUST be installed from the Store (or sideloaded with
a Store-issued identity) for the Store API to return real updates.
Sideloaded dev builds will see no updates — that's correct, expected
silent-fail behavior.

### Once the app is on the Store

1. Publish a new MSIX version to the Store.
2. On a Store-installed machine still on the old version, launch the
   app.
3. Within ~2 seconds of the window appearing, the dialog should pop:
   *"Update available — A new version of School Tool is available in
   the Microsoft Store. You're on v2.1.1.0. Open the Microsoft Store
   now?"*
4. Click **Yes** → Microsoft Store opens, our app's listing is shown.
5. Click **No** → dialog dismisses; app proceeds normally. Relaunch
   later and the dialog should appear again until the update is
   installed.

### Pre-Store / sideloaded smoke test

1. Run `pip install -e .[dev]` then `python app.py` in a dev shell.
2. App launches, status bar shows the version, **no dialog appears**.
3. Logs should show DEBUG-level "Store update check failed: …" or
   nothing at all (depending on whether `winrt` is installed). No
   ERROR-level lines.

### Network-down test

1. Disconnect from the internet.
2. Launch the app.
3. Same as above — no dialog, no error. The check times out at
   5 seconds and returns None silently.

---

## Notes for future rounds

* **MSIX manifest**: the MSIX must declare the
  `runFullTrust` capability to call WinRT APIs. The package
  identity in `app_metadata.STORE_PACKAGE_IDENTITY_NAME` already
  exists; just make sure the `<Capabilities>` block in
  `msix/AppxManifest.xml` includes `<rescap:Capability
  Name="runFullTrust" />` (it should from Round 16).
* **Bundling winrt for PyInstaller / MSIX**: the `winrt-*` packages
  are pure Python wrappers around OS-level COM objects, so they're
  small and bundle cleanly with PyInstaller. No extra hooks needed.
* **Behaviour when user clicks No repeatedly**: by design, the
  prompt re-appears every launch. This is the user's chosen UX. If
  they later want a "Don't show again" / "Remind me tomorrow" option,
  add a tiny preferences file at
  `%LOCALAPPDATA%\Packages\<MSIX>\LocalCache\update_prefs.json` and
  honour `dismissed_until: <ISO8601>`.
* **In-place install instead of opening Store**: the API supports
  `request_download_and_install_store_package_updates_async()` for
  in-place install. We chose to deep-link to the Store page instead
  to give the user explicit consent to download — no surprise
  installs. If you switch later, surface a progress bar in the shell
  status area; downloads can be 100+ MB.
