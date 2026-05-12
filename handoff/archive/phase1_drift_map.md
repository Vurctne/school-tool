# Phase 1 Handoff — Highlight-Colour Drift Map

**Date:** 2026-04-25
**Orchestrator:** Opus 4.7 (Lead)
**Agents dispatched:** A (token-source), B (instruction-text), C (export-fill), D (tests) — all Sonnet 4.6, read-only, in parallel.

---

## Headline

There is **no numerical disagreement** between `toolkit/tokens.py`, the design-system CSS, the instruction text, or the exported xlsx fills. All hex values found in the codebase agree with the three canonical `HL_*` constants.

The drift is **structural**: most hex values are hard-coded string literals rather than interpolations of `HL_*` constants. The codebase therefore *happens to* be consistent today, but nothing enforces it — any future edit to `toolkit/tokens.py` would silently drift the instruction text and the xlsx fills without failing any existing test.

---

## Canonical values (confirmed)

| Constant | Hex | Role | CSS custom property |
| --- | --- | --- | --- |
| `HL_EDITED` | `FFF2CC` | yellow — user-edited cell | `--hl-edited` |
| `HL_MISMATCH` | `F4CCCC` | pink/red — over-budget / mismatch | `--hl-mismatch` |
| `HL_SOURCE_ONLY` | `E2F0D9` | green — source-only row | `--hl-source-only` |

openpyxl fills apply these via `"FF" + HL_*` (ARGB alpha prefix).

---

## Drift map by layer

### Token source — clean
`toolkit/tokens.py` and `colors_and_type.css` agree exactly on all three values.

### Instruction text — 5 hard-coded hex literals in user-facing strings

| File | Line | Hex | Role |
| --- | --- | --- | --- |
| `tools/sub_program/frame.py` | 44 | `#F4CCCC` | HL_MISMATCH |
| `tools/sub_program/frame.py` | 72 | `#F4CCCC` | HL_MISMATCH |
| `tools/master_budget/frame.py` | 47 | `#F4CCCC` | HL_MISMATCH |
| `tools/master_budget/frame.py` | 52 | `#E2F0D9` | HL_SOURCE_ONLY |
| `tools/master_budget/frame.py` | 58 | `#FFF2CC` | HL_EDITED |

All values correct today; none of them are interpolated from `HL_*`.

### Export fills — 9 construction sites

| File | Line | Source | Canonical token |
| --- | --- | --- | --- |
| `tools/sub_program/logic.py` | 506 | `"FF" + HL_MISMATCH` (correct pattern) | HL_MISMATCH |
| `tools/master_budget/logic.py` | 68 | hard-coded `"FFF4CCCC"` | HL_MISMATCH |
| `tools/master_budget/logic.py` | 69 | hard-coded `"FFE2F0D9"` | HL_SOURCE_ONLY |
| `tools/master_budget/logic.py` | 1428 | Win32 BGR int `13421812` | HL_MISMATCH |
| `tools/master_budget/logic.py` | 1435 | Win32 BGR int `13421812` | HL_MISMATCH |
| `tools/master_budget/logic.py` | 1442 | Win32 BGR int `14282978` | HL_SOURCE_ONLY |
| `tools/master_budget/logic.py` | 1449 | Win32 BGR int `14282978` | HL_SOURCE_ONLY |
| `tools/master_budget/logic.py` | 1468 | Win32 BGR int `14282978` | HL_SOURCE_ONLY |
| `tools/master_budget/logic.py` | 1476 | Win32 BGR int `14282978` | HL_SOURCE_ONLY |

Only 1 of 9 sites derives from the token source. `master_budget/logic.py` already imports all three `HL_*` with a `# noqa: F401` marker, suggesting the imports were placed but the refactor was never completed.

### Tests — no assertion constrains instruction text or fills to `HL_*`

- `tests/test_tokens_drift.py` only verifies CSS↔Python parity; does not pin absolute values.
- `tools/sub_program/tests/test_frame.py` uses bare literal `"F4CCCC"` — wouldn't catch token rename.
- `tools/sub_program/tests/test_logic.py` only asserts `HL_MISMATCH` on one cell; `HL_EDITED` and `HL_SOURCE_ONLY` are unguarded.
- No test scans instruction text for stray hex.
- `test_over_budget_fill_present` silently skips when the sample PDF contains no over-budget lines.

---

## Findings that require a user decision

1. **Scope extension beyond `tools/sub_program/`.** The plan permits touching other tools only if Phase 1 surfaces drift. It has — heavily, in `tools/master_budget/`. Proceed or scope-limit?
2. **`HL_EDITED` is a ghost constant.** Defined and referenced in instruction text, but no fill site applies it. Retain / annotate / investigate?
3. **Alpha-prefix helper.** Introduce `toolkit.tokens.argb(HL_*)` to eliminate `"FF" + HL_*` sprinkling, or keep the current inline pattern?

---

## Suggested new tests (D's proposal, unimplemented)

1. `test_canonical_token_values` — pin absolute hex in `test_tokens_drift.py`.
2. `test_hl_edited_fill_present` + `test_hl_source_only_fill_present` — cover the two untested colours.
3. Refactor `test_over_budget_fill_present` to import `HL_MISMATCH` instead of hard-coding.
4. `test_over_budget_fill_all_columns` — scan every column, not just column 1.
5. `test_no_rogue_hex_in_instruction_text` — xlsx-wide hex scan.
6. Replace `pytest.skip` with a hard assertion on over-budget sample coverage.

---

## Next step

Waiting on user decisions on scope (1), ghost constant (2), alpha helper (3) before dispatching Phase 2 agents E, F, G.
