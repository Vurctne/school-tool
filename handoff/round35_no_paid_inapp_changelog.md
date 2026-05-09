# Round 35 — Remove paid-tier language + ship in-app changelog

**Date:** 2026-05-02

---

## User asks

1. "Do not indicate that we are intend to introduce paid version in
   future." — audit user-facing strings; remove or soften any text
   that implies an upcoming paid tier.
2. "include changelog in app" — add a "What's new" entry the user
   can click to read recent release notes inside the app.

---

## What changed (user-facing)

### 1. New "What's new" rail entry

The left rail's static-entries block now reads:

```
[ Instructions ] [ What's new ] [ Privacy Policy ]
```

Clicking "What's new" opens a scrollable modal that renders
`CHANGELOG.md` from the install root. Same rendering pattern as
"Privacy Policy" — same `_show_help_window` primitive, same
strip-leading-`# Heading` behaviour, same fallback if the file
isn't reachable.

### 2. CHANGELOG.md created at repo root

```
CHANGELOG.md   (new file — 86 lines)
```

Covers v2.2.2.0 (the upcoming hotfix) on top, then v2.2.1.0 (the
already-published broken version, listed as "this is the first
version where these features actually display correctly" because
of the Round 32 rendering bug), then a note that earlier versions
predate the Store launch. Tone is end-user-friendly — no jargon,
no internal round numbers, no mentions of pricing or paid tiers.

### 3. Paid-tier language removed from user-visible strings

| Where | Before | After |
| --- | --- | --- |
| `_CASES21_PO_HELP_TEXT` (Help button on the unlock screen) | "...recognised automatically and **unlocks your paid tools** within seconds." | "...recognised automatically." |
| same | "...licence status flip to Active and **your paid tools unlock right away**." | (removed — now just "School Tool validates it instantly.") |
| Unlock-screen banner (when a tool has `requires_feature` set) | "Get started with **School Tool Pro** in three steps: 1. Sign in · 2. Generate an annual invoice · 3. Upload your Purchase Order." | "This tool isn't available yet. Email feedback@schooltool.com.au if you'd like access." |
| Unlock-screen footer | "**Already paid?** Try 'Refresh licence' in User → Service." | (removed) |
| `docs/store_listing_copy.md` Pricing block | "**Free** (Round 15 launch)<br>**No in-app purchases** (paid tier resumes when you flip `requires_feature` back on the paid tools and re-add the User tab — that's a separate Store update later)" | "**Free**<br>**No in-app purchases**" |

The unlock screen as a whole only fires when a tool has
`requires_feature` set on it. **Currently every tool sets
`requires_feature = None`** (Round 15 free-tier launch), so the
unlock screen never shows in the published app. The wording changes
above are belt-and-braces in case a future change accidentally
flips a tool back to gated.

### 4. PyInstaller spec bundles the docs

```python
# packaging/SchoolTool.spec
_datas = [
    (os.path.join(_root, "resources"), "resources"),
    (os.path.join(_root, "assets", "brand"), os.path.join("assets", "brand")),
    # NEW: ship docs/ + CHANGELOG.md so the in-app modals find them
    (os.path.join(_root, "docs"), "docs"),
    (os.path.join(_root, "CHANGELOG.md"), "."),
]
```

`_show_changelog` reads `CHANGELOG.md` from the install root via the
same relative-walk pattern `_show_privacy_policy` already uses. Both
work in dev (running from repo root) and in the packaged MSIX build.

---

## Files touched

```
ADD   CHANGELOG.md
MOD   toolkit/shell.py
       - new _show_changelog method (mirrors _show_privacy_policy)
       - rail static_entries gains ("What's new", self._show_changelog)
       - _CASES21_PO_HELP_TEXT softened (no "paid tools" mentions)
       - unlock-screen banner softened ("not available yet" + email)
       - unlock-screen "Already paid?" footer removed
MOD   packaging/SchoolTool.spec
       - _datas bundles docs/ + CHANGELOG.md so the install root has
         them at runtime in the MSIX build
MOD   docs/store_listing_copy.md
       - Pricing block: removed "(Round 15 launch)" and the
         "(paid tier resumes when you flip requires_feature back on...)"
         note
```

No tests changed — `_show_changelog` follows the same I/O pattern as
`_show_privacy_policy` which already has coverage.

---

## What was deliberately left alone

* **`toolkit/licence.py`, `toolkit/api_client.py`, `toolkit/user_frame.py`** — full licence-and-account infrastructure stays in the codebase. It's unreachable today (`SHOW_USER_TAB = False`, every tool's `requires_feature = None`) but ripping it out is out of scope for "don't show paid wording to users". If you want it gone entirely, that's a separate cleanup round.
* **Internal docs** (`docs/01_REQUIREMENTS.md`, `docs/03_ROADMAP.md`, `docs/04_BACKEND_DESIGN.md`, `docs/06_PRICING.md`, `CLAUDE.md`, `PROJECT-INVENTORY.md`, etc.) — these describe the design intent of the project and reference pricing / licence concepts. They aren't shipped to end users. Left alone.
* **`backend/`** — Cloudflare Workers API surface includes licence routes. Same as above: not user-facing. Left alone.

If anything in those buckets should also change wording, say so —
half a round to do.

---

## Quality gates

```
ruff format --check .   → 79 files already formatted
ruff check .             → All checks passed!
mypy --strict --cache-dir=/tmp/mypy_cache toolkit/ tools/ tests/
                         → no issues found in 72 source files
pytest --ignore=tools/operating/tests/test_logic.py
                         → 550 passed, 66 skipped (env), 1 warning
```

---

## What to manually verify on Windows

1. Launch `python app.py` (or the built MSIX).
2. Look at the left rail static-entries section (below the "In
   development" group). Three entries should be visible:
   **Instructions**, **What's new**, **Privacy Policy**.
3. Click **What's new** — a modal opens with the CHANGELOG content,
   v2.2.2.0 at the top, scrollable.
4. Click **Privacy Policy** — same modal style, privacy text loads.
5. The status bar at the bottom of the window still shows
   `v2.2.2.0 · feedback@schooltool.com.au`.
6. None of the tools fire the unlock screen during normal use, so
   the softened gate wording isn't visible in regular operation —
   that's correct.

---

## Suggested release-notes update

If you've already drafted patch notes for the v2.2.2.0 hotfix
submission, add this line to the "smaller changes" section:

> * **What's new in-app.** A new "What's new" entry in the left
>   rail opens this changelog inside the app, so you don't have to
>   leave the window to see what changed.

---

## Round 35 files committed-side

```
ADD   handoff/round35_no_paid_inapp_changelog.md
ADD   CHANGELOG.md
MOD   toolkit/shell.py
MOD   packaging/SchoolTool.spec
MOD   docs/store_listing_copy.md
```
