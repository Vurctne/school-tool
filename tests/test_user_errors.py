"""Tests for toolkit/user_errors.py — the plain-English error translator."""

from __future__ import annotations

from pathlib import Path

from toolkit.user_errors import FriendlyError, friendly_error

# ---------------------------------------------------------------------------
# Generic shape
# ---------------------------------------------------------------------------


class TestShape:
    def test_returns_friendly_error_dataclass(self) -> None:
        result = friendly_error(RuntimeError("boom"))
        assert isinstance(result, FriendlyError)
        # All four fields are non-empty strings.
        assert result.banner
        assert result.message
        assert result.advice
        assert result.technical

    def test_technical_keeps_original_python_detail(self) -> None:
        # Support staff need the original message to triage — it should
        # appear in `technical` even when the user-facing copy is simplified.
        exc = ValueError("File not found: /tmp/xyz.pdf")
        result = friendly_error(exc)
        assert "ValueError" in result.technical
        assert "/tmp/xyz.pdf" in result.technical

    def test_no_python_typenames_in_user_facing_strings(self) -> None:
        # The banner / message / advice should never expose words like
        # "ValueError", "RuntimeError", or "Traceback".
        exc = ValueError("File not found: /tmp/foo.pdf")
        result = friendly_error(exc)
        for field in (result.banner, result.message, result.advice):
            assert "ValueError" not in field
            assert "RuntimeError" not in field
            assert "Traceback" not in field


# ---------------------------------------------------------------------------
# Specific rules
# ---------------------------------------------------------------------------


class TestFileNotFound:
    def test_filenotfounderror_type_match(self) -> None:
        result = friendly_error(FileNotFoundError(2, "No such file", "/tmp/x"))
        assert "couldn't find" in result.banner.lower()
        assert "file picker" in result.advice.lower()

    def test_text_match_from_logic_layer(self) -> None:
        # Our logic.py raises ValueError("File not found: …") in many
        # places — make sure the text-match path hits.
        result = friendly_error(ValueError("File not found: /foo/bar.pdf"))
        assert "couldn't find" in result.banner.lower()


class TestFileLocked:
    def test_permission_error_type_match(self) -> None:
        result = friendly_error(PermissionError(13, "Permission denied"))
        assert "wouldn't let us" in result.banner.lower()
        assert "close the file" in result.advice.lower()

    def test_in_use_text_match(self) -> None:
        # Win32 raises OSError("...being used by another process") rather
        # than PermissionError on some Excel-locked paths.
        result = friendly_error(
            OSError(
                32, "The process cannot access the file because it is being used by another process"
            )
        )
        assert "wouldn't let us" in result.banner.lower()


class TestPdfEmpty:
    def test_pdf_empty(self) -> None:
        result = friendly_error(ValueError("Operating Statement PDF appears empty: /foo.pdf"))
        assert "didn't contain any rows" in result.banner.lower()
        assert "cases21" in result.advice.lower()

    def test_no_data_rows(self) -> None:
        result = friendly_error(
            ValueError("No data rows found in Operating Statement PDF: /foo.pdf")
        )
        assert "didn't contain any rows" in result.banner.lower()


class TestPdfUnreadable:
    def test_cannot_read(self) -> None:
        result = friendly_error(ValueError("Cannot read Operating Statement PDF: /foo.pdf"))
        assert "couldn't read" in result.banner.lower()
        assert "adobe reader" in result.advice.lower()


class TestNumberParse:
    def test_decimal_parse(self) -> None:
        result = friendly_error(ValueError("Cannot parse 'TBC' as a decimal: …"))
        assert "number" in result.banner.lower()
        assert "tbc" in result.advice.lower() or "placeholder" in result.advice.lower()

    def test_currency_parse(self) -> None:
        result = friendly_error(ValueError("Cannot parse 'foo' as a currency amount"))
        assert "number" in result.banner.lower()


class TestNonNegative:
    def test_must_be_non_negative(self) -> None:
        result = friendly_error(ValueError("amount_cents must be non-negative, got -50"))
        assert "negative" in result.banner.lower()
        assert "positive" in result.advice.lower()


class TestExcelRetry:
    def test_excel_retry_loop(self) -> None:
        result = friendly_error(RuntimeError("Excel retry loop ended unexpectedly."))
        assert "excel" in result.banner.lower()
        assert "close" in result.advice.lower()


class TestBrowser:
    def test_browser_launch_failure(self) -> None:
        result = friendly_error(RuntimeError("Could not open the browser: BrowserError"))
        assert "browser" in result.banner.lower()
        assert "default browser" in result.advice.lower()


class TestGenericFallback:
    def test_unknown_exception_uses_fallback(self) -> None:
        # Any exception we don't have a rule for should still produce a
        # friendly result and include support contact info.
        result = friendly_error(ZeroDivisionError("division by zero"))
        assert "unexpected" in result.banner.lower()
        assert "feedback@schooltool.com.au" in result.advice.lower()


class TestMissingInput:
    """Round 37 — ``KeyError`` from missing input fields surfaces as a
    'fill in X first' message, not the support fallback."""

    def test_known_key_uses_friendly_label(self) -> None:
        result = friendly_error(KeyError("report_file"))
        # Banner should mention the human-readable label, not the raw key.
        assert "Sub-Program report" in result.banner
        assert "report_file" not in result.banner
        # Advice tells the user what to do, not to email support.
        assert "feedback@schooltool.com.au" not in result.advice.lower()
        # Technical line preserves the original error for debugging.
        assert "KeyError" in result.technical
        assert "report_file" in result.technical

    def test_unknown_key_falls_back_to_key_name(self) -> None:
        # An input key we haven't seen yet still produces a helpful
        # message — just uses the key name as the label.
        result = friendly_error(KeyError("brand_new_input"))
        assert "brand_new_input" in result.banner

    def test_master_budget_compass_key(self) -> None:
        result = friendly_error(KeyError("expense_file"))
        assert "Compass Expense file" in result.banner

    def test_master_budget_b_key(self) -> None:
        result = friendly_error(KeyError("master_file_b"))
        assert "Master Budget B" in result.banner


# ---------------------------------------------------------------------------
# Realism — sample data uses Path instances often
# ---------------------------------------------------------------------------


class TestRealistic:
    def test_path_in_message(self) -> None:
        # ValueError("File not found: " + str(Path)) is the typical form —
        # make sure the rule still triggers when the path is interpolated.
        p = Path("/users/ivan/Downloads/budget.pdf")
        result = friendly_error(ValueError(f"File not found: {p}"))
        assert "couldn't find" in result.banner.lower()
        # The original path is preserved in technical so support can repro.
        assert str(p) in result.technical
