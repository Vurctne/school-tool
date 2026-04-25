from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SecurityCodeBreakdown:
    sin: int
    amount_raw: int  # amount × 100
    day: int
    month: int
    year_two_digit: int
    code: int


def compute_security_code(
    sin: int,
    amount_cents: int,
    d: date,
) -> SecurityCodeBreakdown:
    """Westpac HYIA security code per DoE spec (Updated May 2022).

    ``amount_cents`` is the AUD amount in integer cents (e.g. $20,000.00 → 2_000_000).
    ``d`` is the date of request; year is taken modulo 100.

    Raises ValueError if sin < 0 or amount_cents < 0.
    """
    if sin < 0:
        raise ValueError(f"SIN must be non-negative, got {sin!r}")
    if amount_cents < 0:
        raise ValueError(f"amount_cents must be non-negative, got {amount_cents!r}")

    day = d.day
    month = d.month
    year_two_digit = d.year % 100

    code = sin + amount_cents + day + month + year_two_digit

    return SecurityCodeBreakdown(
        sin=sin,
        amount_raw=amount_cents,
        day=day,
        month=month,
        year_two_digit=year_two_digit,
        code=code,
    )


_CURRENCY_RE = re.compile(r"^\s*\$?\s*([\d,]+(?:\.\d{1,2})?)\s*$")


def parse_currency(text: str) -> int:
    """Parse a currency string into integer cents.

    Accepts formats like ``"$20,000.00"``, ``"20000"``, ``"20,000.00"``,
    ``"1.23"``. Strips leading/trailing whitespace, ``$``, and commas.

    Raises ValueError for negative values, non-numeric input, or empty input.
    """
    stripped = text.strip()

    # Reject explicit negatives before any other processing
    inner = stripped[1:].lstrip() if stripped.startswith("$") else stripped
    if inner.startswith("-"):
        raise ValueError(f"Amount must be non-negative, got {text!r}")

    m = _CURRENCY_RE.match(stripped)
    if not m:
        raise ValueError(f"Cannot parse {text!r} as a currency amount")

    numeric_str = m.group(1).replace(",", "")

    if "." in numeric_str:
        integer_part, decimal_part = numeric_str.split(".")
        # Normalise to exactly 2 decimal places
        decimal_part = decimal_part.ljust(2, "0")[:2]
    else:
        integer_part = numeric_str
        decimal_part = "00"

    cents = int(integer_part) * 100 + int(decimal_part)
    return cents
