# Round 51 Phase D — Structured commentary

**Date:** 2026-05-10
**Trigger:** User: "Phase D — structured commentary (move #5 from the
brief)" — the last of six moves in the original Round 44
Sub-Program redesign brief.
**Honest delivery:** Phase D shipped end-to-end with two rounds of
multi-personality testing, eight Round-1 fixes applied, and two
Round-2 fixes applied. Move #5 closes the original 6-move
redesign brief — all six are now done.

---

## What shipped

### `SubProgramLine` schema change

```python
@dataclass(frozen=True)
class SubProgramLine:
    ...
    commentary: str = ""             # ← FREEFORM NOTES only (was: everything)
    commentary_driver: str = ""      # NEW — _DRIVER_VALUES tuple member
    commentary_outlook: str = ""     # NEW — _OUTLOOK_VALUES tuple member
    commentary_action: str = ""      # NEW — _ACTION_VALUES tuple member
```

Three module-scope tuples are the single source of truth for the
inline editor's Comboboxes, the XLSX prefix encoder, and the tests:

| Tuple | Values |
|---|---|
| `_DRIVER_VALUES` | One-time, Ongoing, Structural, Timing-early, Timing-late, Investigating |
| `_OUTLOOK_VALUES` | One-time, Expected to continue, Improving, Deteriorating |
| `_ACTION_VALUES` | None, Monitor, Investigate, Update forecast |

The user explicitly chose `Timing-early` / `Timing-late` (hyphenated)
over the brief's `Timing (early)` / `Timing (late)` (parens) at the
start of the round via `AskUserQuestion`. That choice is locked in
the tuples; the Round-1 UX critic flagged it ("reads as software
output") but the values are user-confirmed and not relitigated.

### XLSX encoding contract

The Comments cell (column 12) carries an optional structured prefix
encoded as:

```
[Driver: Ongoing | Outlook: Expected to continue | Action: Monitor]
Reviewed by council
```

(Prefix on first line, notes on second — newline separator added in
Round-1 fix #8 for cleaner wrap-text rendering.)

Encoder rules:

- All four blank → empty cell (matches pre-Phase-D shape)
- Notes only (no dropdowns) → plain text, no prefix
- Notes only AND notes start with `[` → empty-body escape `[]\nnotes`
  so the decoder can distinguish from a structured prefix
- Any structured field set → `[Field1: V | Field2: V]\nnotes`
  (blank fields are omitted from the prefix entirely)

Decoder is symmetric — accepts both space and newline separators
(forward-compat with pre-Round-1 encoded cells).

### Inline editor flow

`_open_inline_comment_editor` now packs three `ttk.Combobox(state="readonly")`
widgets above the existing `tk.Text` Notes widget:

```
┌─[ Comment - 4400 Mathematics (Revenue) ]──────────┐
│ Driver:    [Combobox          v]                  │
│ Outlook:   [Combobox          v]                  │
│ Action:    [Combobox          v]                  │
│                                                   │
│ Notes:                                            │
│ ┌───────────────────────────────────────────────┐ │
│ │                                               │ │
│ │                                               │ │
│ └───────────────────────────────────────────────┘ │
│                                                   │
│                            [Cancel]   [Save]      │
└───────────────────────────────────────────────────┘
```

Each Combobox includes `""` as the first dropdown value so users can
clear a previously-set field. Window sized 560×360 (was 520×240).
Default focus is on Notes (median user wants to type a note); Tab
binding on Notes advances focus to Save (Round-2 fix).

### In-app sub-row display

The speech-bubble row beside each commented line shows the most
action-relevant tag inline (per the user's confirmed answer):

| State | Display |
|---|---|
| Action set, notes set | `   💬  [Action: Investigate] notes paragraph` |
| Action set, no notes | `   💬  [Action: Investigate]` |
| No Action, Driver set | `   💬  [Driver: Ongoing]` ← Round-1 fallback |
| No Action / Driver, Outlook set | `   💬  [Outlook: Improving]` ← Round-1 fallback |
| Action `""`, only notes | `   💬  notes paragraph` |
| Action `"None"` (literal) | `   💬  [Action: None] notes` ← distinct from blank |
| All four blank | (no sub-row) |

The Round-1 fallback chain (Action > Driver > Outlook) ensures the
speech bubble is never empty when *any* categorisation exists.

### `_commentary_overrides` type change

```python
# Pre-Phase-D
_commentary_overrides: dict[str, str] | None  # raw commentary text

# Post-Phase-D (Round 51)
_commentary_overrides: dict[str, tuple[str, str, str, str]] | None
#                                       (notes, driver, outlook, action)
```

Tests in `tests/test_shell_clear.py` and
`tools/sub_program/tests/test_frame.py` updated to the new shape.

### Prior-period round-trip

`load_prior_period_comments` is unchanged in signature — still
returns `dict[tuple[str, str], str]` of raw cell values. The
caller (`generate_report`) now calls `decode_commentary` on each
value to populate the four fields on the resulting `SubProgramLine`.

A pre-Phase-D file with freeform commentary (no prefix) decodes
to Notes-only with the three dropdowns blank — graceful migration.

---

## Multi-personality testing

### Round 1: 3 lenses in parallel (logic, UX, Excel QA)

Each agent returned 6–10 findings. **8 Round-1 fixes applied:**

1. **[Excel P0] Formula injection guard.** A user typing `=SUM(...)`
   into Notes would otherwise become a live Excel formula.
   `_write_monthly_sub_program_sheet` now prepends `'` (Excel's
   "force text" sigil) when the encoded cell starts with
   `=` / `+` / `-` / `@`. `load_prior_period_comments` strips it
   on read so the round-trip doesn't accumulate apostrophes.
2. **[Logic P0] Atomic per-sub-program aggregation.** The writer's
   pre-fix design picked Notes / Driver / Outlook / Action
   independently across the Account-rows of a sub-program — which
   could fabricate a `[Action: Investigate]\nnotes from a different
   row` combination that existed on no actual line. Replaced four
   independent dicts with one `commentary_tuple: dict[str, tuple[…]]`
   so the FIRST row contributing any commentary owns all four
   fields atomically.
3. **[Logic P0] Whitespace preservation in `decode_commentary`.**
   Pre-fix the decoder did `text.strip()` and `rest.strip()`,
   destroying user's leading/trailing whitespace. encode→decode→encode
   is now idempotent — only the prefix-adjacent separator is
   stripped.
4. **[Logic P0] Unknown-value validation.** Pre-Phase-D users whose
   freeform text happened to contain `[Driver: foo]` would have it
   silently parsed as structured. Round-1 added validation against
   the canonical tuples, treating the whole cell as Notes if any
   value was unknown. **(Later relaxed in Round 2 — see below.)**
5. **[Logic P1] Stale `over_budget_lines` after merge.**
   `_merge_commentary_overrides` rebuilt `summary.lines` but left
   `summary.over_budget_lines` pointing at pre-merge instances.
   Now re-derives the subset.
6. **[UX P1] Inline display fallback chain.** When user set only
   Driver=Ongoing (no Action, no Notes), the row showed
   `   💬  ` (empty bubble). The fallback now shows the first set
   structured tag — Action > Driver > Outlook — so the bubble is
   never blank when something is categorised.
7. **[Logic P1] Combobox preserves unknown values.** Pre-fix
   `cb.set(initial if initial in values else "")` silently zeroed
   any out-of-band value (older tool version, hand-edited XLSX,
   schema drift). Combobox now extends `value_list` with the
   unknown value once for the editor session so the user can keep
   it OR re-pick a canonical one.
8. **[Excel P1] Newline separator between prefix and notes.**
   Was `[…] notes`, now `[…]\nnotes`. With `wrap_text=True` on the
   Excel cell, notes start on their own visual line instead of
   running into a wrapped prefix mid-paragraph.

**Deferred from Round 1** (documented for future rounds):

- **[UX]** Dropdown wording — "Structural" too jargon-y; "Timing-early"
  reads as software output; duplicate "One-time" in Driver and
  Outlook. **Reason:** values are user-confirmed via AskUserQuestion;
  changing them needs a new design call. Worth revisiting if a real
  school user feedback comes in.
- **[Excel P1]** Row height auto-fit. Tall encoded cells may clip on
  printed pages (default 15pt height, no `row_dimensions` set).
  Cosmetic only — wrap_text still works in Excel display, just
  print clipping. Worth fixing in a follow-up that tightens the
  whole Round 47 print-page-setup story.
- **[Logic P2]** Pipe character in any field value would be unescaped
  by the encoder. The frozen tuples have no pipes, so the only path
  is hand-editing the XLSX. Not worth complicating the encoder.

### Round 2: 2 lenses (logic, UX) for verification

**1 P1 fix** found a regression introduced by Round-1 fix #4
colliding with #7:

9. **[Logic P1] Round-trip data loss for unknown Combobox-preserved
   values.** Round-1 fix #7 preserved unknown values in the editor;
   fix #4 stripped them in the decoder. A user who saved an
   editor with "FooBar" Driver would lose it on the next XLSX read.
   **Fix:** relaxed the decoder validation. Unknown values are now
   preserved verbatim in the returned tuple. The editor's Combobox
   is the single point of truth for what's canonical — a user
   opening such a row sees the legacy value AND can re-pick. The
   pre-Phase-D safety case (`[Driver: foo]` literal text in
   freeform notes) is empirically very rare; the round-trip
   preservation case (hand-edited XLSXes, schema drift) is more
   common.

**1 UX P1** Tab-key keyboard accessibility:

10. **[UX P1] Tab in Notes Text widget inserts whitespace, blocks
    keyboard reach to Save.** Bound `<Tab>` on the Notes Text widget
    to call `tk_focusNext().focus()` and `return "break"` so
    keyboard users reach Save without typing literal tabs into the
    note.

**Round 2 confirmed PASS:** 7 of the 8 Round-1 fixes hold. Atomic
aggregation, apostrophe round-trip, inline-display fallback,
`over_budget_lines` re-derivation, idempotent encode→decode all
verified. Only fix #4 + #7 collision needed remediation.

---

## Files touched

| File | Change |
|---|---|
| `tools/sub_program/logic.py` | New `_DRIVER_VALUES` / `_OUTLOOK_VALUES` / `_ACTION_VALUES` tuples + `_COMMENTARY_PREFIX_RE` / `_PREFIX_FIELD_RE` regexes + `encode_commentary` / `decode_commentary` helpers (~120 lines). 3 new fields on `SubProgramLine`. `_write_monthly_sub_program_sheet` rewritten to use atomic aggregation + apostrophe-guarded cell-write + `\n` separator + `number_format="@"`. `_write_sheet` (legacy revenue/expense) updated to encode. `load_prior_period_comments` strips formula-guard apostrophe. `generate_report` uses `dataclasses.replace` instead of full SubProgramLine reconstruction (decode_commentary inline). |
| `tools/sub_program/frame.py` | `_commentary_overrides` typed as `dict[str, tuple[str, str, str, str]] \| None`. `_open_inline_comment_editor` rewritten with three `ttk.Combobox(state="readonly")` widgets above the Text widget; Combobox preserves unknown initial values; Tab on Notes advances focus. `_merge_commentary_overrides` applies 4-tuple via `replace` and re-derives `over_budget_lines`. `_build_result` sub-row description includes the inline tag with Action > Driver > Outlook fallback. New imports for `_ACTION_VALUES` / `_DRIVER_VALUES` / `_OUTLOOK_VALUES` / `SubProgramLine`. |
| `tools/sub_program/tests/test_logic.py` | New `TestStructuredCommentary`, `TestStructuredCommentaryPriorPeriodMigration`, `TestStructuredCommentaryXlsxOutput`, `TestStructuredCommentaryRound1Fixes` test classes (~20 tests covering encode/decode round-trip, value-tuple shape, prefix encoding, formula guard, atomic aggregation, apostrophe round-trip, idempotent whitespace, unknown-value preservation, separator tolerance). |
| `tools/sub_program/tests/test_frame.py` | New `TestStructuredCommentaryInlineDisplay`, `TestStructuredCommentaryOverrideMerge` test classes (~10 tests — inline tag rendering, fallback chain, Action priority, `over_budget_lines` refresh). Existing `_line_with_commentary` helper extended to accept driver/outlook/action kwargs. `_commentary_overrides = {"4001": "A note"}` updated to 4-tuple shape. |
| `tests/test_shell_clear.py` | `_commentary_overrides = {"4001": ("Some note", "", "", "")}` 4-tuple shape. |
| `app_metadata.py` | `APP_VERSION` 2.2.9.0 → 2.3.0.0 (schema change is meaningful enough for a minor bump). |
| `CHANGELOG.md` | New v2.3.0.0 section. |

---

## Quality gates

```
ruff format --check .                       # 79/79 ok
ruff check .                                # All checks passed!
mypy --strict --cache-dir=/tmp/mypy_cache tools/sub_program/
                                            # 0 new errors (2 pre-existing
                                            # in tools/master_budget/logic.py
                                            # — unused-ignore comments,
                                            # unrelated to Phase D)
pytest tools/sub_program/tests/             # 149 passed, 9 failed (env-only:
                                            # missing Samples/ PDF fixture),
                                            # 15 errors (same env)
```

The 9 failures and 15 errors all share the same root cause: the
`Samples/Annual Subprogram Budget Report/GL21157_Annual Subprogram
budget report.pdf` fixture isn't in this worktree. They are
unchanged from `origin/main` baseline — verified via `git stash`
+ run + restore.

---

## Phase D completion status (vs original 6-move brief)

| Move | Status |
|---|---|
| #1 Variance + Pacing columns | ✅ Round 45 (Phase A) |
| #2 Watchlist tab | ✅ Round 46 (Phase B) |
| #3 Bridge waterfall | ✅ Round 50 (Phase C) |
| #4 Dollar materiality | ✅ Round 45 (Phase A) |
| **#5 Structured commentary** | ✅ **Round 51 (Phase D)** |
| #6 Faculty rail by contribution | ✅ Round 46 (Phase B) |

**All six moves done.** The original Round 44 redesign brief is
closed.

---

## Carried over (still pending)

From the Round 47 audit (deferred):
- Revenue under-collection signal (Phase B.2)
- Pacing direction inversion for Revenue (Phase B.2)
- Faculty rail bar tone for contribution-pct values (Phase B.2)
- Variance + Pacing columns in XLSX (decision needed)
- Conditional formatting / data bars on monthly XLSX sheet
- School-name extraction for print header
- ~25 P0 tests proposed by Round 47 Agent D

From Round 50 (Bridge follow-ups, deferred):
- Bar-scale dwarfing (anchor bars saturate while drivers collapse)
- Anchor `amount` cell empty-string vs em-dash
- Fold cut at 6 vs brief's 8 ceiling
- 12 lower-priority Bridge findings

From Round 51 itself (this round, deferred):
- **[UX]** Dropdown wording revision — "Structural", "Timing-early"
  hyphenation, duplicate "One-time" in Driver+Outlook. User-confirmed
  values, requires a new design call.
- **[Excel P1]** Row height auto-fit for tall encoded cells (cosmetic
  print-clipping risk).
- **[Logic P2]** Pipe character escape in field values (frozen tuples
  have no pipes, so this only affects hand-edited XLSXes).
- **[UX P2]** "[Action: None]" inline display reads ambiguously vs
  "[Action: not set]" — user-confirmed wording, deferred.
- **[UX P2]** No discoverability cue (banner / "(new)" label) for
  Round-50 → Round-51 returning users encountering the new editor.

---

## Sandbox / git note

Working in worktree `claude/admiring-feynman-a1c366` rebased to
`origin/main` HEAD `6cddf59` at the start of the round. **All Phase D
changes are still in the working tree — not yet committed.** Per
the user's standing rule (never auto-suggest commit commands in
Cowork mode), the user controls commit timing.

The cross-FS truncation gotcha did not bite this round — surgical
Edits handled all changes without recovery cycles.

---

## Status

- 6 of 6 redesign-brief moves complete.
- 2.3.0.0 ready for `pwsh msix\build_msix_package.ps1 -StoreUpload`
  on Windows.
- Round 1 (3-lens) + Round 2 (2-lens) multi-personality testing
  complete. 10 fixes applied, 9 deferred items documented.
- Phase D — Move #5 — closes the Round 44 redesign brief. The next
  natural batch is the Phase B.2 deferrals (Revenue under-collection
  signal + faculty rail bar tone) plus the Round 47 P0 test list.

— end of round —
