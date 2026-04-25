"""Drift guard: asserts that toolkit/tokens.py matches what port_tokens.py
would generate from the canonical CSS.  Run with pytest or directly.

CI usage: pytest tests/test_tokens_drift.py

Three tests in this module
--------------------------
1. test_tokens_not_drifted
   Runs ``python scripts/port_tokens.py --check`` and asserts exit 0,
   confirming toolkit/tokens.py is in sync with the CSS source-of-truth.

2. test_no_rogue_hex_in_tool_strings
   AST-scans every non-test .py file under tools/ for string literals that
   contain a bare hex colour (``#RRGGBB``).  Any such hex must be one of the
   three canonical HL_* values; anything else indicates hard-coded drift.

3. test_pattern_fill_colours_are_canonical
   AST-scans the same file set for PatternFill(fgColor=...) call sites and
   asserts the fgColor argument is either ``argb(<HL_*>)`` or a string
   literal whose 8-char ARGB value matches ``"FF" + <HL_*>``.  Also fails if
   no PatternFill calls are found at all, so an accidental wholesale removal
   of fills doesn't silently bypass the check.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

from toolkit.tokens import HL_EDITED, HL_MISMATCH, HL_SOURCE_ONLY

_REPO = Path(__file__).parent.parent
_SCRIPT = _REPO / "scripts" / "port_tokens.py"
_TOOLS = _REPO / "tools"

# The three canonical HL_* hex values (always 6 uppercase chars, no leading #).
_CANONICAL_HEX: frozenset[str] = frozenset(
    {HL_EDITED.upper(), HL_MISMATCH.upper(), HL_SOURCE_ONLY.upper()}
)

# Set of HL_* identifier names (used for AST Name checks).
_CANONICAL_NAMES: frozenset[str] = frozenset({"HL_EDITED", "HL_MISMATCH", "HL_SOURCE_ONLY"})

# Regex that finds a bare #RRGGBB hex literal inside any string value.
_HEX_RE = re.compile(r"#([0-9A-Fa-f]{6})")


def _tool_py_files() -> Iterator[Path]:
    """Yield every .py file under tools/ that is not __pycache__ or tests."""
    for path in _TOOLS.rglob("*.py"):
        parts = path.relative_to(_TOOLS).parts
        if "__pycache__" in parts:
            continue
        if "tests" in parts:
            continue
        yield path


# ---------------------------------------------------------------------------
# Test 1 — shipped by the original authors; must not be modified.
# ---------------------------------------------------------------------------


def test_tokens_not_drifted() -> None:
    """port_tokens.py --check exits 0 when tokens.py is in sync."""
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "toolkit/tokens.py has drifted from colors_and_type.css.\n"
        "Re-run:  python scripts/port_tokens.py\n\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# Test 2 — rogue hex literals in tool string constants.
# ---------------------------------------------------------------------------


def test_no_rogue_hex_in_tool_strings() -> None:
    """Every #RRGGBB hex inside a string literal in tools/ must be a canonical HL_* value.

    Scans the AST of each production .py file under tools/ (skipping
    __pycache__ and tests sub-trees) for ast.Constant string nodes.  Any
    string that contains a pattern matching ``#[0-9A-Fa-f]{6}`` must have
    that hex portion (upper-cased) equal to one of:
        {HL_EDITED, HL_MISMATCH, HL_SOURCE_ONLY}
    """
    violations: list[str] = []

    for path in _tool_py_files():
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            violations.append(f"{path.relative_to(_REPO)}: SyntaxError — {exc}")
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant):
                continue
            if not isinstance(node.value, str):
                continue
            for match in _HEX_RE.finditer(node.value):
                found_hex = match.group(1).upper()
                if found_hex not in _CANONICAL_HEX:
                    violations.append(
                        f"{path.relative_to(_REPO)}:{node.lineno}: "
                        f"rogue hex #{found_hex!r} found in string literal — "
                        f"allowed values: {_CANONICAL_HEX}"
                    )

    assert not violations, (
        "Hard-coded non-canonical hex colour(s) found in tool string literals:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ---------------------------------------------------------------------------
# Test 3 — PatternFill fgColor must use the canonical argb() pattern.
# ---------------------------------------------------------------------------


def _is_canonical_argb_call(node: ast.expr) -> bool:
    """Return True if *node* is ``argb(<HL_*>)`` — a call to the argb() helper
    with exactly one positional argument that is one of the HL_* identifiers.
    """
    if not isinstance(node, ast.Call):
        return False
    # Accept bare ``argb(...)`` regardless of how it was imported.
    func = node.func
    if isinstance(func, ast.Name):
        func_name = func.id
    elif isinstance(func, ast.Attribute):
        func_name = func.attr
    else:
        return False
    if func_name != "argb":
        return False
    # Exactly one positional argument, no keyword arguments.
    if len(node.args) != 1 or node.keywords:
        return False
    arg = node.args[0]
    return isinstance(arg, ast.Name) and arg.id in _CANONICAL_NAMES


def _is_canonical_argb_string(node: ast.expr) -> bool:
    """Return True if *node* is a string constant of the form ``"FF" + <HL_*>``.

    Accepts any capitalisation; the comparison is performed after upper-casing
    the value.  Only 8-character values are considered.
    """
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        return False
    val = node.value.upper()
    if len(val) != 8:
        return False
    if not val.startswith("FF"):
        return False
    return val[2:] in _CANONICAL_HEX


def _get_func_end_name(call_node: ast.Call) -> str:
    """Return the trailing name component of a call's function expression."""
    func = call_node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def test_pattern_fill_colours_are_canonical() -> None:
    """Every PatternFill(fgColor=...) in tools/ must use argb(<HL_*>) or an ARGB string literal.

    Scans the AST of every production .py file under tools/ (skipping
    __pycache__ and tests sub-trees) for ast.Call nodes whose function name
    ends in ``PatternFill``.  For any such call that includes an ``fgColor``
    keyword argument the value must be either:

    * A call to ``argb()`` whose sole positional argument is one of the HL_*
      identifiers (``HL_EDITED``, ``HL_MISMATCH``, or ``HL_SOURCE_ONLY``).
    * A string constant of exact form ``"FF" + <one of the three HL_* hex>``
      (case-insensitive, e.g. ``"FFF4CCCC"``).

    Also fails with a sentinel message if no PatternFill calls at all are
    found under tools/, so that an accidental wholesale removal of fills
    doesn't silently render this check inert.
    """
    violations: list[str] = []
    total_fill_calls: int = 0

    for path in _tool_py_files():
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            violations.append(f"{path.relative_to(_REPO)}: SyntaxError — {exc}")
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _get_func_end_name(node) != "PatternFill":
                continue

            total_fill_calls += 1

            # Find the fgColor keyword argument (if any).
            fg_value: ast.expr | None = None
            for kw in node.keywords:
                if kw.arg == "fgColor":
                    fg_value = kw.value
                    break

            if fg_value is None:
                # PatternFill without fgColor — not our concern.
                continue

            if _is_canonical_argb_call(fg_value) or _is_canonical_argb_string(fg_value):
                continue

            # Non-canonical fgColor found.
            rel = path.relative_to(_REPO)
            violations.append(
                f"{rel}:{node.lineno}: PatternFill fgColor is not canonical — "
                f"got {ast.unparse(fg_value)!r}; "
                f"expected argb(<HL_*>) or a string like 'FF' + one of {_CANONICAL_HEX}"
            )

    assert total_fill_calls > 0, (
        "no PatternFill calls found — drift check is inert. "
        "If PatternFill has been replaced by a different fill API, "
        "update this test to match."
    )

    assert not violations, (
        "Non-canonical PatternFill fgColor value(s) detected in tools/:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_canonical_token_values() -> None:
    """Pin the absolute hex of the three highlight tokens.

    `test_tokens_not_drifted` only checks Python<->CSS parity. If both sides drift
    to the same wrong value, that test passes. This test is the second hand on
    the clock -- the three highlight roles (yellow/edited, pink/mismatch,
    green/source-only) must hold their hex values *forever*; if a refresh of
    the design system genuinely renames any of them, that's a deliberate
    cross-cutting change that should also update this test.
    """
    assert HL_EDITED == "FFF2CC", (
        "HL_EDITED is the yellow user-edited convention; canonical hex is FFF2CC."
    )
    assert HL_MISMATCH == "F4CCCC", (
        "HL_MISMATCH is the pink/red over-budget / row+column mismatch fill; "
        "canonical hex is F4CCCC."
    )
    assert HL_SOURCE_ONLY == "E2F0D9", (
        "HL_SOURCE_ONLY is the green source-only inserted-row fill; canonical hex is E2F0D9."
    )
