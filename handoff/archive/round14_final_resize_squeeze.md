# Round 14 — Final resize-lag squeeze + bigger default window

**Date:** 2026-04-28
**Orchestrator:** Opus 4.7
**Builder:** Sonnet 4.6 (Agent P, ~119K tokens) + orchestrator inline cross-FS recovery
**Quality gates:** all green (ruff format 65 files, ruff check clean, mypy --strict 0 issues, pytest **424 passed / 53 skipped / 0 failed** in main scope)

---

## Two fixes landed

### Fix 1 — Default window size bumped

`app.py` line 19: `root.geometry("1440x900")` (was `"1200x820"`). The `minsize()` constraint is unchanged at `960x640`, so users on smaller laptops can still narrow the window if needed.

Test: `tests/test_shell_smoke.py::test_default_window_size_is_1440x900` (Tk-skip on Linux CI).

### Fix 2 — Final resize-lag squeeze

Round 9, 11, 13 cumulatively reduced what fires per resize tick. Round 14 finishes the job:

**A. Debounce 50ms → 100ms across all 9 sites**

| Site | Round added | Before | After |
|---|---|---|---|
| `SelectableList._on_inner_configure` | 9 | 50ms | 100ms |
| `SelectableList._on_canvas_configure` | 9 | 50ms | 100ms |
| `user_frame.py` outer canvas inner | 11 | 50ms | 100ms |
| `user_frame.py` outer canvas width | 11 | 50ms | 100ms |
| `shell.py::_build_tool_frame` per-tool inner | 11 | 50ms | 100ms |
| `shell.py::_build_tool_frame` per-tool width | 11 | 50ms | 100ms |
| `shell.py::_build_range_widget` slider preview (Sub-Program) | 10 | 100ms | 100ms (already) |
| `shell.py` second range widget instance | 10 | 100ms | 100ms (already) |
| `shell.py::_on_root_configure` global | 13 | 50ms | 100ms |

The 100ms window means layout settles ~100ms after motion stops, but during a drag the deferred work fires 1× per 100ms instead of 1× per 50ms — half the work, half the flicker.

**B. Treeview fixed rowheight**

Added `ttk.Style().configure("Treeview", rowheight=22)` at the start of `_build_layout` in `shell.py`. Tk's default Treeview recomputes row heights from font metrics on every `<Configure>` event. Pinning row height to 22px skips that recomputation entirely.

**C. Code comments**

Added clarifying comments on `_do_inner_configure` and `_do_canvas_configure` in both `shell.py` and `user_frame.py` explaining handler separation: scrollregion is inner-frame's job; canvas window width is canvas's job. Round 11/13 already had this scoping correct, but the comment now documents it for future maintainers.

---

## Cumulative resize improvements (Rounds 9 → 14)

| Aspect | Before all rounds | After Round 14 |
|---|---|---|
| Active Configure handlers per resize tick | many, every tool frame, every primitive | 1 root + 1 active-tool canvas + 1 active-tool inner |
| Debounce on each handler | none — synchronous | 100ms cancel-and-reschedule |
| Inactive tool frames receiving Configure | yes (lower()-ed but placed) | no (place_forget()-ed; Round 13) |
| Treeview column stretch | all columns stretch | only last column stretches (Round 13) |
| Treeview row height | dynamic, font-metric recomputed | fixed 22px (Round 14) |
| Default window | 1200x820 | 1440x900 |

---

## Files changed (Round 14)

| File | Change |
|---|---|
| `app.py` | geometry `"1200x820"` → `"1440x900"` |
| `toolkit/shell.py` | Treeview rowheight=22 in `_build_layout`; per-tool debounce 50→100ms (2 sites); root debounce 50→100ms; clarifying comments |
| `toolkit/user_frame.py` | Outer canvas debounces 50→100ms (2 sites); clarifying comments |
| `toolkit/primitives.py` | SelectableList debounces 50→100ms (2 sites); clarifying comments |
| `tests/test_shell_smoke.py` | New `test_default_window_size_is_1440x900` |

---

## Final quality gates

```
ruff format --check ........ 65 files already formatted
ruff check ................. All checks passed!
mypy --strict .............. Success: no issues found in 64 source files
pytest (main scope) ........ 424 passed, 53 skipped, 0 failed
Operating tests ............ 9 failed, 24 passed, 12 errors (PRE-EXISTING — missing PDF
                              files; not Round 14 related)
```

---

## Cross-FS sync note

Both `toolkit/user_frame.py` and `toolkit/primitives.py` had bash-mount truncation again — primitives.py cut at "# Tab" mid-comment, user_frame.py at "# Error banner helpers" mid-dash-line. Tail content restored from Windows-side Read view via Python heredoc + `touch` to invalidate Python's mtime cache.

This gotcha continues to bite essentially every multi-file round. CLAUDE.md documents the workaround. A defensive post-write verifier remains the right next investment if the project keeps iterating on the toolkit.

---

## What the user will see

1. Restart School Tool — the window opens at 1440x900 (roomy 16:10 default).
2. Drag the window edge from narrow to wide. Should feel smoothest yet — flicker reduced ~50%, settle is one beat after motion stops (~100ms imperceptible to most users).
3. The Sub-Program tab with a loaded report (rail + 7-col Treeview + log + banner) is the worst stress test; it should now feel as smooth as the simpler tabs.

---

## Pending items

- **Operating sample PDFs** — 12 setup errors reference `Samples/Operating Statement/GL21150_Operating Statement Detailed.pdf`; actual files are `…Feb.pdf` / `…Mar.pdf`. Small fixture-path fix when convenient.
- **Mailer FROM** — gmail.com still rejected by Resend; manual `/verify-email` curl works as test-account unblock.
- **Argon2 in Workers** — degraded to PBKDF2-100k for pilot.
- **M4** (admin dashboard, invoicing, credits) — paused since Round 6.
- **M8 — Camps** — blocked on samples.
