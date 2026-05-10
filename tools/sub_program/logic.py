from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import openpyxl
import pdfplumber
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from toolkit.base_tool import ProgressFn
from toolkit.fills import argb
from toolkit.tokens import HL_MISMATCH

# Pink row fill for over-budget rows in the XLSX output.
# Uses argb() from toolkit.fills to derive the correct openpyxl ARGB literal
# from the canonical HL_MISMATCH token — same approach as master_budget/logic.py.
_OVER_FILL = PatternFill(fill_type="solid", fgColor=argb(HL_MISMATCH))

# Round 39 — comment-column header synonyms.  Module-scope so that the
# fall-through "no comments column found" error path can quote them
# even when every input sheet was empty (otherwise we hit
# UnboundLocalError before surfacing the helpful message).
_COMMENT_SYNONYMS: tuple[str, ...] = (
    "comment",
    "commentary",
    "note",
    "remark",
    "memo",
)

# ---------------------------------------------------------------------------
# Round 51 Phase D — structured commentary
# ---------------------------------------------------------------------------
# Replaces freeform commentary with three Combobox-backed dropdowns plus
# a free-text Notes paragraph. The XLSX cell carries an optional prefix
# of the shape ``[Driver: X | Outlook: Y | Action: Z] notes``; only set
# fields appear in the prefix, blank fields are omitted. When all three
# dropdowns are blank the prefix is suppressed entirely so pre-Phase-D
# files round-trip as Notes-only.

_DRIVER_VALUES: tuple[str, ...] = (
    "One-time",
    "Ongoing",
    "Structural",
    "Timing-early",
    "Timing-late",
    "Investigating",
)
_OUTLOOK_VALUES: tuple[str, ...] = (
    "One-time",
    "Expected to continue",
    "Improving",
    "Deteriorating",
)
_ACTION_VALUES: tuple[str, ...] = (
    "None",
    "Monitor",
    "Investigate",
    "Update forecast",
)

# Greedy-up-to-first-`]` body match. The body must contain at least one
# of the three keys to be treated as a structured prefix; otherwise the
# whole cell falls through to freeform Notes (e.g. ``"[NOTE TO SELF]
# review later"`` is preserved verbatim, NOT parsed as a prefix).
_COMMENTARY_PREFIX_RE = re.compile(
    r"^\[(?P<body>[^\]\n]*)\](?P<rest>.*)$",
    re.DOTALL,
)
_PREFIX_FIELD_RE = re.compile(r"\s*(?P<key>Driver|Outlook|Action)\s*:\s*(?P<val>[^|]*?)\s*(?:\||$)")


def encode_commentary(
    notes: str,
    driver: str = "",
    outlook: str = "",
    action: str = "",
) -> str:
    """Encode structured commentary into a single string.

    Used as the value written to the XLSX Comments cell. The prefix is
    only emitted when at least one structured field is non-empty;
    otherwise we return the bare notes (preserving backward
    compatibility with pre-Phase-D files). Blank fields are omitted
    from the prefix entirely — e.g. ``encode_commentary("n", action="Monitor")``
    → ``"[Action: Monitor]\\nn"``.

    Edge case: when all three structured fields are blank but the notes
    paragraph happens to start with ``[``, we emit an empty-body
    prefix ``[]`` as an escape so :func:`decode_commentary` can later
    distinguish "user typed a literal bracket" from "structured prefix
    we couldn't parse".

    Round 1 fix (R51): the prefix and notes are separated by a NEWLINE
    so when ``wrap_text`` is on the XLSX cell, notes start on their own
    visual line — the prefix doesn't visually merge into the paragraph
    when the cell wraps mid-prefix in a 50-char column.
    :func:`decode_commentary` strips exactly one separator either way,
    so the round-trip is unaffected.

    Excel-formula-injection guard: this encoder NEVER prepends
    ``=``/``+``/``-``/``@`` (the Excel formula sigils) — those checks
    happen at the cell-write site since not every encoder consumer
    writes to a cell. See ``_write_monthly_sub_program_sheet``.
    """
    fields: list[str] = []
    if driver:
        fields.append(f"Driver: {driver}")
    if outlook:
        fields.append(f"Outlook: {outlook}")
    if action:
        fields.append(f"Action: {action}")
    if not fields:
        if notes.lstrip().startswith("["):
            return f"[]\n{notes}"
        return notes
    prefix = "[" + " | ".join(fields) + "]"
    if not notes:
        return prefix
    return f"{prefix}\n{notes}"


def decode_commentary(text: str) -> tuple[str, str, str, str]:
    """Inverse of :func:`encode_commentary`.

    Returns ``(notes, driver, outlook, action)``. Anything that doesn't
    look like a Phase-D prefix is treated as freeform notes — so a
    pre-Phase-D file with unstructured text round-trips as
    ``(text, "", "", "")``.

    Round 1 fixes (R51):

    * **Whitespace preservation** — only the prefix-adjacent separator
      (the single space or newline immediately after ``]``) is stripped.
      Inner whitespace in the user's notes is preserved so a
      save→reopen cycle is idempotent.
    * **Unknown-value validation** — extracted Driver / Outlook / Action
      values are checked against the canonical
      :data:`_DRIVER_VALUES` / :data:`_OUTLOOK_VALUES` /
      :data:`_ACTION_VALUES` tuples. If any value is unknown, the
      whole text is preserved verbatim as Notes — protects users
      whose pre-Phase-D commentary happened to contain literal
      ``[Driver: foo]`` text from being silently mis-parsed and losing
      part of their note. Also the Editor's Combobox preload then
      relies on this contract.

    Special cases:

    * ``[] rest`` — empty-body prefix is the encoder's escape for
      "notes started with ``[`` and dropdowns were blank". We strip
      ``[]`` and return ``rest`` as Notes.
    * ``[FREE TEXT] more`` — body without any Phase-D key. Preserved
      verbatim as Notes (no information loss).
    """
    if not text:
        return "", "", "", ""
    m = _COMMENTARY_PREFIX_RE.match(text)
    if m is None:
        return text, "", "", ""
    body = m.group("body").strip()
    rest_raw = m.group("rest")
    # Strip exactly one separator (newline or space) immediately
    # following the closing ``]`` — preserves inner whitespace in the
    # user's notes so encode→decode→encode is idempotent.
    if rest_raw.startswith("\n") or rest_raw.startswith(" "):
        rest = rest_raw[1:]
    else:
        rest = rest_raw
    if body == "":
        # Empty-body prefix = encoder's escape for "[..." in Notes.
        return rest, "", "", ""
    # Body must contain at least one Phase-D key, else treat the whole
    # thing as freeform notes (preserves "[FREE TEXT] more" verbatim).
    if not any(k in body for k in ("Driver:", "Outlook:", "Action:")):
        return text, "", "", ""
    driver = outlook = action = ""
    for fm in _PREFIX_FIELD_RE.finditer(body):
        key = fm.group("key")
        val = fm.group("val").strip()
        if key == "Driver":
            driver = val
        elif key == "Outlook":
            outlook = val
        elif key == "Action":
            action = val
    # Round 2 fix (R51): preserve unknown values verbatim instead of
    # discarding the whole prefix. The Round-1 "fall through to Notes
    # on unknown value" rule collided with the editor's Combobox
    # preservation (frame.py:_add_combobox_row) and produced a
    # round-trip data-loss bug — a non-canonical value the editor
    # preserved was stripped on the next XLSX read, demoting Driver
    # back into Notes. Trading that for a small pre-Phase-D risk:
    # freeform text like ``"[Driver: training costs] note"`` will now
    # extract Driver as ``"training costs"`` instead of staying as
    # Notes. The ``_DRIVER_VALUES`` / etc tuples remain the source of
    # truth for the editor's dropdown — a user opening such a row sees
    # the legacy value AND can re-pick a canonical one — so any
    # mis-parse is recoverable. The frequency of pre-Phase-D
    # commentary literally beginning with ``[Driver:`` / ``[Outlook:``
    # / ``[Action:`` is empirically very low; the frequency of
    # hand-edited or schema-drifted values is higher.
    return rest, driver, outlook, action


# ---------------------------------------------------------------------------
# Round 53 F1 — Status pills (Move B)
# ---------------------------------------------------------------------------
# The XLSX output gains a per-sub-program ``Status`` column whose value
# is one of six plain-English pills. The pill replaces — for non-finance
# readers — the unreadable ``Available Balance % YTD`` column (which can
# read ``-2.21`` for a 221% overdraw and which the actual KMAR file
# shows as a literal ``7`` for stale ``=N/A`` cells).

_STATUS_ON_TRACK = "On track"
_STATUS_SLIGHTLY_OVER = "Slightly over"
# Round 53 F1 R1 fix: was "Material concern" (finance jargon).
# Renamed to plain English so a non-finance reader parses it correctly.
_STATUS_MATERIAL = "Significant overspend"
_STATUS_URGENT = "Investigate urgently"
_STATUS_NO_SPEND_YET = "No spend yet"
_STATUS_SPENT_WITHOUT_BUDGET = "Spent without budget"

_STATUS_VALUES: tuple[str, ...] = (
    _STATUS_ON_TRACK,
    _STATUS_SLIGHTLY_OVER,
    _STATUS_MATERIAL,
    _STATUS_URGENT,
    _STATUS_NO_SPEND_YET,
    _STATUS_SPENT_WITHOUT_BUDGET,
)

# Bucket boundaries for overrun magnitude. Both dollar AND percent
# triggers fire — whichever is larger picks the bucket. This matches
# the variance-analysis skill's "either exceeded" rule for materiality.
_STATUS_URGENT_DOLLAR = Decimal("100000")
_STATUS_URGENT_PCT = Decimal("50")
_STATUS_MATERIAL_DOLLAR = Decimal("25000")
_STATUS_MATERIAL_PCT = Decimal("25")

# "No spend yet" only fires when we're past 25% of the year — earlier
# than that, an empty YTD on a budgeted line is normal seasonal flow.
_NO_SPEND_CALENDAR_THRESHOLD = 25.0


def compute_status_pill(
    *,
    available: Decimal,
    annual_exp_budget: Decimal,
    rev_ytd: Decimal,
    exp_ytd: Decimal,
    annual_rev_budget: Decimal = Decimal("0"),
    materiality_dollar: int = 5000,
    calendar_pct: float = 0.0,
) -> str:
    """Return a plain-English status pill for one sub-program row.

    ``available`` is the signed YTD net position (rev_ytd + carry-forward
    − exp_ytd − outstanding_orders, mirrors the XLSX writer's calc).
    Positive = surplus / under-spend; negative = over-drawn.

    Pill picks (first match wins):

    * ``Spent without budget`` — TRULY unbudgeted capital spend:
      ``annual_exp_budget == 0 AND annual_rev_budget == 0 AND exp_ytd > 0``.
      The R1-fix-tightened gate excludes fundraising programs that
      have a revenue budget but no expenditure budget (cost-recovery
      style), which would otherwise mis-fire here.
    * ``No spend yet`` — annual exp budget > materiality_dollar AND
      both exp_ytd == 0 AND rev_ytd == 0 AND calendar past 25%. A
      council member would ask "shouldn't this be funded by now?".
    * ``On track`` — for combined programs (both rev_b and exp_b > 0):
      surplus, OR overrun below the materiality dollar floor.
      For expenditure-only programs (no revenue side): R1 fix uses a
      pacing-aware compare — pacing within ±15% of calendar is on
      track. Without this, a 50%-spent line in April (calendar 33%)
      would mis-classify as Material via the raw available signal.
    * ``Investigate urgently`` — overrun > $100K OR > 50% of budget.
    * ``Significant overspend`` — overrun $25K–$100K OR 25–50% of
      budget. (Renamed from the R0 "Material concern" — was finance
      jargon to a non-finance reader.)
    * ``Slightly over`` — anything else past the materiality floor.
    """
    mat = Decimal(str(materiality_dollar))

    # Spent without budget — capital-spend-without-approval flag.
    # R1 fix: tightened gate — must have NO budget on either side.
    # A fundraiser with rev_b > 0, exp_b == 0 is NOT unbudgeted.
    # R2 fix: also require ``rev_ytd == 0``. A program collecting
    # revenue but with zero budget on either side is a configuration
    # mistake (someone forgot to add the budget) — surfacing it as
    # "Spent without budget" alongside its visible revenue collection
    # reads as contradictory to a council member.
    if annual_exp_budget == 0 and annual_rev_budget == 0 and rev_ytd == 0 and exp_ytd > 0:
        return _STATUS_SPENT_WITHOUT_BUDGET

    # No spend yet — placeholder past 25% of year.
    # R2 fix: loosened the ``exp_ytd == 0`` strict gate to a fractional
    # threshold capped at the dollar materiality floor — captures the
    # trickle case (e.g. $100 spent on a $50K budget at 33% calendar)
    # without false-positives on normally-paced small programs ($3,500
    # on $10K at 33% calendar is healthy, not "no spend yet"). The
    # threshold = min(materiality_dollar, 5% of annual_exp_budget).
    spend_threshold = min(mat, annual_exp_budget * Decimal("0.05"))
    if (
        annual_exp_budget > mat
        and exp_ytd < spend_threshold
        and rev_ytd < spend_threshold
        and calendar_pct > _NO_SPEND_CALENDAR_THRESHOLD
    ):
        return _STATUS_NO_SPEND_YET

    # R1 fix: Expenditure-only sub-programs (no revenue side and no
    # carry-forward) need a pacing-aware comparison. The raw
    # ``available`` value is just ``-exp_ytd`` for these — it always
    # reads as deficit, even when the program is perfectly on pace.
    # We compare actual spend pace to calendar pace: if exp_ytd / eb
    # is within ±15% of calendar_pct / 100, the line is on track.
    # R2 fix: dropped the ``rev_ytd == 0`` requirement. A donation-
    # funded program (rev_b == 0 but rev_ytd > 0) belongs in this
    # branch too — its expenditure side is what we're pacing against.
    is_expenditure_only = annual_rev_budget == 0 and annual_exp_budget > 0
    if is_expenditure_only and calendar_pct > 0:
        # R2 fix: pacing uses the COMMITTED amount (exp_ytd + outstanding
        # orders), not just exp_ytd. Outstanding orders bind budget the
        # same way actual spend does. Without this fix, an Admin-style
        # row with $192K spent + $1.7M orders on a $582K budget reads
        # as "33% of budget consumed" (matching calendar) and
        # mis-classifies as "On track" — when in reality the program
        # is committed to ~$1.9M of spend (3.3× budget). The committed
        # amount is reconstructible without an extra parameter:
        # committed = rev_ytd - available  (since available =
        # rev_ytd - exp_ytd - oo, so oo + exp_ytd = rev_ytd - available).
        committed = rev_ytd - available
        actual_pace = committed / annual_exp_budget
        expected_pace = Decimal(str(calendar_pct)) / Decimal("100")
        pace_gap = actual_pace - expected_pace
        # Within 15% pacing band -> on track. The 15% band gives a
        # generous tolerance for chunky / front-loaded / back-loaded
        # spending patterns common in school programs.
        if abs(pace_gap) <= Decimal("0.15"):
            return _STATUS_ON_TRACK
        # Outside the band — fall through to the standard overrun
        # logic but using exp_ytd-vs-budget as the overrun magnitude
        # rather than the raw available signal.
        if pace_gap > 0:
            # Over-pacing.
            overrun = committed - (annual_exp_budget * expected_pace)
            pct_over = pace_gap * Decimal("100")
            if overrun >= mat:
                if overrun > _STATUS_URGENT_DOLLAR or pct_over > _STATUS_URGENT_PCT:
                    return _STATUS_URGENT
                if overrun > _STATUS_MATERIAL_DOLLAR or pct_over > _STATUS_MATERIAL_PCT:
                    return _STATUS_MATERIAL
                return _STATUS_SLIGHTLY_OVER
        # Under-pacing — programs that haven't ramped up are on
        # track for budget. (No status flag; council members would
        # ask via the No-spend-yet trigger above for the extreme case.)
        return _STATUS_ON_TRACK

    # Surplus / on-pace — on track.
    if available >= 0:
        return _STATUS_ON_TRACK

    overrun = -available  # positive number
    # R2 fix: hard $500 noise floor — chart-of-accounts placeholder
    # rows ($50 over a $30 stationery budget = 167% over but $50
    # absolute) are below council attention regardless of percent.
    # This sits BELOW the regular dollar/percent floors: "below
    # noise" wins.
    if overrun < Decimal("500"):
        return _STATUS_ON_TRACK
    # Compute overrun as percent of expenditure budget once.
    pct_over = (
        (overrun / annual_exp_budget * Decimal("100")) if annual_exp_budget > 0 else Decimal("0")
    )
    # R2 fix: materiality floor now uses BOTH dollar AND percent (skill
    # rule: "either exceeded"). A $4K overrun on a $200 budget = 2,000%
    # over and IS material; a $5K overrun on a $50K budget = 10% over
    # → below both floors → On track.
    if overrun < mat and pct_over <= Decimal("50"):
        return _STATUS_ON_TRACK

    if overrun > _STATUS_URGENT_DOLLAR or pct_over > _STATUS_URGENT_PCT:
        return _STATUS_URGENT
    if overrun > _STATUS_MATERIAL_DOLLAR or pct_over > _STATUS_MATERIAL_PCT:
        return _STATUS_MATERIAL
    return _STATUS_SLIGHTLY_OVER


# ---------------------------------------------------------------------------
# Round 53 F1 — Plain-English commentary (Move E)
# ---------------------------------------------------------------------------
# The XLSX Comments cell renders the structured Phase-D triplet as
# plain English instead of the bracketed prefix that lives internally.
# Round-trip fidelity through prior-period files is sacrificed in the
# rendered cell (the visible value is prose, not the prefix); the
# decoder still works on legacy R51 prefix-encoded cells.

_DRIVER_PROSE: dict[str, str] = {
    "One-time": "One-time variance",
    "Ongoing": "Ongoing variance",
    "Structural": "Structural variance",
    "Timing-early": "Spend earlier than planned",
    "Timing-late": "Spend later than planned",
    "Investigating": "Driver under investigation",
}

_OUTLOOK_PROSE: dict[str, str] = {
    "One-time": "won't recur",
    "Expected to continue": "expected to continue",
    "Improving": "improving",
    "Deteriorating": "deteriorating",
}

_ACTION_PROSE: dict[str, str] = {
    "None": "no action needed",
    "Monitor": "being monitored",
    "Investigate": "needs investigation",
    "Update forecast": "forecast update needed",
}


def _capitalize_first(s: str) -> str:
    """Uppercase only the first character. Differs from str.capitalize
    which lower-cases the rest — we want 'Reviewed by HOD' to keep
    'HOD' upper-cased, not become 'Reviewed by hod'."""
    return s[:1].upper() + s[1:] if s else s


def _ensure_terminal_period(s: str) -> str:
    """Ensure the trimmed string ends with terminal punctuation."""
    s = s.strip()
    if not s:
        return s
    if s[-1] in (".", "!", "?"):
        return s
    return s + "."


# Combinations that read as logically contradictory and should NOT
# render together. R1 fix: Round-1 logic skeptic flagged these.
# Format: (driver, outlook) tuples whose outlook is dropped.
_CONTRADICTORY_DRIVER_OUTLOOK: frozenset[tuple[str, str]] = frozenset(
    {
        # Structural variance won't recur — by definition it's permanent.
        ("Structural", "One-time"),
        # One-time variance "expected to continue" — definitionally wrong.
        ("One-time", "Expected to continue"),
        # R2 fix: "we don't know what's driving this AND we know it's
        # getting better" reads as incoherent. ``Investigating`` +
        # ``Deteriorating`` is fine ("we don't know why but it's
        # getting worse").
        ("Investigating", "Improving"),
    }
)

# Driver / Action combinations where the action is dropped (it
# duplicates or contradicts the driver).
_CONTRADICTORY_DRIVER_ACTION: frozenset[tuple[str, str]] = frozenset(
    {
        # "Driver under investigation" + "no action needed" is a direct
        # contradiction — investigating IS an action.
        ("Investigating", "None"),
        # R2 fix: "Driver under investigation. Needs investigation." is
        # repetitive — same word root in two sentences. The driver
        # phrase already implies the investigation; drop the
        # action_prose.
        ("Investigating", "Investigate"),
    }
)


def render_commentary_prose(
    notes: str = "",
    driver: str = "",
    outlook: str = "",
    action: str = "",
) -> str:
    """Render structured commentary as plain-English prose for the
    XLSX Comments cell.

    Returns a 1–2 sentence string. The structured triplet (Driver +
    Outlook + Action) collapses to one or two short sentences (each
    with its own period — R1 fix replaced the em-dash splice that
    read as software-generated); the freeform Notes paragraph is the
    final sentence. All blank returns "".

    Unknown structured values (schema drift, hand edit) fall through
    silently — no crash, no half-sentence.

    Round 1 fix: contradictory triplet combinations have the conflicting
    field dropped (e.g. ``Structural`` + ``One-time`` outlook drops the
    outlook; ``Investigating`` + ``None`` action drops the action). See
    :data:`_CONTRADICTORY_DRIVER_OUTLOOK` / `_CONTRADICTORY_DRIVER_ACTION`.
    """
    driver_prose = _DRIVER_PROSE.get(driver, "")
    outlook_prose = _OUTLOOK_PROSE.get(outlook, "")
    action_prose = _ACTION_PROSE.get(action, "")

    # R1 fix: drop conflicting outlook / action combinations.
    if driver and outlook and (driver, outlook) in _CONTRADICTORY_DRIVER_OUTLOOK:
        outlook_prose = ""
    if driver and action and (driver, action) in _CONTRADICTORY_DRIVER_ACTION:
        action_prose = ""

    # Sentence 1: description (Driver + Outlook joined with ", ").
    # Sentence 2: action_prose, capitalised, its own sentence.
    # Sentence 3: notes verbatim with terminal punctuation guaranteed.
    # R1 fix: replaced em-dash splice ("description — action") with two
    # short sentences ("description. Action."). Reads as natural
    # English instead of template output.
    sentences: list[str] = []

    # R2 fix: when ``Investigating`` driver and outlook are both set,
    # the comma-joined form ("Driver under investigation, improving")
    # parses ambiguously — "improving" attaches to "investigation"
    # rather than to the variance. Render as two unambiguous
    # sentences instead.
    if driver == "Investigating" and outlook_prose and driver_prose:
        sentences.append(_ensure_terminal_period(_capitalize_first(driver_prose)))
        sentences.append(_ensure_terminal_period(_capitalize_first("variance " + outlook_prose)))
    else:
        desc_pieces: list[str] = []
        if driver_prose:
            desc_pieces.append(driver_prose)
        if outlook_prose:
            if desc_pieces:
                desc_pieces.append(outlook_prose)
            else:
                # Outlook leads — "Outlook improving."
                desc_pieces.append("Outlook " + outlook_prose)
        description = ", ".join(desc_pieces)
        if description:
            sentences.append(_ensure_terminal_period(_capitalize_first(description)))

    if action_prose:
        sentences.append(_ensure_terminal_period(_capitalize_first(action_prose)))
    if notes:
        sentences.append(_ensure_terminal_period(_capitalize_first(notes.strip())))

    return " ".join(sentences)


# ---------------------------------------------------------------------------
# Round 53 F1 — Percent display cap (Move F)
# ---------------------------------------------------------------------------
# Some sub-programs produce percent values that read as nonsense to a
# non-finance reader (the actual KMAR file has rev_y / rev_b = 21.36 =
# "2,136% revenue received" for sub-program 4400 Mathematics). We cap
# the displayed value at ±999% (= ±9.99 stored, since the cell number
# format is ``0.0%``) and attach a cell comment carrying the uncapped
# value so investigators still see the truth.

_PERCENT_CAP = Decimal("9.99")


def cap_percent_for_display(pct: Decimal | float | int | None) -> Decimal | None:
    """Cap an unbounded percent (stored as a fraction, e.g. 0.65 =
    65%) at ±999% for display.

    Returns ``None`` for ``None`` input. Otherwise returns a Decimal
    in the closed range ``[-9.99, 9.99]``.
    """
    if pct is None:
        return None
    p = Decimal(str(pct))
    if p > _PERCENT_CAP:
        return _PERCENT_CAP
    if p < -_PERCENT_CAP:
        return -_PERCENT_CAP
    return p


# ---------------------------------------------------------------------------
# Faculty inference
# ---------------------------------------------------------------------------
# Sub-program codes are numeric (e.g. 4001, 8599).
# Faculties are inferred from the leading digit(s) as visible in the PDF.
# The CASES21 GL21157 export groups rows by Revenue / Expenditure sections
# rather than by faculty, so we derive faculty from the code prefix.

_FACULTY_MAP: dict[str, str] = {
    "1": "Design & Technology",
    "4": "Curriculum",
    "5": "Student Wellbeing",
    "6": "Facilities",
    "7": "Administration",
    "8": "Programs & Camps",
    "9": "Computing & Curriculum",
}


def _infer_faculty(sub_program: str) -> str | None:
    """Return a faculty label from the first digit of *sub_program*."""
    code = sub_program.strip()
    if code and code[0].isdigit():
        return _FACULTY_MAP.get(code[0])
    return None


# ---------------------------------------------------------------------------
# Currency parsing
# ---------------------------------------------------------------------------

_DASH_RE = re.compile(r"^[—–\-]{1,2}$")  # em-dash, en-dash, hyphen alone


def parse_decimal(raw: str) -> Decimal:
    """Convert a CASES21 currency string to Decimal.

    Handles: ``"1,234.56"``, ``"$1,234.56"``, ``"-500.00"``, ``"(500.00)"``,
    ``"$0.00"``, ``"—"`` (em-dash = zero), blank strings.
    Returns ``Decimal("0")`` for empty / dash inputs.
    """
    text = raw.strip() if raw else ""

    if not text or _DASH_RE.match(text):
        return Decimal("0")

    # parentheses -> negative  e.g. "(500.00)" -> "-500.00"
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]

    # strip leading $
    text = text.lstrip("$").strip()

    # remove thousands separators
    text = text.replace(",", "")

    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Cannot parse {raw!r} as a decimal: {exc}") from exc


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubProgramLine:
    sub_program: str
    account: str  # section tag: "Revenue" | "Expenditure"
    description: str
    budget: Decimal
    ytd: Decimal
    remaining: Decimal
    used_pct: Decimal  # 0..100+
    faculty: str | None
    is_over: bool
    # Round 51 Phase D — ``commentary`` is now FREEFORM NOTES only.
    # Pre-Phase-D code stored everything in this single field; the new
    # XLSX prefix carries the structured triplet (driver/outlook/action)
    # alongside the notes via :func:`encode_commentary`.
    commentary: str = ""
    # Round 51 Phase D — structured commentary triplet. Each field is
    # one of the ``_DRIVER_VALUES`` / ``_OUTLOOK_VALUES`` /
    # ``_ACTION_VALUES`` module-scope tuples, or empty string for
    # "not categorised" (distinct from the literal ``"None"`` Action,
    # which means "user reviewed and decided no action needed").
    commentary_driver: str = ""
    commentary_outlook: str = ""
    commentary_action: str = ""
    # New fields -- default to zero so existing callers remain valid.
    last_year_actual: Decimal = Decimal("0")
    last_year_budget: Decimal = Decimal("0")
    outstanding_orders: Decimal = Decimal("0")
    # Round 45 Phase A — variance + pacing fields.
    #
    # variance_amount: signed YTD - Budget. Positive means YTD has exceeded
    # the annual budget. Sign is unconditional (same convention for Revenue
    # and Expenditure rows); the UI renders positive Expense variance as
    # red (over-spent) and negative Revenue variance as amber (under-
    # collected) — i.e., colour comes from account-aware tinting at render
    # time, not from the sign of this field.
    #
    # variance_pct: variance_amount / budget * 100, also signed. Zero when
    # budget is zero (we don't divide by zero — a zero-budget line with
    # any spend is flagged via is_over and surfaced via materiality, not
    # via percentage).
    #
    # pacing: used_pct / calendar_pct, expressed as a multiplier (1.00 =
    # exactly on pace, 1.50 = 50% ahead of calendar). Zero when calendar_pct
    # is zero or unknown — the UI then shows an em-dash.
    variance_amount: Decimal = Decimal("0")
    variance_pct: Decimal = Decimal("0")
    pacing: Decimal = Decimal("0")
    # Round 45 Phase A — materiality flag. True when |variance_amount| meets
    # OR exceeds the materiality dollar floor for this run. Computed in
    # generate_report (or _recompute_is_over for live-slider previews).
    is_material: bool = False


@dataclass(frozen=True)
class ReportSummary:
    lines: list[SubProgramLine]
    faculty_counts: dict[str, int]
    over_budget_lines: list[SubProgramLine]
    total_budget: Decimal
    total_ytd: Decimal
    output_path: Path
    faculty_budget: dict[str, Decimal] = field(default_factory=dict)
    faculty_ytd: dict[str, Decimal] = field(default_factory=dict)
    faculty_used_pct: dict[str, Decimal] = field(default_factory=dict)
    period_label: str = ""  # e.g. "March 2026" -- extracted from the PDF footer
    over_budget_threshold: float = 101.0  # threshold used for is_over computation
    # Round 21 — separate Revenue / Expense thresholds.  When the user does
    # not split them explicitly, both fields mirror over_budget_threshold
    # (set in generate_report) so existing callers stay valid.
    revenue_threshold: float = 101.0
    expense_threshold: float = 101.0
    # Round 45 Phase A — calendar pacing + dollar materiality.
    # calendar_pct: float 0..100 — how far through the school year we are
    # at the period end (e.g. April 2026 → 33.3 = 4/12). When zero, the
    # tool couldn't infer a calendar position and pacing columns will
    # show "—" rather than a misleading multiplier.
    # materiality_dollar: int — variance dollars below this floor render
    # muted instead of warn/danger. Default mirrors the input default.
    calendar_pct: float = 0.0
    materiality_dollar: int = 5000


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Header patterns that mark the start of a section
_REVENUE_HDR = re.compile(r"Revenue Recurrent", re.IGNORECASE)
_EXPENDITURE_HDR = re.compile(r"Expenditure Recurrent", re.IGNORECASE)

# Lines we must skip
_SKIP_RE = re.compile(
    r"^("
    r"\d{4}:\w"  # school header e.g. "8819:Melbourne"
    r"|General Ledger"
    r"|Annual Sub Program"
    r"|From Sub Program"
    r"|Revenue Recurrent"
    r"|Expenditure Recurrent"
    r"|Sub Prog\."  # column header
    r"|Revenue totals"
    r"|Expenditure totals"
    r"|\d+ \w+ \d{4}"  # date footer e.g. "3 March 2026"
    r"|\d+ \[GL"  # page/number footer e.g. "1 [GL21157]"
    r")",
    re.IGNORECASE,
)

# Matches a whitespace-delimited field that is a standalone numeric token:
# optional leading minus/dollar, digits with commas, optional decimal part;
# OR a parenthesised value like (500.00).
_NUM_PART_RE = re.compile(r"^[\-\$]?[\d,]+(\.\d+)?$|^\([\d,]+(\.\d+)?\)$")


def _parse_numeric_tokens_from_parts(parts: list[str]) -> list[str]:
    """Filter *parts* to only those that look like numeric tokens."""
    return [p for p in parts if _NUM_PART_RE.match(p)]


def _build_line(
    sub_prog: str,
    title: str,
    tokens: list[str],
    section: str,
) -> SubProgramLine:
    """Build a SubProgramLine from the numeric tokens on a data row.

    Revenue rows:
        Last year actual | Last year budget | Annual budget | YTD | % Budget received
    Expenditure rows:
        Last year actual | Last year budget | Annual budget | YTD | % | Outstanding | Uncommitted

    Column layout varies: some rows omit early columns when zero (particularly
    last-year columns), and YTD is omitted when it is zero (pct then shows 0.00).

    Strategy
    --------
    1. Locate the % token (has a decimal point, 0 <= value <= 9999) by scanning
       right-to-left; this is always present.
    2. ``pre`` = tokens before %; ``post`` = tokens after %.
    3. budget = pre[-2], ytd = pre[-1]  (if len(pre) >= 2; existing logic).
    4. last_year_budget = pre[-3] if len(pre) >= 3 else zero.
    5. last_year_actual  = pre[-4] if len(pre) >= 4 else zero.
    6. outstanding_orders (Expenditure only): post[0] if len(post) >= 2; zero
       if post has only one token (that token is then Uncommitted Balance).
    """
    pct = Decimal("0")
    budget = Decimal("0")
    ytd = Decimal("0")
    last_year_actual = Decimal("0")
    last_year_budget = Decimal("0")
    outstanding_orders = Decimal("0")

    if not tokens:
        remaining = budget - ytd
        faculty = _infer_faculty(sub_prog)
        is_over = ytd > budget if budget != 0 else False
        return SubProgramLine(
            sub_program=sub_prog,
            account=section,
            description=title.strip(),
            budget=budget,
            ytd=ytd,
            remaining=remaining,
            used_pct=pct,
            faculty=faculty,
            is_over=is_over,
        )

    # Locate % token: scan right-to-left for a value with a dot and value <= 9999
    pct_idx: int | None = None
    for idx in range(len(tokens) - 1, -1, -1):
        raw = tokens[idx].replace(",", "")
        if "." in raw:
            try:
                v = Decimal(raw)
                if Decimal("0") <= v <= Decimal("9999"):
                    pct_idx = idx
                    break
            except InvalidOperation:
                pass

    if pct_idx is not None:
        pct = parse_decimal(tokens[pct_idx])
        pre = tokens[:pct_idx]
        post = tokens[pct_idx + 1 :]
    else:
        pre = tokens
        post = []

    # From pre: last = YTD, second-last = Annual budget (if >= 2 tokens)
    if len(pre) >= 2:
        ytd = parse_decimal(pre[-1])
        budget = parse_decimal(pre[-2])
    elif len(pre) == 1:
        # Only one token before %: treat as YTD; budget is zero
        ytd = parse_decimal(pre[-1])
        budget = Decimal("0")
    # else: both remain 0

    # Last-year columns sit immediately before Annual budget in pre.
    if len(pre) >= 3:
        last_year_budget = parse_decimal(pre[-3])
    if len(pre) >= 4:
        last_year_actual = parse_decimal(pre[-4])

    # Outstanding orders: only meaningful for Expenditure rows.
    # When present it is the FIRST token after %; the second (if any) is
    # Uncommitted Balance (derived, not stored).  When outstanding is zero the
    # PDF omits it entirely, leaving only Uncommitted Balance in post.
    if section == "Expenditure" and len(post) >= 2:
        outstanding_orders = parse_decimal(post[0])

    remaining = budget - ytd
    faculty = _infer_faculty(sub_prog)
    is_over = bool(ytd > budget) if budget != Decimal("0") else False

    return SubProgramLine(
        sub_program=sub_prog,
        account=section,
        description=title.strip(),
        budget=budget,
        ytd=ytd,
        remaining=remaining,
        used_pct=pct,
        faculty=faculty,
        is_over=is_over,
        last_year_actual=last_year_actual,
        last_year_budget=last_year_budget,
        outstanding_orders=outstanding_orders,
    )


def _parse_text_lines(text: str, section: str) -> list[SubProgramLine]:
    """Parse data rows from a page's extracted text given its current section."""
    results: list[SubProgramLine] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _SKIP_RE.match(line):
            continue

        # Data row must start with a 4-digit sub-program code
        m = re.match(r"^(\d{4})\s+(.*)", line)
        if not m:
            continue

        sub_prog = m.group(1)
        rest = m.group(2).strip()

        # Split title from numerics using whitespace-delimited tokens.
        # Scan left-to-right; first part that looks like a standalone number
        # marks the boundary between title text and numeric columns.
        parts = rest.split()
        title_parts: list[str] = []
        numeric_start_idx = len(parts)
        for pi, part in enumerate(parts):
            if _NUM_PART_RE.match(part):
                numeric_start_idx = pi
                break
            title_parts.append(part)

        title = " ".join(title_parts)
        numeric_parts = parts[numeric_start_idx:]
        tokens = _parse_numeric_tokens_from_parts(numeric_parts)

        results.append(_build_line(sub_prog, title, tokens, section))

    return results


# Regex to extract the print-date footer: "3 March 2026 13:37 1 [GL21157]"
# Capture group 1: "Month YYYY" string used as the period label.
_FOOTER_DATE_RE = re.compile(
    r"\d{1,2}\s+([A-Z][a-z]+\s+\d{4})\s+\d{2}:\d{2}\s+\d+\s+\[GL",
    re.IGNORECASE,
)


def _extract_period_label(text: str) -> str:
    """Return 'Month YYYY' from the GL21157 page-footer date, or '' if not found.

    The footer format is: ``3 March 2026 13:37 1 [GL21157]``
    This function extracts ``March 2026`` from that pattern.
    """
    m = _FOOTER_DATE_RE.search(text)
    if m:
        return m.group(1)
    return ""


# Round 45 Phase A — calendar position from period label.
#
# The CASES21 GL21157 export prints a footer date like "3 March 2026"; we use
# the month name to compute "calendar percent" — what fraction of the
# (calendar-) year has elapsed by the end of that month. This is the
# denominator for the Pacing column (Used % / Calendar %).
#
# Why calendar year and not Victorian school year (Feb–Dec)? Because
# CASES21 budgets are themselves struck on a calendar year (Jan–Dec — see
# the "Annual budget" column header in the GL21157 export). January spend
# counts against the same annual budget as December spend, so the natural
# pacing denominator is months-elapsed / 12.
_MONTH_TO_PCT: dict[str, float] = {
    "january": 100 / 12,
    "february": 200 / 12,
    "march": 300 / 12,
    "april": 400 / 12,
    "may": 500 / 12,
    "june": 600 / 12,
    "july": 700 / 12,
    "august": 800 / 12,
    "september": 900 / 12,
    "october": 1000 / 12,
    "november": 1100 / 12,
    "december": 100.0,
}


def calendar_pct_from_period_label(period_label: str) -> float:
    """Return calendar-position percent (0..100) for a period label.

    ``period_label`` looks like "March 2026" or "Apr 2026". We match on the
    month token (case-insensitive, prefix-matched against full month names
    so "Apr" → April → 400/12 = 33.33).

    Returns 0.0 when no month is recognisable; callers use that as a
    sentinel for "calendar position unknown — show pacing as em-dash".
    """
    if not period_label:
        return 0.0
    for token in period_label.lower().split():
        for full_name, pct in _MONTH_TO_PCT.items():
            if full_name.startswith(token):
                return pct
    return 0.0


# ---------------------------------------------------------------------------
# Public API -- parse from PDF
# ---------------------------------------------------------------------------


def parse_sub_program_pdf(pdf_path: Path) -> list[SubProgramLine]:
    """Parse a CASES21 GL21157 Annual Sub-Program Budget Report PDF.

    Returns a list of :class:`SubProgramLine` objects, one per data row.
    Skips header/footer rows and total rows.

    Raises :class:`ValueError` if the file appears empty or unrecognised.
    """
    lines, _period = _parse_sub_program_pdf_internal(pdf_path)
    return lines


def parse_sub_program_pdf_with_period(pdf_path: Path) -> tuple[list[SubProgramLine], str]:
    """Parse a GL21157 PDF and return ``(lines, period_label)``.

    ``period_label`` is a string like ``"March 2026"`` extracted from the
    footer date; it is ``""`` if detection fails.
    """
    return _parse_sub_program_pdf_internal(pdf_path)


def _parse_sub_program_pdf_internal(
    pdf_path: Path,
) -> tuple[list[SubProgramLine], str]:
    """Internal implementation shared by the two public PDF parsers."""
    if not pdf_path.exists():
        raise ValueError(f"File not found: {pdf_path}")

    lines: list[SubProgramLine] = []
    section = "Revenue"  # default; updated per-page
    period_label = ""

    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                raise ValueError(
                    "Sub-Program Report PDF appears empty or unrecognised; "
                    "check the file is a CASES21 GL21157 export"
                )

            for page in pdf.pages:
                # Try tables first; fall back to text
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        for row in table:
                            if row and row[0]:
                                cell0 = str(row[0]).strip()
                                if _REVENUE_HDR.search(cell0):
                                    section = "Revenue"
                                elif _EXPENDITURE_HDR.search(cell0):
                                    section = "Expenditure"
                else:
                    text = page.extract_text() or ""
                    # Update section from page headers
                    if _REVENUE_HDR.search(text):
                        section = "Revenue"
                    if _EXPENDITURE_HDR.search(text):
                        section = "Expenditure"

                    # Extract period label from footer (first match wins).
                    if not period_label:
                        period_label = _extract_period_label(text)

                    page_lines = _parse_text_lines(text, section)
                    lines.extend(page_lines)

    except OSError as exc:
        raise ValueError(
            "Sub-Program Report PDF appears empty or unrecognised; "
            "check the file is a CASES21 GL21157 export"
        ) from exc

    if not lines:
        raise ValueError(
            "Sub-Program Report PDF appears empty or unrecognised; "
            "check the file is a CASES21 GL21157 export"
        )

    return lines, period_label


# ---------------------------------------------------------------------------
# Public API -- parse from XLSX (fallback)
# ---------------------------------------------------------------------------


def _get_cell(row: Sequence[Any], idx: int) -> Decimal:
    """Safely extract a Decimal from a row at *idx*."""
    if idx < len(row) and row[idx] is not None:
        raw = str(row[idx]).strip()
        try:
            return parse_decimal(raw)
        except ValueError:
            return Decimal("0")
    return Decimal("0")


def parse_sub_program_xlsx(xlsx_path: Path) -> list[SubProgramLine]:
    """Fallback parser: read a CASES21 XLSX export of the sub-program report.

    Expects columns in order: Sub-Program, Title, [Last year actual],
    [Last year budget], Annual budget, YTD, % Budget [, Outstanding, Uncommitted].
    The first row is treated as a header.
    """
    if not xlsx_path.exists():
        raise ValueError(f"File not found: {xlsx_path}")

    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    try:
        ws = wb[wb.sheetnames[0]]
        rows: list[Any] = [list(r) for r in ws.iter_rows(values_only=True)]
    finally:
        wb.close()

    if len(rows) < 2:
        raise ValueError(
            "Sub-Program Report XLSX appears empty or unrecognised; "
            "check the file is a CASES21 GL21157 export"
        )

    lines: list[SubProgramLine] = []
    section = "Expenditure"

    for row in rows[1:]:
        if not row or row[0] is None:
            continue
        sub_prog = str(row[0]).strip()
        if not sub_prog.isdigit():
            continue

        title = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""

        budget = _get_cell(row, 4)
        ytd = _get_cell(row, 5)
        pct = _get_cell(row, 6)
        remaining = budget - ytd
        faculty = _infer_faculty(sub_prog)
        is_over = bool(ytd > budget) if budget != Decimal("0") else False

        lines.append(
            SubProgramLine(
                sub_program=sub_prog,
                account=section,
                description=title,
                budget=budget,
                ytd=ytd,
                remaining=remaining,
                used_pct=pct,
                faculty=faculty,
                is_over=is_over,
            )
        )

    if not lines:
        raise ValueError(
            "Sub-Program Report XLSX appears empty or unrecognised; "
            "check the file is a CASES21 GL21157 export"
        )

    return lines


# ---------------------------------------------------------------------------
# Public API -- prior-period comments
# ---------------------------------------------------------------------------


def load_prior_period_comments(xlsx_path: Path) -> dict[tuple[str, str], str]:
    """Load per-row commentary from a prior-period comments XLSX.

    Reads every worksheet in the workbook (Revenue + Expenditure sheets in
    a typical export both carry comments), and returns
    ``{(sub_program, second_key): commentary_text}``.  The second key is
    either the account code (if an "Account" header is found) or the
    line title / description (if not).  This keeps the join robust against
    files exported by this tool itself, which intentionally drops the raw
    Account column from the published workbook.

    Bug fixed in Round 21
    ---------------------
    Earlier versions silently defaulted to ``txt_col = 2`` when no
    "comments" header was found.  Column 2 in our own export is
    "Last year actual" — a dollar amount — so users saw last-year-actual
    values copied into the new report's comments column.  We now raise a
    descriptive ValueError instead, listing the headers we did find so
    the user can rename the column in their source file.

    Accepted comment-column synonyms: comment, comments, commentary,
    note, notes, remark, remarks, memo.

    Accepted account-column synonyms: account, account code, gl, gl code.
    If none match, the line title / description column is used as the
    secondary join key.

    Phase D round-trip
    ------------------
    Cells written by Round 51+ carry an optional structured prefix of
    the form ``[Driver: X | Outlook: Y | Action: Z] notes``. We return
    the cell verbatim — :func:`decode_commentary` is applied at the
    consumer side (``generate_report``) so that pre-Phase-D files
    (no prefix) still round-trip cleanly as Notes-only.
    """
    if not xlsx_path.exists():
        raise ValueError(f"Comments file not found: {xlsx_path}")

    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    try:
        # Walk EVERY sheet — exports of this tool produce Revenue and
        # Expenditure as separate sheets and both carry comments.
        per_sheet_rows: list[list[list[Any]]] = [
            [list(r) for r in wb[name].iter_rows(values_only=True)] for name in wb.sheetnames
        ]
    finally:
        wb.close()

    result: dict[tuple[str, str], str] = {}

    # Track whether ANY sheet had a usable header.  If none did, we raise
    # at the end — silent fall-through used to copy budget data into the
    # comments column.
    found_any_comment_col = False
    seen_headers: list[str] = []

    for sheet_rows in per_sheet_rows:
        if not sheet_rows:
            continue
        header = [
            str(c).strip().lower().replace("_", " ") if c is not None else "" for c in sheet_rows[0]
        ]
        seen_headers.extend(h for h in header if h)

        # --- Sub-program column -------------------------------------------------
        sp_col: int | None = None
        for i, h in enumerate(header):
            # "sub prog" matches "Sub Prog." and "Sub-Program" (after the
            # underscore-to-space normalisation above).
            if "sub" in h and ("prog" in h or "program" in h):
                sp_col = i
                break
        if sp_col is None:
            sp_col = 0  # safe fallback — first column is almost always sub-program

        # --- Comment column (synonyms) ------------------------------------------
        # Synonyms list is module-scope (``_COMMENT_SYNONYMS``) so that the
        # bottom-of-function ``raise ValueError`` block can reference it
        # even when every sheet was empty / blank — otherwise we'd hit
        # an UnboundLocalError before surfacing the real "no comments
        # column" message to the user.
        txt_col: int | None = None
        for i, h in enumerate(header):
            if any(syn in h for syn in _COMMENT_SYNONYMS):
                txt_col = i
                break
        if txt_col is None:
            # No comment column on THIS sheet — skip it; we'll raise at the
            # bottom only if NO sheet had one.
            continue
        found_any_comment_col = True

        # --- Account column (synonyms) ------------------------------------------
        # Exported workbooks intentionally drop the raw Account column, so
        # if no "account" header is found we fall back to the Title /
        # Description column (col 1).  This matches our own exports
        # without forcing the user to hand-edit headers.
        acc_synonyms = ("account", " gl", "gl code", "code")
        sec_col: int | None = None
        for i, h in enumerate(header):
            if any(syn in h for syn in acc_synonyms):
                sec_col = i
                break
        if sec_col is None:
            # Fall back to Title / Description column — same column used
            # as the second join key when generating the new report.
            sec_col = 1

        # --- Walk rows ----------------------------------------------------------
        for row in sheet_rows[1:]:
            if not row:
                continue
            sp = str(row[sp_col]).strip() if sp_col < len(row) and row[sp_col] is not None else ""
            sec = (
                str(row[sec_col]).strip() if sec_col < len(row) and row[sec_col] is not None else ""
            )
            txt = (
                str(row[txt_col]).strip() if txt_col < len(row) and row[txt_col] is not None else ""
            )
            # Round 1 fix (R51): strip the formula-injection-guard
            # apostrophe written by ``_write_monthly_sub_program_sheet``
            # when an encoded cell happened to start with ``=``/``+``/
            # ``-``/``@`` (Excel's formula sigils). Excel renders the
            # apostrophe as a "force text" marker but openpyxl returns
            # it verbatim — we strip it back so :func:`decode_commentary`
            # sees the original encoded value and round-trips cleanly
            # without accumulating apostrophes across save→reopen→save
            # cycles.
            if len(txt) >= 2 and txt[0] == "'" and txt[1] in ("=", "+", "-", "@"):
                txt = txt[1:]
            # Skip rows that are clearly not data — sub-program codes are
            # purely numeric.  This stops "Total" / blank header artefacts
            # from polluting the dict.
            if not sp or not sp.isdigit():
                continue
            if sp or sec:
                # If two sheets disagree on the same key, the later one
                # wins — matches the visual reading order in the workbook.
                result[(sp, sec)] = txt

    if not found_any_comment_col:
        seen = ", ".join(sorted(set(h for h in seen_headers if h))) or "(none)"
        raise ValueError(
            "Could not find a comments column in the prior-period file. "
            "Looked for any header containing one of: "
            f"{', '.join(_COMMENT_SYNONYMS)}. "
            f"Headers we found: {seen}. "
            "Rename your comments column to 'Comments' (or one of the "
            "synonyms above) and try again."
        )

    return result


# ---------------------------------------------------------------------------
# XLSX output writer
# ---------------------------------------------------------------------------

# Excel Accounting format -- matches the Jan26 reference file exactly.
_ACCOUNTING_FMT = '_-"$"* #,##0_-;\\-"$"* #,##0_-;_-"$"* "-"??_-;_-@_-'
_PERCENT_FMT = "0.00"
# Round 47 — proper percent format for the new Monthly shape's
# % columns. Cells store the value as a fraction (0.398...) and
# Excel renders it as "39.8%". The legacy ``_PERCENT_FMT`` above
# treats stored 50 as "50.00" and is kept for the legacy Revenue /
# Expense sheets.
_PERCENT_AS_PERCENT_FMT = "0.0%"
_TITLE_FONT = Font(bold=True, size=14)
# Green data bar colour -- matches Jan26 reference (#63C384 with full alpha).
_DATA_BAR_COLOR = "FF63C384"

# Revenue sheet: 8 columns -- no Outstanding Orders column.
_REV_HEADERS = [
    "Sub Prog.",
    "Title",
    "Last year actual",
    "Last year budget",
    "Annual budget",
    "YTD",
    "% Budget received",
    "Comments",
]
_REV_WIDTHS = [10, 43, 13, 14, 17, 15, 13, 60]

# Expenditure sheet: 9 columns -- Outstanding Orders is parsed from the PDF
# and used in the Uncommitted Balance computation (Annual - YTD - Outstanding)
# but NOT displayed as its own column, per user's Q3 spec direction.
_EXP_HEADERS = [
    "Sub Prog.",
    "Title",
    "Last year actual",
    "Last year budget",
    "Annual budget",
    "YTD",
    "% Budget Expended",
    "Uncommitted Balance",
    "Comments",
]
_EXP_WIDTHS = [10, 43, 13, 14, 17, 15, 14, 18, 60]


def _recompute_is_over(
    lines: list[SubProgramLine],
    threshold: float,
    *,
    revenue_threshold: float | None = None,
    expense_threshold: float | None = None,
    calendar_pct: float = 0.0,
    materiality_dollar: int = 5000,
) -> list[SubProgramLine]:
    """Return new SubProgramLine list with is_over + variance + pacing recomputed.

    By default both Revenue and Expenditure rows use the same ``threshold``,
    which preserves backward compatibility with all earlier callers.
    Round 21 added the optional ``revenue_threshold`` / ``expense_threshold``
    keyword-only parameters.  When supplied, a Revenue line is flagged as
    over-budget if ``used_pct > revenue_threshold`` and an Expenditure line
    if ``used_pct > expense_threshold``.

    Round 45 Phase A also (re)computes:

    * ``variance_amount = ytd - budget`` — signed; positive means YTD has
      exceeded the annual budget. Same sign for Revenue and Expense rows;
      account-aware tinting at render time differentiates "over-spent" red
      from "under-collected" amber.
    * ``variance_pct = variance_amount / budget * 100`` — signed; zero
      when budget is zero.
    * ``pacing = used_pct / calendar_pct`` — multiplier; 1.00 = on pace.
      Zero when ``calendar_pct`` is zero (period unknown) so the UI can
      render an em-dash.
    * ``is_material`` — True when ``abs(variance_amount) >= materiality_dollar``.
      Lines below the floor still flag over-budget by percentage but render
      muted in the UI so they don't compete for attention with the genuinely
      large variances.
    """
    from dataclasses import replace as _replace

    rev_th = revenue_threshold if revenue_threshold is not None else threshold
    exp_th = expense_threshold if expense_threshold is not None else threshold
    cal = Decimal(str(calendar_pct)) if calendar_pct > 0 else Decimal("0")
    mat = Decimal(str(materiality_dollar))

    result: list[SubProgramLine] = []
    for ln in lines:
        # Pick the threshold by section.  Account values are always
        # "Revenue" or "Expenditure" (or close variants) — we lower-case
        # and compare prefixes to be tolerant of typos.
        is_revenue = ln.account.lower().startswith("revenue")
        section_th = rev_th if is_revenue else exp_th
        # Round 47 — a sub-program with $0 budget but $X spent has
        # used_pct = 0 from the parser (division-by-zero defended) but
        # is unambiguously over budget. Flag those rows directly so
        # they don't slip past the percentage gate.
        zero_budget_with_spend = ln.budget == Decimal("0") and ln.ytd != Decimal("0")
        new_is_over = float(ln.used_pct) > section_th or zero_budget_with_spend

        new_variance_amount = ln.ytd - ln.budget
        new_variance_pct = (
            (new_variance_amount / ln.budget * Decimal("100"))
            if ln.budget != Decimal("0")
            else Decimal("0")
        )
        new_pacing = (ln.used_pct / cal) if cal > 0 else Decimal("0")
        new_is_material = abs(new_variance_amount) >= mat

        ln = _replace(
            ln,
            is_over=new_is_over,
            variance_amount=new_variance_amount,
            variance_pct=new_variance_pct,
            pacing=new_pacing,
            is_material=new_is_material,
        )
        result.append(ln)
    return result


def _write_sheet(
    ws: Any,
    title: str,
    headers: list[str],
    widths: list[int],
    lines: list[SubProgramLine],
    is_revenue: bool,
) -> None:
    """Populate a single Revenue or Expenditure worksheet."""
    from openpyxl.formatting.rule import DataBarRule
    from openpyxl.worksheet.worksheet import Worksheet

    assert isinstance(ws, Worksheet)
    n_cols = len(headers)

    # Row 1: merged title -- bold, size 14, centred.
    title_cell = ws.cell(row=1, column=1, value=title)
    title_cell.font = _TITLE_FONT
    title_cell.alignment = Alignment(horizontal="center")
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)

    # Row 2: column headers.
    for col_idx, header in enumerate(headers, start=1):
        ws.cell(row=2, column=col_idx, value=header).alignment = Alignment(
            horizontal="left", wrap_text=True
        )

    # Freeze panes so title + header row both stay visible.
    ws.freeze_panes = "A3"

    # Column widths.
    for col_idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Data rows start at row 3.
    percent_col = 7
    for row_idx, line in enumerate(lines, start=3):
        # Round 51 Phase D — encode structured triplet + notes into the
        # single Comments cell. Cells where all four fields are blank
        # come out as empty string (matches pre-Phase-D behaviour).
        encoded_comment = encode_commentary(
            line.commentary,
            driver=line.commentary_driver,
            outlook=line.commentary_outlook,
            action=line.commentary_action,
        )
        if is_revenue:
            row_values: list[Any] = [
                line.sub_program,
                line.description,
                float(line.last_year_actual),
                float(line.last_year_budget),
                float(line.budget),
                float(line.ytd),
                float(line.used_pct),
                encoded_comment,
            ]
            # Accounting format on Annual budget (col 5) and YTD (col 6).
            currency_cols = {5, 6}
        else:
            # Uncommitted Balance = Annual budget - YTD - Outstanding Orders.
            # Outstanding Orders is parsed from the PDF but not surfaced as a
            # column (per user spec Q3); it only contributes to this derivation.
            uncommitted = line.budget - line.ytd - line.outstanding_orders
            row_values = [
                line.sub_program,
                line.description,
                float(line.last_year_actual),
                float(line.last_year_budget),
                float(line.budget),
                float(line.ytd),
                float(line.used_pct),
                float(uncommitted),
                encoded_comment,
            ]
            # Accounting format on Annual budget (col 5), YTD (col 6).
            currency_cols = {5, 6}

        for col_idx, val in enumerate(row_values, start=1):
            c = ws.cell(row=row_idx, column=col_idx, value=val)
            if col_idx in currency_cols:
                c.number_format = _ACCOUNTING_FMT
            elif col_idx == percent_col:
                c.number_format = _PERCENT_FMT
            # Pink row fill for over-budget rows (threshold-aware is_over).
            if line.is_over:
                c.fill = _OVER_FILL

    # Conditional formatting on the % Budget column (G = col 7).
    if lines:
        last_data_row = 2 + len(lines)
        pct_col_letter = get_column_letter(percent_col)
        rng = f"{pct_col_letter}3:{pct_col_letter}{last_data_row}"

        # Data bar: green, 0--110 (matches Revenue sheet in Jan26 reference).
        ws.conditional_formatting.add(
            rng,
            DataBarRule(  # type: ignore[no-untyped-call]
                start_type="num",
                start_value=0,
                end_type="num",
                end_value=110,
                color=_DATA_BAR_COLOR,
                showValue=True,
            ),
        )


def _sheet_title(base: str, period_label: str, suffix: str) -> str:
    """Compose a sheet title, gracefully omitting the period when absent."""
    if period_label:
        return f"{base} - {period_label} {suffix}"
    return f"{base} - {suffix}"


def _write_xlsx(
    lines: list[SubProgramLine],
    output_file: Path,
    period_label: str = "",
    over_budget_threshold: float = 101.0,
    *,
    include_combined: bool = False,
    materiality_dollar: int = 5000,
) -> None:
    """Write the report to an XLSX with the Monthly Sub Program Report shape.

    Round 38 — replaces the prior 2-sheet (Revenue / Expenditure) layout
    with a single sheet matching the school's own Monthly Sub Program
    Report workbook: 12 columns, one row per sub-program, with the
    canonical Vic-school finance KPIs (carry-forward, revenue and
    expenditure budget + YTD, outstanding orders, available balance,
    available-balance %, revenue % received, comments).

    Sub-programs whose Available Balance YTD is negative (over-drawn
    given carry-forward + revenue collected to date − expenditure
    YTD − outstanding orders) get the canonical pink ``HL_MISMATCH``
    fill so the user can scan for trouble spots at a glance.

    The ``include_combined`` and ``over_budget_threshold`` arguments
    are accepted for backward compatibility with existing call sites
    but no longer affect the output (the new shape is itself the
    "combined" view by sub-program).
    """
    del include_combined, over_budget_threshold  # no-op for the new shape

    from openpyxl import Workbook

    wb = Workbook()
    default_ws = wb.active
    if default_ws is not None:
        wb.remove(default_ws)

    ws = wb.create_sheet("Sub Program Report")
    _write_monthly_sub_program_sheet(ws, lines, period_label, materiality_dollar)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_file)


def _write_monthly_sub_program_sheet(
    ws: Any,
    lines: list[SubProgramLine],
    period_label: str,
    materiality_dollar: int = 5000,
) -> None:
    """Round 38 — Monthly Sub Program Report shape.

    12-column per-sub-program output matching the school's own
    "Monthly Sub Program Report" workbook:

    1.  CODE                                 sub_program code
    2.  PROGRAM NAME                         description
    3.  Funds from Previous Years (Funds)    carry-forward (blank — not in PDF)
    4.  Budget Revenue {year}                annual revenue budget
    5.  Total Budget Allocation Expenditure  annual expenditure budget
    6.  Revenue YTD                          revenue collected so far
    7.  Expenditure YTD                      expenditure spent so far
    8.  Less outstanding orders              committed-but-not-paid
    9.  Available Balance YTD                rev_y − exp_y − orders
    10. Available Balance % YTD              available / expenditure budget
    11. Revenue Budget % Received YTD        rev_y / revenue budget
    12. Comments                             commentary

    Rows where the Available Balance YTD is negative get the pink
    ``_OVER_FILL`` (HL_MISMATCH) — the canonical "needs attention"
    indicator across the toolkit.

    The "Funds from Previous Years" column is left blank: the
    GL21157 PDF doesn't carry rolled-forward surplus / deficit data,
    and inferring it would risk producing wrong numbers.  Schools
    that need the column populated can open the file and fill it in
    by hand from their council records.
    """
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.worksheet import Worksheet

    assert isinstance(ws, Worksheet)

    # ----- Aggregate per-sub-program -----
    rev_b: dict[str, Decimal] = {}
    exp_b: dict[str, Decimal] = {}
    rev_y: dict[str, Decimal] = {}
    exp_y: dict[str, Decimal] = {}
    orders: dict[str, Decimal] = {}
    desc: dict[str, str] = {}
    # Round 51 Phase D Round-1 fix — atomic per-sub-program commentary
    # aggregation. Pre-fix the four fields (notes / driver / outlook /
    # action) were each independently "first non-empty wins" across
    # Account-rows of the same sub-program — which produced
    # cross-row data fabrication (Action from row B alongside Notes
    # from row A). Now we adopt the WHOLE 4-tuple from the first row
    # that contributes ANY commentary content, keeping the
    # categorisation atomic and traceable to a single source row.
    commentary_tuple: dict[str, tuple[str, str, str, str]] = {}

    for ln in lines:
        sp = ln.sub_program
        kind = ln.account.lower()
        if kind.startswith("revenue"):
            rev_b[sp] = rev_b.get(sp, Decimal("0")) + ln.budget
            rev_y[sp] = rev_y.get(sp, Decimal("0")) + ln.ytd
        elif kind.startswith("expenditure"):
            exp_b[sp] = exp_b.get(sp, Decimal("0")) + ln.budget
            exp_y[sp] = exp_y.get(sp, Decimal("0")) + ln.ytd
            # Outstanding orders are an expenditure-side concept; aggregate
            # across all expenditure account-rows for the sub-program.
            if ln.outstanding_orders:
                orders[sp] = orders.get(sp, Decimal("0")) + ln.outstanding_orders
        # First non-empty description / commentary wins (consistent
        # with how the in-app Combined view picks its description).
        if ln.description and sp not in desc:
            desc[sp] = ln.description
        # Atomic 4-tuple adoption: the row that wins is the first one
        # that contributes ANY commentary content for the sub-program.
        if sp not in commentary_tuple and (
            ln.commentary or ln.commentary_driver or ln.commentary_outlook or ln.commentary_action
        ):
            commentary_tuple[sp] = (
                ln.commentary,
                ln.commentary_driver,
                ln.commentary_outlook,
                ln.commentary_action,
            )

    sub_programs = sorted(set(rev_b.keys()) | set(exp_b.keys()))

    # ----- Title row (merged across 12 cols) -----
    base = "Monthly Sub Program Report"
    title = _sheet_title(base, period_label, "")
    title_cell = ws.cell(row=1, column=1, value=title)
    title_cell.font = _TITLE_FONT
    title_cell.alignment = Alignment(horizontal="center")
    # Round 53 F1: title spans 13 columns now (Status added at col 13).
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=13)

    # ----- Header row -----
    # Year label for the budget headers — extracted from period_label
    # (e.g. "Apr 2026" → "2026"); falls back to a blank year suffix.
    year_label = ""
    if period_label:
        for tok in period_label.split():
            if tok.isdigit() and len(tok) == 4:
                year_label = tok
                break
    rev_budget_header = f"Budget Revenue {year_label}".strip()
    exp_budget_header = f"Total Budget Allocation Expenditure {year_label}".strip()

    headers = [
        "CODE",
        "PROGRAM NAME",
        "Funds from Previous Years (Funds) ",
        rev_budget_header,
        exp_budget_header,
        "Revenue YTD",
        "Expenditure YTD",
        "Less outstanding orders",
        "Available Balance YTD",
        "Available Balance % YTD",
        "Revenue Budget % Received YTD",
        "Comments",
        # Round 53 F1 — Status pill (col 13). Plain-English summary so a
        # non-finance reader can scan the rightmost column and instantly
        # see which sub-programs need attention.
        "Status",
    ]
    # R2 fix: Comments width reduced 50 → 40 to relieve print-width
    # compression risk. Total widths sum 248 → 238 char-units; landscape
    # A4 fit-to-width has ~277 char-units of usable space at default
    # margins, so the new 238 leaves ~14% margin (was 11%). Long prose
    # still wraps via wrap_text — just to slightly taller rows, which
    # the row-height heuristic handles.
    widths = [8, 32, 14, 16, 22, 14, 14, 14, 16, 12, 14, 40, 22]
    for col_idx, (header, width) in enumerate(zip(headers, widths, strict=True), start=1):
        cell = ws.cell(row=2, column=col_idx, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # ----- Data rows -----
    for row_idx, sp in enumerate(sub_programs, start=3):
        ry = rev_y.get(sp, Decimal("0"))
        ey = exp_y.get(sp, Decimal("0"))
        rb = rev_b.get(sp, Decimal("0"))
        eb = exp_b.get(sp, Decimal("0"))
        oo = orders.get(sp, Decimal("0"))
        # Carry-forward isn't in the PDF; we leave the cell blank
        # rather than guessing a zero (a blank cell signals "not
        # known", which is honest; a zero would be a wrong number).
        carry_fwd: Decimal | None = None
        # Available balance: rev_y + carry_fwd − exp_y − orders.
        # carry_fwd defaults to zero for the calc.
        cf_for_calc = carry_fwd if carry_fwd is not None else Decimal("0")
        available = cf_for_calc + ry - ey - oo
        # Available % = available / expenditure_budget.  Schools track
        # "what fraction of my annual budget am I yet to commit".  Use
        # ``!= 0`` rather than ``> 0`` so the rare negative-budget rows
        # (cost-recovery accounts that net to a negative annual figure)
        # still produce a percentage; otherwise we'd silently emit a
        # blank cell for valid CASES21 data.
        avail_pct: Decimal | None = available / eb if eb != 0 else None
        # Revenue % received = rev_y / revenue_budget.
        rev_pct: Decimal | None = ry / rb if rb != 0 else None

        ws.cell(row=row_idx, column=1, value=_to_int_or_str(sp))
        ws.cell(row=row_idx, column=2, value=desc.get(sp, ""))
        # Carry-forward cell stays blank.
        if carry_fwd is not None:
            c = ws.cell(row=row_idx, column=3, value=float(carry_fwd))
            c.number_format = _ACCOUNTING_FMT

        for col_idx, value in (
            (4, rb),
            (5, eb),
            (6, ry),
            (7, ey),
            (8, oo),
            (9, available),
        ):
            c = ws.cell(row=row_idx, column=col_idx, value=float(value))
            c.number_format = _ACCOUNTING_FMT

        # Percentages — written as fractions and formatted with the
        # Excel percent format so they render as "39.8%" not "0.398".
        # Round 47 fix: number_format was missing pre-fix, principals
        # saw raw decimals.
        # Round 53 F1 (Move F): cap unbounded percents at ±999% for
        # display so a non-finance reader sees a finite number.
        # R1 fix: when capped, write a text marker (">999%" /
        # "<-999%") instead of the capped fraction — the marker
        # SURVIVES print, while the original cell-comment tooltip is
        # screen-only and invisible on the printed copy. Cell comment
        # ALSO attached for screen readers who want exact value.
        from openpyxl.comments import Comment

        def _write_capped_percent(r: int, cell_col: int, raw_pct: Decimal, label: str) -> None:
            capped = cap_percent_for_display(raw_pct)
            assert capped is not None
            cell = ws.cell(row=r, column=cell_col)
            if capped != raw_pct:
                # Render as text marker so the cap is visible on print.
                marker = ">999%" if raw_pct > 0 else "<-999%"
                cell.value = marker
                cell.number_format = "@"
                cell.comment = Comment(
                    f"Capped from {float(raw_pct) * 100:.1f}% for display ({label}).",
                    "School Tool",
                )
            else:
                cell.value = float(capped)
                cell.number_format = _PERCENT_AS_PERCENT_FMT

        if avail_pct is not None:
            _write_capped_percent(row_idx, 10, avail_pct, "Available Balance %")
        if rev_pct is not None:
            _write_capped_percent(row_idx, 11, rev_pct, "Revenue % Received")

        # Round 53 F1 (Move B) — Status pill at column 13. Per-
        # sub-program plain-English summary computed from the same
        # available-balance value the Available Balance YTD column
        # carries, so the pill and the dollar number always tell the
        # same story. R1 fix: also pass annual_rev_budget so the
        # Spent-without-budget gate can distinguish capital-spend-
        # without-approval from rev-only / cost-recovery programs.
        status = compute_status_pill(
            available=available,
            annual_exp_budget=eb,
            annual_rev_budget=rb,
            rev_ytd=ry,
            exp_ytd=ey,
            materiality_dollar=materiality_dollar,
            calendar_pct=calendar_pct_from_period_label(period_label),
        )
        status_cell = ws.cell(row=row_idx, column=13, value=status)
        # Bold the call-for-attention pills (Urgent / Significant /
        # Spent-without-budget / No-spend-yet) so they stand out on
        # the printed page. R1 fix added No-spend-yet to the bold set
        # — it's the row a council member would ask about.
        if status in (
            _STATUS_URGENT,
            _STATUS_MATERIAL,
            _STATUS_SPENT_WITHOUT_BUDGET,
            _STATUS_NO_SPEND_YET,
        ):
            status_cell.font = Font(bold=True)

        # Round 53 F1 (Move E) — render structured triplet + notes as
        # plain-English prose. Replaces the Round-51 prefix encoding for
        # the visible cell. Pre-Round-53 prefix-encoded cells still
        # round-trip through ``load_prior_period_comments`` +
        # ``decode_commentary`` (the reader handles both forms).
        # R1 fix: when prose is empty AND the Status is non-OK, auto-
        # fill with a "(no commentary recorded)" placeholder so the
        # cell doesn't print as a contradiction (urgent status with
        # blank Comments looks like the BM ignored the alert).
        c_notes, c_driver, c_outlook, c_action = commentary_tuple.get(sp, ("", "", "", ""))
        prose = render_commentary_prose(
            notes=c_notes,
            driver=c_driver,
            outlook=c_outlook,
            action=c_action,
        )
        if not prose and status in (
            _STATUS_URGENT,
            _STATUS_MATERIAL,
            _STATUS_SPENT_WITHOUT_BUDGET,
            _STATUS_NO_SPEND_YET,
        ):
            # R2 fix: differentiate the auto-fill text by status. A
            # parenthesised "(no commentary recorded)" reads as
            # archival absence to a council reader — passive, system-
            # noted. For genuinely-attention statuses we want an
            # imperative cue that the BM has a to-do. ``No spend yet``
            # is left as the parenthesised form because the absence
            # IS the literal point (the program hasn't transacted).
            if status == _STATUS_NO_SPEND_YET:
                prose = "(no commentary recorded)"
            else:
                prose = "Action needed: add commentary."
        # Defensive Excel-formula-injection guard. A user typing
        # ``=SUM(...)`` etc. into Notes would otherwise get
        # auto-evaluated by Excel on file open, surfacing as ``#NAME?``
        # or unexpected numerics. We prepend an apostrophe — Excel's
        # canonical "force text" sigil. The apostrophe doesn't render
        # in Excel display but is preserved in the stored value, and
        # ``load_prior_period_comments`` strips it on read.
        if prose and prose[0] in ("=", "+", "-", "@"):
            comment_cell = ws.cell(row=row_idx, column=12, value="'" + prose)
        else:
            comment_cell = ws.cell(row=row_idx, column=12, value=prose)
        # Round 47: long commentary cells need wrap_text or they
        # overflow horizontally and push the print width past one page.
        comment_cell.alignment = Alignment(wrap_text=True, vertical="top")
        # Round 51 R1 fix: force text format so a user pasting
        # "01/04/2026 reviewed" doesn't get auto-coerced into an Excel
        # date by General-format inference on re-save.
        comment_cell.number_format = "@"
        # R1 fix: explicit row height so multi-line prose doesn't clip
        # on print. Default Excel row height is 15pt — shows only the
        # first line. Heuristic: ~50 chars per visual line at column
        # width 50, ~15pt per line.
        # R2 fix: Comments column width is 40 (was 50 in F1; reduced
        # to relieve print-width compression). Row-height heuristic
        # tracks the same width so multi-line prose still gets the
        # correct row height for print.
        col_12_width = 40
        prose_visual_lines = max(1, (len(prose) + col_12_width - 1) // col_12_width)
        if prose_visual_lines > 1:
            ws.row_dimensions[row_idx].height = 15 * prose_visual_lines

        # Pink fill on rows where Available Balance YTD is negative
        # AND the magnitude meets the dollar materiality floor —
        # mirrors the in-app row_style behaviour so a $50 over a $30
        # budget doesn't paint pink in the printed copy. Round 47.
        # Round 53 F1: extended ``range(1, 14)`` paints cols 1..13
        # inclusive, so the new Status column also gets the row tint.
        if available < 0 and abs(available) >= materiality_dollar:
            for col_idx in range(1, 14):
                ws.cell(row=row_idx, column=col_idx).fill = _OVER_FILL

    # Freeze panes below the header so the column titles stay
    # visible while the user scrolls through sub-programs.
    ws.freeze_panes = "A3"

    # Round 47 — print page setup. Without this the 12-column report
    # overflows portrait A4 onto 3-4 pages and rows split across page
    # breaks. Schools print these for council meetings.
    from openpyxl.worksheet.page import PageMargins

    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    page_setup_pr = ws.sheet_properties.pageSetUpPr
    if page_setup_pr is not None:
        page_setup_pr.fitToPage = True
    ws.print_title_rows = "1:2"  # repeat title + header on every printed page
    ws.page_margins = PageMargins(left=0.4, right=0.4, top=0.5, bottom=0.5, header=0.3, footer=0.3)
    # Period in the centre of the page header; page-N-of-N at right
    # of the footer; tool-version footer left so the artefact is
    # forensically traceable.
    # mypy can't prove ws.oddHeader / ws.oddFooter are non-None (openpyxl
    # types them as Optional even though they're always populated on a
    # real Worksheet), so we guard explicitly to avoid noise.
    odd_header = ws.oddHeader
    odd_footer = ws.oddFooter
    if period_label and odd_header is not None and odd_header.center is not None:
        odd_header.center.text = f"Sub-Program Budget Report — {period_label}"
    if odd_footer is not None:
        if odd_footer.left is not None:
            odd_footer.left.text = "Generated by School Tool"
        if odd_footer.right is not None:
            odd_footer.right.text = "Page &P of &N"


def _to_int_or_str(code: str) -> Any:
    """Render a sub-program code as an int when possible, else as str.

    The Monthly Sub Program Report stores codes as integers (4101,
    1320, …) which Excel sorts and right-aligns.  Codes that are
    non-numeric (rare — e.g. "EI/SP" sentinels) stay as strings.
    """
    text = str(code).strip()
    if text.isdigit():
        return int(text)
    return text


def _write_combined_sheet(ws: Any, lines: list[SubProgramLine], period_label: str) -> None:
    """Round 26 — append a per-sub-program Combined / YTD sheet.

    Columns: Sub-program · Description · Revenue YTD · Expense YTD ·
    Net YTD · Annual budget net.  Sorted by Net YTD ascending so the
    biggest school-funded gaps surface first.  Subsidised rows
    (Net YTD < 0) carry the canonical pink HL_MISMATCH fill.
    """
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.worksheet import Worksheet

    assert isinstance(ws, Worksheet)

    rev_b: dict[str, Decimal] = {}
    exp_b: dict[str, Decimal] = {}
    rev_y: dict[str, Decimal] = {}
    exp_y: dict[str, Decimal] = {}
    desc: dict[str, str] = {}
    for ln in lines:
        sp = ln.sub_program
        if ln.account.lower().startswith("revenue"):
            rev_b[sp] = rev_b.get(sp, Decimal("0")) + ln.budget
            rev_y[sp] = rev_y.get(sp, Decimal("0")) + ln.ytd
        elif ln.account.lower().startswith("expenditure"):
            exp_b[sp] = exp_b.get(sp, Decimal("0")) + ln.budget
            exp_y[sp] = exp_y.get(sp, Decimal("0")) + ln.ytd
        if ln.description and sp not in desc:
            desc[sp] = ln.description

    sub_programs = sorted(set(rev_b.keys()) | set(exp_b.keys()))
    # Pre-compute & sort by Net YTD ascending (biggest deficit first).
    rows: list[tuple[str, str, Decimal, Decimal, Decimal, Decimal]] = []
    for sp in sub_programs:
        ry = rev_y.get(sp, Decimal("0"))
        ey = exp_y.get(sp, Decimal("0"))
        rb = rev_b.get(sp, Decimal("0"))
        eb = exp_b.get(sp, Decimal("0"))
        rows.append((sp, desc.get(sp, ""), ry, ey, ry - ey, rb - eb))
    rows.sort(key=lambda r: r[4])

    # Title row (merged).
    title = _sheet_title("Annual Sub-Program Budget Report", period_label, "Combined")
    title_cell = ws.cell(row=1, column=1, value=title)
    title_cell.font = _TITLE_FONT
    title_cell.alignment = Alignment(horizontal="center")
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=6)

    # Header row.
    headers = [
        "Sub-program",
        "Description",
        "Revenue YTD",
        "Expense YTD",
        "Net YTD",
        "Annual budget net",
    ]
    widths = [12, 38, 14, 14, 16, 18]
    for col_idx, (header, width) in enumerate(zip(headers, widths, strict=True), start=1):
        cell = ws.cell(row=2, column=col_idx, value=header)
        cell.font = Font(bold=True)
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Data rows.
    for row_idx, (sp, description, ry, ey, net_ytd, net_budget) in enumerate(rows, start=3):
        ws.cell(row=row_idx, column=1, value=sp)
        ws.cell(row=row_idx, column=2, value=description)
        for col_idx, value in enumerate(
            (float(ry), float(ey), float(net_ytd), float(net_budget)), start=3
        ):
            c = ws.cell(row=row_idx, column=col_idx, value=value)
            c.number_format = _ACCOUNTING_FMT

        # Pink fill on subsidised rows (Net YTD < 0) — same HL_MISMATCH
        # token used by the over-budget rows on the other sheets.
        if net_ytd < 0:
            for col_idx in range(1, 7):
                ws.cell(row=row_idx, column=col_idx).fill = _OVER_FILL

    # Freeze panes below the headers.
    ws.freeze_panes = "A3"


# ---------------------------------------------------------------------------
# Public API -- generate_report
# ---------------------------------------------------------------------------


def generate_report(
    report_file: Path,
    comments_file: Path | None,
    output_file: Path,
    progress: ProgressFn,
    over_budget_threshold: float = 101.0,
    write_xlsx: bool = True,
    *,
    revenue_threshold: float | None = None,
    expense_threshold: float | None = None,
    materiality_dollar: int = 5000,
) -> ReportSummary:
    """Orchestrate parse + comment join + optional XLSX write.

    Parameters
    ----------
    report_file:
        CASES21 GL21157 PDF (or XLSX fallback).
    comments_file:
        Optional prior-period commentary workbook.
    output_file:
        Destination ``.xlsx`` path (used only when ``write_xlsx=True``).
    progress:
        Callback ``(percent: int, message: str) -> None``.
    over_budget_threshold:
        Combined threshold applied to BOTH Revenue and Expenditure when
        the per-section overrides below are not supplied.  Kept for
        backward compatibility with all earlier callers.
    revenue_threshold, expense_threshold:
        Round 21 — optional per-section thresholds.  When supplied they
        override ``over_budget_threshold`` for that section.  Schools
        often want a different tolerance on Revenue (over-collecting
        is rarely a problem) than on Expenditure (over-running is the
        whole point of the report).
    write_xlsx:
        When True (default), write the XLSX workbook to ``output_file``.
        Pass False to skip the write step (e.g. for the preview-then-export
        two-phase flow in Sub-Program tool v2).
    """
    rev_th = revenue_threshold if revenue_threshold is not None else over_budget_threshold
    exp_th = expense_threshold if expense_threshold is not None else over_budget_threshold
    progress(10, "Reading PDF…")

    period_label = ""
    suffix = report_file.suffix.lower()
    if suffix == ".pdf":
        lines, period_label = parse_sub_program_pdf_with_period(report_file)
    elif suffix in {".xlsx", ".xlsm"}:
        lines = parse_sub_program_xlsx(report_file)
    else:
        raise ValueError(
            f"Unsupported report file format: {suffix!r}. Please supply a .pdf or .xlsx file."
        )

    progress(40, "Joining commentary…")

    comments: dict[tuple[str, str], str] = {}
    if comments_file is not None:
        comments = load_prior_period_comments(comments_file)

    final_lines: list[SubProgramLine] = []
    from dataclasses import replace as _replace

    for ln in lines:
        # Round 51 Phase D — decode the prior-period cell into the
        # structured triplet + notes. Pre-Phase-D files (no prefix)
        # round-trip as Notes-only with the three dropdowns blank.
        raw = comments.get((ln.sub_program, ln.account), "")
        if not raw:
            raw = comments.get((ln.sub_program, ln.description), "")
        notes, driver, outlook, action = decode_commentary(raw)
        if (
            notes != ln.commentary
            or driver != ln.commentary_driver
            or outlook != ln.commentary_outlook
            or action != ln.commentary_action
        ):
            ln = _replace(
                ln,
                commentary=notes,
                commentary_driver=driver,
                commentary_outlook=outlook,
                commentary_action=action,
            )
        final_lines.append(ln)

    # Round 45 Phase A - calendar pacing: derive % of year elapsed from the
    # period label (e.g. "April 2026" -> 33.3) so Pacing column has a denom.
    calendar_pct = calendar_pct_from_period_label(period_label)

    final_lines = _recompute_is_over(
        final_lines,
        over_budget_threshold,
        revenue_threshold=rev_th,
        expense_threshold=exp_th,
        calendar_pct=calendar_pct,
        materiality_dollar=materiality_dollar,
    )

    if write_xlsx:
        progress(70, "Writing workbook...")
        _write_xlsx(
            final_lines,
            output_file,
            period_label=period_label,
            over_budget_threshold=over_budget_threshold,
            materiality_dollar=materiality_dollar,
        )
    else:
        progress(70, "Preparing preview...")

    over_budget_lines = [ln for ln in final_lines if ln.is_over]
    total_budget = sum((ln.budget for ln in final_lines), Decimal("0"))
    total_ytd = sum((ln.ytd for ln in final_lines), Decimal("0"))

    progress(100, "Done")

    faculty_counts: dict[str, int] = {}
    faculty_budget: dict[str, Decimal] = {}
    faculty_ytd: dict[str, Decimal] = {}
    for ln in final_lines:
        key = ln.faculty or "Unknown"
        faculty_counts[key] = faculty_counts.get(key, 0) + 1
        faculty_budget[key] = faculty_budget.get(key, Decimal("0")) + ln.budget
        faculty_ytd[key] = faculty_ytd.get(key, Decimal("0")) + ln.ytd

    faculty_used_pct: dict[str, Decimal] = {
        k: (faculty_ytd[k] / faculty_budget[k] * Decimal("100"))
        if faculty_budget[k] != Decimal("0")
        else Decimal("0")
        for k in sorted(faculty_budget.keys())
    }

    return ReportSummary(
        lines=final_lines,
        faculty_counts=faculty_counts,
        over_budget_lines=over_budget_lines,
        total_budget=total_budget,
        total_ytd=total_ytd,
        output_path=output_file,
        faculty_budget=faculty_budget,
        faculty_used_pct=faculty_used_pct,
        period_label=period_label,
        over_budget_threshold=over_budget_threshold,
        revenue_threshold=revenue_threshold or over_budget_threshold,
        expense_threshold=expense_threshold or over_budget_threshold,
        calendar_pct=calendar_pct,
        materiality_dollar=materiality_dollar,
    )
