"""Parse design_system/…/colors_and_type.css and emit toolkit/tokens.py.

Usage
-----
  python scripts/port_tokens.py          # regenerate toolkit/tokens.py
  python scripts/port_tokens.py --check  # exit 0 if in sync, 1 if drift
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (relative to repo root, resolved against this script's location)
# ---------------------------------------------------------------------------
_REPO = Path(__file__).parent.parent
_CSS = _REPO / "design_system" / "design_handoff_school_finance_toolkit" / "colors_and_type.css"
_OUT = _REPO / "toolkit" / "tokens.py"

# ---------------------------------------------------------------------------
# Font constants — derived from CSS font-family stacks (hard-coded per spec)
# ---------------------------------------------------------------------------
_FONTS: list[tuple[str, str]] = [
    ("FONT_MONO_FALLBACK", "Consolas"),
    ("FONT_MONO_PRIMARY", "Cascadia Mono"),
    ("FONT_SANS_FALLBACK", "Segoe UI"),
    ("FONT_SANS_PRIMARY", "Aptos"),
    ("FONT_SERIF_PRIMARY", "Source Serif 4"),
]

# Tokens whose hex values must be emitted WITHOUT the leading '#'
# (they feed openpyxl PatternFill directly).
_OPENPYXL_FILLS = {"HL_EDITED", "HL_MISMATCH", "HL_SOURCE_ONLY"}

# Tokens to skip entirely (motion, elevation — not used by Tkinter)
_SKIP_PREFIXES = ("--sh-", "--ease-", "--dur-", "--font-", "--font-display")


# ---------------------------------------------------------------------------
# CSS parsing helpers
# ---------------------------------------------------------------------------


def _extract_root_block(css: str) -> str:
    """Return the text inside the first :root { … } block."""
    m = re.search(r":root\s*\{([^}]*)\}", css, re.DOTALL)
    if not m:
        raise ValueError("No :root { } block found in CSS.")
    return m.group(1)


def _parse_declarations(block: str) -> dict[str, str]:
    """Return {css-var-name: raw-value} for every declaration in *block*.

    Handles multi-line values (box-shadows, font stacks) by tracking the
    value up to the next ``--`` property or the end of the block.
    """
    raw: dict[str, str] = {}
    # Strip comments first
    block = re.sub(r"/\*.*?\*/", "", block, flags=re.DOTALL)
    # Each property starts with --<name>:
    pattern = re.compile(r"(--[\w-]+)\s*:\s*", re.MULTILINE)
    positions = [(m.start(), m.end(), m.group(1)) for m in pattern.finditer(block)]
    for i, (_, val_start, name) in enumerate(positions):
        val_end = positions[i + 1][0] if i + 1 < len(positions) else len(block)
        value = block[val_start:val_end].strip().rstrip(";").strip()
        # Collapse internal whitespace / newlines in the value
        value = re.sub(r"\s+", " ", value)
        raw[name] = value
    return raw


def _resolve(raw: dict[str, str]) -> dict[str, str]:
    """Resolve var(--x) references transitively (one-pass is sufficient for
    this file because all references point to earlier declarations)."""
    resolved: dict[str, str] = {}
    for name, value in raw.items():
        v = value
        for _ in range(10):  # guard against circular refs
            m = re.search(r"var\((--[\w-]+)\)", v)
            if not m:
                break
            ref = m.group(1)
            replacement = resolved.get(ref, raw.get(ref, m.group(0)))
            v = v[: m.start()] + replacement + v[m.end() :]
        resolved[name] = v
    return resolved


# ---------------------------------------------------------------------------
# Value coercion
# ---------------------------------------------------------------------------


def _py_name(css_name: str) -> str:
    """--brand-navy-700 → BRAND_NAVY_700"""
    return css_name.lstrip("-").replace("-", "_").upper()


def _is_hex(value: str) -> bool:
    return bool(re.fullmatch(r"#[0-9A-Fa-f]{3,8}", value))


def _is_px_int(value: str) -> bool:
    return bool(re.fullmatch(r"\d+px", value))


def _is_float_lh(value: str) -> bool:
    return bool(re.fullmatch(r"\d+\.\d+", value))


def _is_plain_int(value: str) -> bool:
    return bool(re.fullmatch(r"\d+", value))


def _coerce(py_name: str, value: str) -> str | None:
    """Return the Python literal for *value*, or None to skip."""
    if _is_hex(value):
        hex_digits = value.lstrip("#")
        if py_name in _OPENPYXL_FILLS:
            return f'"{hex_digits.upper()}"'
        return f'"{value.upper() if len(value) == 7 else value}"'
    if _is_px_int(value):
        return str(int(value[:-2]))
    if _is_float_lh(value):
        return value  # keep as float literal e.g. 1.15
    if _is_plain_int(value):
        return value
    return None  # skip complex / unrecognised values


# ---------------------------------------------------------------------------
# Token grouping
# ---------------------------------------------------------------------------

_GROUP_ORDER: list[tuple[str, Callable[[str], bool]]] = [
    ("# Colors — brand", lambda n: n.startswith("BRAND_")),
    ("# Colors — neutrals (backgrounds)", lambda n: n.startswith("BG_")),
    ("# Colors — borders", lambda n: n.startswith("BORDER_")),
    ("# Colors — foregrounds", lambda n: n.startswith("FG_")),
    ("# Colors — semantic: ok", lambda n: n.startswith("OK_")),
    ("# Colors — semantic: warning", lambda n: n.startswith("WARN_")),
    ("# Colors — semantic: danger", lambda n: n.startswith("DANGER_")),
    ("# Colors — semantic: info", lambda n: n.startswith("INFO_")),
    ("# Colors — data highlights (openpyxl fills, no leading #)", lambda n: n.startswith("HL_")),
    ("# Typography — font sizes (px as int)", lambda n: n.startswith("FS_")),
    ("# Typography — line heights", lambda n: n.startswith("LH_")),
    ("# Typography — font weights", lambda n: n.startswith("FW_")),
    ("# Fonts", lambda n: n.startswith("FONT_")),
    ("# Spacing — 4 px grid", lambda n: n.startswith("SP_")),
    ("# Radii", lambda n: n.startswith("R_")),
]


def _assign_group(name: str) -> int:
    for i, (_, pred) in enumerate(_GROUP_ORDER):
        # check predicate
        if pred(name):
            return i
    return len(_GROUP_ORDER)  # catch-all (should not happen after filtering)


# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------


def _generate(css_path: Path) -> str:
    css = css_path.read_text(encoding="utf-8")
    block = _extract_root_block(css)
    raw = _parse_declarations(block)
    resolved = _resolve(raw)

    # Collect emittable tokens (skip motion/shadow/font-stack refs)
    tokens: list[tuple[str, str]] = []  # (py_name, literal)
    for css_name, value in resolved.items():
        if any(css_name.startswith(p) for p in _SKIP_PREFIXES):
            continue
        py = _py_name(css_name)
        literal = _coerce(py, value)
        if literal is None:
            continue
        tokens.append((py, literal))

    # Add hard-coded font constants
    for fname, fval in _FONTS:
        tokens.append((fname, f'"{fval}"'))

    # Sort within groups, groups in defined order
    def sort_key(item: tuple[str, str]) -> tuple[int, str]:
        return (_assign_group(item[0]), item[0])

    tokens.sort(key=sort_key)

    # Build output lines
    lines: list[str] = [
        "# AUTO-GENERATED — DO NOT EDIT BY HAND. Run scripts/port_tokens.py.",
        "from __future__ import annotations",
        "",
    ]

    current_group: int = -1
    for py_name, literal in tokens:
        g = _assign_group(py_name)
        if g != current_group:
            if current_group != -1:
                lines.append("")
            label, _ = _GROUP_ORDER[g] if g < len(_GROUP_ORDER) else ("# Other", None)
            lines.append(label)
            current_group = g
        lines.append(f"{py_name} = {literal}")

    lines.append("")  # trailing newline (file ends with \n)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    check_mode = "--check" in sys.argv[1:]

    content = _generate(_CSS)

    if check_mode:
        if not _OUT.exists():
            print("DRIFT: toolkit/tokens.py does not exist.", file=sys.stderr)
            sys.exit(1)
        existing = _OUT.read_text(encoding="utf-8")
        if existing == content:
            print("OK: toolkit/tokens.py is in sync with the CSS.")
            sys.exit(0)
        else:
            print(
                "DRIFT: toolkit/tokens.py differs from what port_tokens.py would generate.",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        _OUT.write_text(content, encoding="utf-8")
        print(f"Written: {_OUT}")


if __name__ == "__main__":
    main()
