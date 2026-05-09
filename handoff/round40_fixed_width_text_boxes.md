# Round 40 — Fixed-width text boxes

**Date:** 2026-05-08

User ask: "Change all text boxes to appropriate fixed width." All
input fields previously stretched to fill the entire panel width.
Now each field has a sensible fixed default width baked in, with a
`width=` override available per-tool.

---

## What changed

### Default widths per field type

| Field | Default `width=` (chars) | Why |
| --- | --- | --- |
| `TextField` (`TextInput`) | 32 | Generic text — fits typical labels (school code, period name, etc.) without dominating the panel |
| `NumberField` (`NumberInput`) | 12 | Fits `999,999.99` with breathing room |
| `CurrencyField` (`CurrencyInput`) | 14 | Fits `9,999,999.99` (the `$` prefix is a separate sibling label, not part of the entry) |
| `DateField` (`DateInput`) | 12 | `DD/MM/YYYY` is 10 chars; +2 for the calendar chevron |
| `SecretField` (`SecretInput`) | 20 | Generic secret — most schools' SINs are 4–6 digits but the primitive is general-purpose |

### Per-tool overrides

* **HYIA SIN field** — `width=8` (the SIN regex is `\d{4,6}`, so 8 chars is plenty and visually communicates "this is a short field").

Other tools' `TextInput`/`NumberInput`/`CurrencyInput`/`DateInput`/`SecretInput` declarations don't specify a width, so they inherit the new defaults above.

### Layout change

The Entry widgets now pack with `anchor="w"` instead of `fill="x"` —
they sit on the left edge of the input row at their declared width
rather than stretching across the full panel. The label above each
entry still spans full panel width (so the input row aligns left).

---

## Files touched

```
MOD   toolkit/primitives.py
       - TextField.__init__: new ``width`` param (default 32);
         entry packs with anchor="w" instead of fill="x"
       - NumberField.__init__: new ``width`` param (default 12)
       - CurrencyField.__init__: new ``width`` param (default 14);
         row+entry pack with anchor/no-fill
       - DateField.__init__: new ``width`` param (default 12);
         calendar dropdown + fallback Entry both honour it
       - SecretField.__init__: new ``width`` param (default 20);
         entry+eye-toggle row stays compact

MOD   toolkit/base_tool.py
       - TextInput / NumberInput / CurrencyInput / DateInput /
         SecretInput each gain a ``width: int = <sensible default>``
         field so per-tool overrides are declarative.

MOD   toolkit/shell.py
       - _build_input_widget threads ``inp.width`` through to the
         primitive constructor for all five field types.

MOD   tools/hyia/frame.py
       - SIN SecretInput: ``width=8`` (4-6 digit SIN)

MOD   tools/operating/tests/test_frame.py
       - noqa on the placeholder ``import tools.operating`` (F401
         was previously suppressed by ruff cache; surfaced this round).
```

---

## Quality gates

```
ruff format --check .   → 79 files already formatted
ruff check .             → All checks passed!
mypy --strict --cache-dir=/tmp/mypy_cache toolkit/ tools/ tests/
                         → no issues found in 72 source files
pytest --ignore=tools/operating/tests/test_logic.py
                         → 544 passed, 66 skipped (env), 1 warning
```

---

## What to manually verify on Windows

1. Launch `python app.py`.
2. **HYIA Transfer Code Generator** — SIN field should be a short
   box (~8 chars wide), not stretching across the panel. Transfer
   amount should fit `9,999,999.99` (~14 chars). Date should be
   ~12 chars wide.
3. **Master Budget Compass Autofill** — three FileInput rows, the
   Browse / path display untouched (FileRow is a separate primitive
   that handles its own width, not affected by Round 40).
4. **Sub-Program Budget Report** — the threshold sliders (RangeInput)
   are unchanged. They already had a paired `numeric_box` of fixed
   ~6 chars (Round 11).
5. **Operating Statement** — threshold dollar field (~14 chars) and
   threshold % field (~12 chars) sit on the left edge, not stretching.
6. **Refined PAL Search** — no inputs; nothing to verify.
7. Resize the window wider — input boxes should NOT grow with the
   window. They stay at their declared width on the left of each row.

---

## Roll into the v2.2.2.0 hotfix

Add to patch notes:

> • Input fields (SIN, transfer amount, dates, thresholds) now have
>   appropriate fixed widths instead of stretching across the
>   window. Cleaner look on wide displays.

---

## Files committed-side

```
ADD   handoff/round40_fixed_width_text_boxes.md
MOD   toolkit/primitives.py
MOD   toolkit/base_tool.py
MOD   toolkit/shell.py
MOD   tools/hyia/frame.py
MOD   tools/operating/tests/test_frame.py
```
