# Round 44 — Bump version to 2.2.3.0 + changelog entry

**Date:** 2026-05-09
**Trigger:** User: "下一个store版本应该是2.2.3.0了" (next Store version
should be 2.2.3.0)
**Scope:** Version bump only — Round 43's UI polish is the actual
content of the v2.2.3.0 release.

---

## Why a new build

Round 43 landed four changes that ship together as the next Store
update. None of them changed `APP_VERSION` at the time, because the
version bump is a single coordinated step done at the moment we're
ready to push to the Store. That moment is now.

The changes folded into v2.2.3.0:

1. **Tool frame shadow removed** (`toolkit/shell.py` — `borderwidth=0,
   highlightthickness=0` on the right-side input frame).
2. **Window resize debounce** (`toolkit/shell.py` —
   `_latest_drag_width` per-canvas holder coalesces drag redraws so
   only the latest size triggers the expensive table-rebuild step).
3. **Status bar simplified** (`toolkit/shell.py` — bottom-right
   shows only `v{APP_VERSION}` now; the support email used to live
   there too, but the new Contact window from Round 42 makes that
   duplicate redundant).
4. **In-development rail refresh** (`toolkit/registry.py` — swapped
   "Operating Statement" for "Fortnightly Salary Comparison" in
   `IN_DEVELOPMENT_TOOLS`).

---

## Files touched this round

| File | Change |
| --- | --- |
| `app_metadata.py` line 10 | `APP_VERSION = "2.2.2.0"` → `"2.2.3.0"` |
| `CHANGELOG.md` | New `## v2.2.3.0 — May 2026` section above the v2.2.2.0 entry, listing the four Round 43 polish items in user-facing language |

Nothing else changed. The four Round 43 code edits are already on
disk from the previous round's work.

---

## Quality gates

```
ruff format --check .   # 79 files already formatted
ruff check .            # All checks passed!
mypy --strict ...       # Success: no issues found in 79 source files
pytest -q --ignore=tools/operating/tests
                        # 507 passed, 66 skipped (env-only), 2 warnings
```

Caveat — there are 9 pre-existing failures in `tools/operating/tests/`
caused by a stale sample-fixture filename (`Samples/Operating
Statement/GL21150_Operating Statement Detailed.pdf` — actual files
are `... Detailed Feb.pdf` and `... Detailed Mar.pdf`). Operating
Statement is parked under "In development" per
`toolkit/registry.py` lines 71-73 (its import + register call are
commented out), so this doesn't ship and doesn't block the build.
Tracked as a follow-up under Round 39 audit findings.

---

## What Ivan does next on Windows

```pwsh
# 1. Build the MSIX hotfix
pwsh msix\build_msix_package.ps1 -StoreUpload

# scripts\bump_version.py will run as part of the script. Note:
# APP_VERSION is already at 2.2.3.0, so the auto-bump will roll the
# BUILD field to 2.2.3.1 unless `-NoVersionBump` is passed.
# That's normal — the Store sees the manifest version, and we want
# fresh build metadata anyway.

# 2. Submit through Partner Center as usual.
```

If you want to lock the manifest at exactly 2.2.3.0 (no BUILD
auto-bump), pass `-NoVersionBump` to the build script.

---

## Status board entries created/updated

- `handoff/round44_version_bump_2_2_3_0.md` (this file)
- Task #62 → completed (after this write)

---

## Addendum — Kate Marshall credit

Mid-round Ivan added: "New sub-program budget report layout is
contributed by Kate Marshall." This is the field contributor whose
template ("Monthly Sub Program Report April 2026 KMAR.xls") became
the new XLSX shape rolled out in Round 38 and shipping in this
version — the "KMAR" suffix on the sample filename is her initials.

Action taken:
- Added a new bullet at the top of the v2.2.3.0 changelog entry
  that calls out the Sub-Program monthly layout change and credits
  Kate Marshall by name.
- Saved a project memory
  (`project_kate_marshall_subprogram_layout.md`) so future
  conversations remember this attribution and surface her name if
  Ivan asks for a contributors page, social post, or in-app
  credits.

The Round 38 layout work itself was already done — the bullet just
documents it for the user-facing changelog. No code change.

---

## Carried over (still pending)

- **Operating Statement test fixtures** — rename or symlink
  `... Detailed.pdf` → one of the existing month-suffixed PDFs; or
  refactor tests to glob the actual filenames. Out of scope for
  v2.2.3.0 since Operating Statement isn't in the registry.
- **`SUPPORT_EMAIL = "feedback@..."`** is correct; **`CONTACT_EMAIL =
  "contact@..."`** is wired. Partner Center "Support contact info"
  field still needs the `contact@schooltool.com.au` update on
  submission.
