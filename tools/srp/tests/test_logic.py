"""Tests for tools/srp/logic.py — parser, diff, and XLSX writer."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from toolkit.tokens import HL_MISMATCH, HL_SOURCE_ONLY
from tools.srp.logic import (
    SrpSummary,
    compare_srp,
    generate_srp_comparison,
    parse_decimal,
    parse_srp_pdf,
)

# ---------------------------------------------------------------------------
# Sample PDF paths (must exist on disk; tests fail, never skip, if absent)
# ---------------------------------------------------------------------------

_INDICATIVE_PDF = Path("Samples/SRP budget Report/2026 Indicative Budget SRP.pdf")
_CONFIRMED_PDF = Path("Samples/SRP budget Report/2026 confirmed SRP Budget.pdf")

# ---------------------------------------------------------------------------
# Test: currency parser
# ---------------------------------------------------------------------------


class TestParseDecimal:
    def test_dollar_prefix(self) -> None:
        assert parse_decimal("$16,172,029.00") == Decimal("16172029.00")

    def test_plain_number(self) -> None:
        assert parse_decimal("1,234.56") == Decimal("1234.56")

    def test_zero(self) -> None:
        assert parse_decimal("$0.00") == Decimal("0.00")

    def test_em_dash(self) -> None:
        assert parse_decimal("—") == Decimal("0")

    def test_blank(self) -> None:
        assert parse_decimal("") == Decimal("0")

    def test_negative_parens(self) -> None:
        assert parse_decimal("(500.00)") == Decimal("-500.00")

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_decimal("not-a-number!!")


# ---------------------------------------------------------------------------
# Test: parse_srp_pdf against real sample PDFs
# ---------------------------------------------------------------------------


class TestParseSrpPdfIndicative:
    @pytest.fixture(scope="class")
    def data(self) -> dict[tuple[int, str], tuple[str, Decimal]]:
        return parse_srp_pdf(_INDICATIVE_PDF)

    def test_minimum_key_count(self, data: dict[tuple[int, str], tuple[str, Decimal]]) -> None:
        assert len(data) >= 20, f"Expected >= 20 keys, got {len(data)}"

    def test_all_values_are_decimal(self, data: dict[tuple[int, str], tuple[str, Decimal]]) -> None:
        for (ref, desc), (_section, total) in data.items():
            assert isinstance(total, Decimal), f"Non-Decimal total for ({ref}, {desc!r})"

    def test_all_refs_are_int(self, data: dict[tuple[int, str], tuple[str, Decimal]]) -> None:
        for ref, _ in data:
            assert isinstance(ref, int), f"Non-int ref: {ref!r}"

    def test_all_descriptions_nonempty(
        self, data: dict[tuple[int, str], tuple[str, Decimal]]
    ) -> None:
        bad = [k for k in data if not k[1].strip()]
        assert not bad, f"Empty descriptions: {bad[:3]}"

    def test_ref15_multiplicity(self, data: dict[tuple[int, str], tuple[str, Decimal]]) -> None:
        """Ref 15 must appear as two distinct (ref, description) keys in Indicative."""
        ref15_keys = [k for k in data if k[0] == 15]
        assert len(ref15_keys) >= 2, (
            f"Expected at least 2 keys for Ref 15 in Indicative, got {ref15_keys}"
        )
        descriptions = {k[1] for k in ref15_keys}
        assert len(descriptions) >= 2, (
            f"Expected distinct descriptions for Ref 15, got {descriptions}"
        )

    def test_known_key_present(self, data: dict[tuple[int, str], tuple[str, Decimal]]) -> None:
        assert (1, "Years 7 - 12 Students") in data

    def test_known_amount(self, data: dict[tuple[int, str], tuple[str, Decimal]]) -> None:
        key = (1, "Years 7 - 12 Students")
        assert key in data
        _, total = data[key]
        assert total == Decimal("16172029.00"), f"Unexpected total for {key}: {total}"

    def test_section_assigned(self, data: dict[tuple[int, str], tuple[str, Decimal]]) -> None:
        sections = {section for (_, (section, _)) in data.items()}
        assert sections - {"Unknown"}, "All sections are 'Unknown' — section detection broken"

    def test_core_student_allocation_section(
        self, data: dict[tuple[int, str], tuple[str, Decimal]]
    ) -> None:
        key = (1, "Years 7 - 12 Students")
        section, _ = data[key]
        assert "Core Student Learning" in section, f"Unexpected section: {section!r}"

    def test_total_sum_positive(self, data: dict[tuple[int, str], tuple[str, Decimal]]) -> None:
        total = sum((v for (_, v) in data.values()), Decimal("0"))
        assert total > Decimal("0"), f"Total should be positive, got {total}"


class TestParseSrpPdfConfirmed:
    @pytest.fixture(scope="class")
    def data(self) -> dict[tuple[int, str], tuple[str, Decimal]]:
        return parse_srp_pdf(_CONFIRMED_PDF)

    def test_minimum_key_count(self, data: dict[tuple[int, str], tuple[str, Decimal]]) -> None:
        assert len(data) >= 20, f"Expected >= 20 keys, got {len(data)}"

    def test_new_lines_present(self, data: dict[tuple[int, str], tuple[str, Decimal]]) -> None:
        """Confirmed has lines not in Indicative (Quality Improvements, Language Assistants)."""
        assert (160, "Quality Improvements") in data or (
            42,
            "Language Assistants Program",
        ) in data, (
            "Expected at least one of (160, 'Quality Improvements') or "
            "(42, 'Language Assistants Program') in Confirmed"
        )

    def test_tier3_present(self, data: dict[tuple[int, str], tuple[str, Decimal]]) -> None:
        assert (138, "Tier 3 Individualised Funding") in data


# ---------------------------------------------------------------------------
# Test: compare_srp with synthetic fixtures
# ---------------------------------------------------------------------------


def _ind(
    ref: int, desc: str, section: str, amount: str
) -> tuple[tuple[int, str], tuple[str, Decimal]]:
    return (ref, desc), (section, Decimal(amount))


def _conf(
    ref: int, desc: str, section: str, amount: str
) -> tuple[tuple[int, str], tuple[str, Decimal]]:
    return (ref, desc), (section, Decimal(amount))


class TestCompareSrp:
    def _make_data(
        self,
    ) -> tuple[
        dict[tuple[int, str], tuple[str, Decimal]],
        dict[tuple[int, str], tuple[str, Decimal]],
    ]:
        indicative = dict(
            [
                _ind(1, "Item A", "Sec1", "1000.00"),
                _ind(2, "Item B", "Sec1", "2000.00"),
                _ind(3, "Item C", "Sec2", "3000.00"),
                _ind(4, "Item D", "Sec2", "4000.00"),
                _ind(5, "Item E", "Sec3", "500.00"),
            ]
        )
        confirmed = dict(
            [
                _conf(1, "Item A", "Sec1", "1000.00"),  # unchanged
                _conf(2, "Item B", "Sec1", "2500.00"),  # increased
                _conf(3, "Item C", "Sec2", "2800.00"),  # decreased
                # Item D removed
                _conf(6, "Item F", "Sec3", "750.00"),  # new_in_confirmed
                _conf(5, "Item E", "Sec3", "500.00"),  # unchanged (exact)
            ]
        )
        return indicative, confirmed

    def test_categories_present(self) -> None:
        ind, conf = self._make_data()
        lines = compare_srp(ind, conf)
        cats = {ln.category for ln in lines}
        assert "unchanged" in cats
        assert "increased" in cats
        assert "decreased" in cats
        assert "new_in_confirmed" in cats
        assert "removed" in cats

    def test_unchanged_variance_zero(self) -> None:
        ind, conf = self._make_data()
        lines = compare_srp(ind, conf)
        unchanged = [ln for ln in lines if ln.category == "unchanged"]
        assert unchanged
        for ln in unchanged:
            assert ln.variance == Decimal("0"), f"Unchanged variance should be 0, got {ln.variance}"

    def test_increased_variance_positive(self) -> None:
        ind, conf = self._make_data()
        lines = compare_srp(ind, conf)
        increased = [ln for ln in lines if ln.category == "increased"]
        assert increased
        for ln in increased:
            assert ln.variance is not None and ln.variance > Decimal("0")

    def test_decreased_variance_negative(self) -> None:
        ind, conf = self._make_data()
        lines = compare_srp(ind, conf)
        decreased = [ln for ln in lines if ln.category == "decreased"]
        assert decreased
        for ln in decreased:
            assert ln.variance is not None and ln.variance < Decimal("0")

    def test_new_in_confirmed_no_indicative(self) -> None:
        ind, conf = self._make_data()
        lines = compare_srp(ind, conf)
        new_lines = [ln for ln in lines if ln.category == "new_in_confirmed"]
        assert new_lines
        for ln in new_lines:
            assert ln.indicative is None
            assert ln.confirmed is not None
            assert ln.variance is None

    def test_removed_no_confirmed(self) -> None:
        ind, conf = self._make_data()
        lines = compare_srp(ind, conf)
        removed = [ln for ln in lines if ln.category == "removed"]
        assert removed
        for ln in removed:
            assert ln.confirmed is None
            assert ln.indicative is not None
            assert ln.variance is None

    def test_ref_desc_join_key(self) -> None:
        """Two lines with the same Ref but different descriptions must be separate."""
        indicative = dict(
            [
                _ind(15, "Integration Level 1", "PSD", "8813.00"),
                _ind(15, "Integration Level 2", "PSD", "20382.00"),
            ]
        )
        confirmed = dict(
            [
                # Level 1 removed, Level 2 increased
                _conf(15, "Integration Level 2", "PSD", "40764.00"),
            ]
        )
        lines = compare_srp(indicative, confirmed)
        assert len(lines) == 2
        cats = {(ln.ref, ln.description): ln.category for ln in lines}
        assert cats[(15, "Integration Level 1")] == "removed"
        assert cats[(15, "Integration Level 2")] == "increased"

    def test_pct_calculation(self) -> None:
        ind, conf = self._make_data()
        lines = compare_srp(ind, conf)
        increased = next(ln for ln in lines if ln.category == "increased")
        # Item B: indicative=2000, confirmed=2500, variance=500, pct=25.00%
        assert increased.pct is not None
        assert increased.pct == Decimal("25.00"), f"Expected 25.00%, got {increased.pct}"

    def test_total_line_count(self) -> None:
        ind, conf = self._make_data()
        lines = compare_srp(ind, conf)
        # 5 indicative + 1 new = 6 unique (ref, desc) pairs
        assert len(lines) == 6


# ---------------------------------------------------------------------------
# Test: generate_srp_comparison against real sample PDFs
# ---------------------------------------------------------------------------


class TestGenerateSrpComparison:
    def test_round_trip_produces_xlsx(self, tmp_path: Path) -> None:
        output = tmp_path / "srp_out.xlsx"
        progress_calls: list[tuple[int, str]] = []

        def progress(pct: int, msg: str) -> None:
            progress_calls.append((pct, msg))

        summary = generate_srp_comparison(
            indicative_pdf=_INDICATIVE_PDF,
            confirmed_pdf=_CONFIRMED_PDF,
            output_file=output,
            progress=progress,
        )

        assert output.exists(), "Output XLSX was not created"
        assert isinstance(summary, SrpSummary)
        assert len(summary.lines) >= 20

    def test_all_five_categories_present(self, tmp_path: Path) -> None:
        """At least one line in each of the 5 categories must exist in the real diff."""
        output = tmp_path / "srp_cat.xlsx"
        summary = generate_srp_comparison(
            indicative_pdf=_INDICATIVE_PDF,
            confirmed_pdf=_CONFIRMED_PDF,
            output_file=output,
            progress=lambda p, m: None,
        )
        cats = {ln.category for ln in summary.lines}
        # The real diff is known to have all 5 categories; each must be present
        # individually (no OR-gating, per reviewer-3 2026-04-26).
        assert "unchanged" in cats, f"Expected 'unchanged' in {cats}"
        assert "increased" in cats, f"Expected 'increased' in {cats}"
        assert "decreased" in cats, f"Expected 'decreased' in {cats}"
        assert "new_in_confirmed" in cats, f"Expected 'new_in_confirmed' in {cats}"
        assert "removed" in cats, f"Expected 'removed' in {cats}"

    def test_xlsx_header_correct(self, tmp_path: Path) -> None:
        output = tmp_path / "srp_hdr.xlsx"
        generate_srp_comparison(
            indicative_pdf=_INDICATIVE_PDF,
            confirmed_pdf=_CONFIRMED_PDF,
            output_file=output,
            progress=lambda p, m: None,
        )
        wb = openpyxl.load_workbook(output)
        ws = wb.active
        headers = [ws.cell(1, c).value for c in range(1, 9)]  # type: ignore[union-attr]
        assert headers[0] == "Ref"
        assert headers[2] == "Description"
        assert "Indicative" in headers
        assert "Confirmed" in headers
        assert "Variance" in headers

    def test_xlsx_row_count_matches_lines(self, tmp_path: Path) -> None:
        output = tmp_path / "srp_rows.xlsx"
        summary = generate_srp_comparison(
            indicative_pdf=_INDICATIVE_PDF,
            confirmed_pdf=_CONFIRMED_PDF,
            output_file=output,
            progress=lambda p, m: None,
        )
        wb = openpyxl.load_workbook(output)
        ws = wb.active
        data_rows = (ws.max_row or 1) - 1  # type: ignore[union-attr]
        assert data_rows == len(summary.lines)

    def test_mismatch_fill_on_decreased_rows(self, tmp_path: Path) -> None:
        """Rows with category 'decreased' or 'removed' must carry HL_MISMATCH fill."""
        output = tmp_path / "srp_fill_dec.xlsx"
        summary = generate_srp_comparison(
            indicative_pdf=_INDICATIVE_PDF,
            confirmed_pdf=_CONFIRMED_PDF,
            output_file=output,
            progress=lambda p, m: None,
        )

        dec_lines = [ln for ln in summary.lines if ln.category in {"decreased", "removed"}]
        assert dec_lines, (
            "No 'decreased' or 'removed' lines found — the sample diff must produce at least one "
            "such line for this test to be meaningful."
        )

        wb = openpyxl.load_workbook(output)
        ws = wb.active
        target_argb = ("FF" + HL_MISMATCH).upper()

        for ln in dec_lines[:3]:  # spot-check first 3
            # Find the row in the workbook by matching Ref + Description
            for row_idx in range(2, (ws.max_row or 2) + 1):  # type: ignore[union-attr]
                ref_val = ws.cell(row_idx, 1).value  # type: ignore[union-attr]
                desc_val = ws.cell(row_idx, 3).value  # type: ignore[union-attr]
                if str(ref_val) == str(ln.ref) and str(desc_val) == ln.description:
                    fill = ws.cell(row_idx, 1).fill  # type: ignore[union-attr]
                    assert fill and fill.fgColor and fill.fgColor.rgb, (
                        f"Decreased row ({ln.ref}, {ln.description!r}) has no fill"
                    )
                    assert target_argb in fill.fgColor.rgb.upper(), (
                        f"Decreased row ({ln.ref}, {ln.description!r}) has wrong fill "
                        f"{fill.fgColor.rgb!r}; expected {target_argb!r}"
                    )
                    break

    def test_source_fill_on_increased_rows(self, tmp_path: Path) -> None:
        """Rows with category 'increased' or 'new_in_confirmed' must carry HL_SOURCE_ONLY fill."""
        output = tmp_path / "srp_fill_inc.xlsx"
        summary = generate_srp_comparison(
            indicative_pdf=_INDICATIVE_PDF,
            confirmed_pdf=_CONFIRMED_PDF,
            output_file=output,
            progress=lambda p, m: None,
        )

        inc_lines = [ln for ln in summary.lines if ln.category in {"increased", "new_in_confirmed"}]
        assert inc_lines, (
            "No 'increased' or 'new_in_confirmed' lines found — the sample diff must produce "
            "at least one such line for this test to be meaningful."
        )

        wb = openpyxl.load_workbook(output)
        ws = wb.active
        target_argb = ("FF" + HL_SOURCE_ONLY).upper()

        for ln in inc_lines[:3]:  # spot-check first 3
            for row_idx in range(2, (ws.max_row or 2) + 1):  # type: ignore[union-attr]
                ref_val = ws.cell(row_idx, 1).value  # type: ignore[union-attr]
                desc_val = ws.cell(row_idx, 3).value  # type: ignore[union-attr]
                if str(ref_val) == str(ln.ref) and str(desc_val) == ln.description:
                    fill = ws.cell(row_idx, 1).fill  # type: ignore[union-attr]
                    assert fill and fill.fgColor and fill.fgColor.rgb, (
                        f"Increased row ({ln.ref}, {ln.description!r}) has no fill"
                    )
                    assert target_argb in fill.fgColor.rgb.upper(), (
                        f"Increased row ({ln.ref}, {ln.description!r}) has wrong fill "
                        f"{fill.fgColor.rgb!r}; expected {target_argb!r}"
                    )
                    break

    def test_unchanged_row_has_no_fill(self, tmp_path: Path) -> None:
        output = tmp_path / "srp_fill_unch.xlsx"
        summary = generate_srp_comparison(
            indicative_pdf=_INDICATIVE_PDF,
            confirmed_pdf=_CONFIRMED_PDF,
            output_file=output,
            progress=lambda p, m: None,
        )

        unchanged = [ln for ln in summary.lines if ln.category == "unchanged"]
        assert unchanged, "Expected at least one unchanged line"

        wb = openpyxl.load_workbook(output)
        ws = wb.active

        for ln in unchanged[:3]:  # spot-check
            for row_idx in range(2, (ws.max_row or 2) + 1):  # type: ignore[union-attr]
                ref_val = ws.cell(row_idx, 1).value  # type: ignore[union-attr]
                desc_val = ws.cell(row_idx, 3).value  # type: ignore[union-attr]
                if str(ref_val) == str(ln.ref) and str(desc_val) == ln.description:
                    fill = ws.cell(row_idx, 1).fill  # type: ignore[union-attr]
                    # No fill means PatternFillType is None or 'none'
                    no_fill = (
                        fill is None
                        or fill.fill_type in (None, "none")
                        or (fill.fgColor is not None and fill.fgColor.type == "none")
                    )
                    assert no_fill, (
                        f"Unchanged row ({ln.ref}, {ln.description!r}) should have no fill"
                    )
                    break

    def test_progress_callbacks_fired(self, tmp_path: Path) -> None:
        output = tmp_path / "srp_prog.xlsx"
        pcts: list[int] = []

        def progress(pct: int, msg: str) -> None:
            pcts.append(pct)

        generate_srp_comparison(
            indicative_pdf=_INDICATIVE_PDF,
            confirmed_pdf=_CONFIRMED_PDF,
            output_file=output,
            progress=progress,
        )

        assert 10 in pcts
        assert 100 in pcts

    def test_totals_computed(self, tmp_path: Path) -> None:
        output = tmp_path / "srp_totals.xlsx"
        summary = generate_srp_comparison(
            indicative_pdf=_INDICATIVE_PDF,
            confirmed_pdf=_CONFIRMED_PDF,
            output_file=output,
            progress=lambda p, m: None,
        )
        assert summary.total_indicative > Decimal("0")
        assert summary.total_confirmed > Decimal("0")

    def test_missing_indicative_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="not found"):
            generate_srp_comparison(
                indicative_pdf=tmp_path / "missing.pdf",
                confirmed_pdf=_CONFIRMED_PDF,
                output_file=tmp_path / "out.xlsx",
                progress=lambda p, m: None,
            )
