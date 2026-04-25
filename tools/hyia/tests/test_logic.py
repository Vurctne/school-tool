from __future__ import annotations

from datetime import date

import pytest

from tools.hyia.logic import SecurityCodeBreakdown, compute_security_code, parse_currency


def test_doe_worked_example() -> None:
    """SIN=12345, Amount=$20,000.00, Date=16/02/07 → 2012370."""
    bd = compute_security_code(12345, 2_000_000, date(2007, 2, 16))
    assert bd.code == 2_012_370


def test_small_numbers() -> None:
    """54321 + 1 + 1 + 1 + 26 = 54350."""
    bd = compute_security_code(54321, 1, date(2026, 1, 1))
    assert bd.code == 54350


def test_year_2000() -> None:
    """11111 + 100 + 15 + 6 + 0 = 11232."""
    bd = compute_security_code(11111, 100, date(2000, 6, 15))
    assert bd.code == 11232


def test_year_1999() -> None:
    """11111 + 100 + 31 + 12 + 99 = 11353."""
    bd = compute_security_code(11111, 100, date(1999, 12, 31))
    assert bd.code == 11353


def test_large_amount() -> None:
    """99999 + 50_000_000 + 23 + 4 + 26 = 50_100_052."""
    bd = compute_security_code(99999, 500_000_00, date(2026, 4, 23))
    assert bd.code == 50_100_052


def test_rejects_negative_amount() -> None:
    with pytest.raises(ValueError):
        parse_currency("-100")


def test_rejects_negative_sin() -> None:
    with pytest.raises(ValueError):
        compute_security_code(-1, 100, date.today())


def test_parse_currency_formats() -> None:
    assert parse_currency("$20,000.00") == 2_000_000
    assert parse_currency("20000") == 2_000_000
    assert parse_currency("1.23") == 123
    assert parse_currency("1,234.56") == 123456


def test_breakdown_fields() -> None:
    bd = compute_security_code(12345, 2_000_000, date(2007, 2, 16))
    assert isinstance(bd, SecurityCodeBreakdown)
    assert bd.sin == 12345
    assert bd.amount_raw == 2_000_000
    assert bd.day == 16
    assert bd.month == 2
    assert bd.year_two_digit == 7
    assert bd.code == 2_012_370
