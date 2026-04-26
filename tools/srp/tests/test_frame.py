"""Tests for tools/srp/frame.py — BaseTool conformance + run() paths."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import patch

from toolkit.base_tool import FileInput, OutputSpec
from toolkit.tokens import HL_MISMATCH, HL_SOURCE_ONLY
from tools.srp.frame import SrpComparisonTool
from tools.srp.logic import SrpLine, SrpSummary

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _noop_progress(pct: int, msg: str) -> None:
    pass


def _make_line(
    ref: int = 1,
    section: str = "Core Student Learning Allocation",
    description: str = "Test line",
    indicative: str | None = "10000.00",
    confirmed: str | None = "10000.00",
    category: str = "unchanged",
) -> SrpLine:
    ind = Decimal(indicative) if indicative is not None else None
    conf = Decimal(confirmed) if confirmed is not None else None
    var: Decimal | None
    pct: Decimal | None
    if ind is not None and conf is not None:
        _var = conf - ind
        var = _var
        pct = (
            (_var / ind * Decimal("100")).quantize(Decimal("0.01"))
            if ind != Decimal("0")
            else Decimal("0")
        )
    else:
        var = None
        pct = None
    from typing import Literal

    cat: Literal["unchanged", "increased", "decreased", "new_in_confirmed", "removed"] = category  # type: ignore[assignment]
    return SrpLine(
        ref=ref,
        section=section,
        description=description,
        indicative=ind,
        confirmed=conf,
        variance=var,
        pct=pct,
        category=cat,
    )


def _make_summary(
    lines: list[SrpLine] | None = None,
    output_path: Path | None = None,
) -> SrpSummary:
    if lines is None:
        lines = [_make_line(1, description="Alpha"), _make_line(2, description="Beta")]
    if output_path is None:
        output_path = Path("/tmp/srp_output.xlsx")
    total_ind = sum((ln.indicative for ln in lines if ln.indicative is not None), Decimal("0"))
    total_conf = sum((ln.confirmed for ln in lines if ln.confirmed is not None), Decimal("0"))
    counts: dict[str, int] = {}
    for ln in lines:
        counts[ln.category] = counts.get(ln.category, 0) + 1
    return SrpSummary(
        lines=lines,
        total_indicative=total_ind,
        total_confirmed=total_conf,
        counts=counts,
        output_path=output_path,
    )


# ---------------------------------------------------------------------------
# 1. Structural conformance
# ---------------------------------------------------------------------------


class TestStructuralConformance:
    def test_id(self) -> None:
        assert SrpComparisonTool.id == "srp"

    def test_group(self) -> None:
        assert SrpComparisonTool.group == "Budget"

    def test_label(self) -> None:
        assert SrpComparisonTool.label == "SRP Comparison"

    def test_short(self) -> None:
        assert SrpComparisonTool.short == "SR"

    def test_order(self) -> None:
        assert isinstance(SrpComparisonTool.order, int)
        assert SrpComparisonTool.order == 20

    def test_primary_button(self) -> None:
        assert SrpComparisonTool.primary_button == "Generate comparison"

    def test_has_run(self) -> None:
        tool = SrpComparisonTool()
        assert callable(tool.run)

    def test_has_secondary_actions(self) -> None:
        tool = SrpComparisonTool()
        actions = tool.secondary_actions()
        assert isinstance(actions, list)

    def test_has_help_text(self) -> None:
        assert isinstance(SrpComparisonTool.help_text, str)
        assert len(SrpComparisonTool.help_text) > 100

    def test_pdf_template_none(self) -> None:
        assert SrpComparisonTool.pdf_template is None

    def test_pdf_body_none(self) -> None:
        assert SrpComparisonTool.pdf_body is None

    def test_no_requires_feature(self) -> None:
        """SRP is a free tool — requires_feature must not be set on the class."""
        assert not hasattr(SrpComparisonTool, "requires_feature") or (
            getattr(SrpComparisonTool, "requires_feature", None) is None
        ), "SRP is a free tool; requires_feature must not be set (or must be None)"


# ---------------------------------------------------------------------------
# 2. Inputs
# ---------------------------------------------------------------------------


class TestInputs:
    def test_inputs_has_two_items(self) -> None:
        assert len(SrpComparisonTool.inputs) == 2

    def test_first_input_is_file_indicative(self) -> None:
        fi = SrpComparisonTool.inputs[0]
        assert isinstance(fi, FileInput)
        assert fi.key == "indicative_pdf"

    def test_second_input_is_file_confirmed(self) -> None:
        fi = SrpComparisonTool.inputs[1]
        assert isinstance(fi, FileInput)
        assert fi.key == "confirmed_pdf"

    def test_output_suffix_xlsx(self) -> None:
        assert SrpComparisonTool.output is not None
        assert isinstance(SrpComparisonTool.output, OutputSpec)
        assert SrpComparisonTool.output.suffix == ".xlsx"

    def test_output_key(self) -> None:
        assert SrpComparisonTool.output is not None
        assert SrpComparisonTool.output.key == "output_file"

    def test_pdf_filetypes_present(self) -> None:
        fi = SrpComparisonTool.inputs[0]
        assert isinstance(fi, FileInput)
        assert any("pdf" in ft[1].lower() for ft in fi.filetypes)


# ---------------------------------------------------------------------------
# 3. Help text
# ---------------------------------------------------------------------------


class TestHelpText:
    def test_mentions_indicative(self) -> None:
        assert "Indicative" in SrpComparisonTool.help_text

    def test_mentions_confirmed(self) -> None:
        assert "Confirmed" in SrpComparisonTool.help_text

    def test_mentions_hl_mismatch_interpolated(self) -> None:
        # The f-string must interpolate HL_MISMATCH (no bare hex in source — drift guard)
        assert HL_MISMATCH in SrpComparisonTool.help_text

    def test_mentions_hl_source_only_interpolated(self) -> None:
        assert HL_SOURCE_ONLY in SrpComparisonTool.help_text

    def test_free_tool_mentioned(self) -> None:
        assert "free" in SrpComparisonTool.help_text.lower()


# ---------------------------------------------------------------------------
# 4. run() — happy path (all unchanged)
# ---------------------------------------------------------------------------


class TestRunHappyPath:
    def test_success_status(self, tmp_path: Path) -> None:
        tool = SrpComparisonTool()
        summary = _make_summary()
        with patch("tools.srp.frame.logic.generate_srp_comparison", return_value=summary):
            result = tool.run(
                {
                    "indicative_pdf": str(tmp_path / "ind.pdf"),
                    "confirmed_pdf": str(tmp_path / "conf.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.status == "success"

    def test_table_rows_populated(self, tmp_path: Path) -> None:
        tool = SrpComparisonTool()
        lines = [_make_line(1, description="Alpha"), _make_line(2, description="Beta")]
        summary = _make_summary(lines=lines)
        with patch("tools.srp.frame.logic.generate_srp_comparison", return_value=summary):
            result = tool.run(
                {
                    "indicative_pdf": str(tmp_path / "ind.pdf"),
                    "confirmed_pdf": str(tmp_path / "conf.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.table_rows is not None
        assert len(result.table_rows) == 2

    def test_table_columns_present(self, tmp_path: Path) -> None:
        tool = SrpComparisonTool()
        summary = _make_summary()
        with patch("tools.srp.frame.logic.generate_srp_comparison", return_value=summary):
            result = tool.run(
                {
                    "indicative_pdf": str(tmp_path / "ind.pdf"),
                    "confirmed_pdf": str(tmp_path / "conf.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.table_columns is not None
        keys = [col["key"] for col in result.table_columns]
        assert "ref" in keys
        assert "section" in keys
        assert "description" in keys
        assert "indicative" in keys
        assert "confirmed" in keys
        assert "variance" in keys
        assert "pct" in keys
        assert "category" in keys

    def test_output_path_set(self, tmp_path: Path) -> None:
        tool = SrpComparisonTool()
        out = tmp_path / "out.xlsx"
        summary = _make_summary(output_path=out)
        with patch("tools.srp.frame.logic.generate_srp_comparison", return_value=summary):
            result = tool.run(
                {
                    "indicative_pdf": str(tmp_path / "ind.pdf"),
                    "confirmed_pdf": str(tmp_path / "conf.pdf"),
                    "output_file": str(out),
                },
                _noop_progress,
            )
        assert result.output_path == out

    def test_metrics_present(self, tmp_path: Path) -> None:
        tool = SrpComparisonTool()
        summary = _make_summary()
        with patch("tools.srp.frame.logic.generate_srp_comparison", return_value=summary):
            result = tool.run(
                {
                    "indicative_pdf": str(tmp_path / "ind.pdf"),
                    "confirmed_pdf": str(tmp_path / "conf.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.metrics is not None
        assert len(result.metrics) >= 3
        labels = [m[0] for m in result.metrics]
        assert "Indicative total" in labels
        assert "Confirmed total" in labels
        assert "Net variance" in labels


# ---------------------------------------------------------------------------
# 5. run() — _bg set correctly per category
# ---------------------------------------------------------------------------


class TestRunRowBg:
    def _run_with_lines(self, lines: list[SrpLine], tmp_path: Path) -> list[dict[str, Any]]:
        tool = SrpComparisonTool()
        summary = _make_summary(lines=lines)
        with patch("tools.srp.frame.logic.generate_srp_comparison", return_value=summary):
            result = tool.run(
                {
                    "indicative_pdf": str(tmp_path / "ind.pdf"),
                    "confirmed_pdf": str(tmp_path / "conf.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.table_rows is not None
        return result.table_rows

    def test_decreased_row_has_mismatch_bg(self, tmp_path: Path) -> None:
        ln = _make_line(1, indicative="2000.00", confirmed="1500.00", category="decreased")
        rows = self._run_with_lines([ln], tmp_path)
        assert rows[0]["_bg"] is not None
        assert HL_MISMATCH in rows[0]["_bg"]

    def test_removed_row_has_mismatch_bg(self, tmp_path: Path) -> None:
        ln = _make_line(2, indicative="1000.00", confirmed=None, category="removed")
        rows = self._run_with_lines([ln], tmp_path)
        assert rows[0]["_bg"] is not None
        assert HL_MISMATCH in rows[0]["_bg"]

    def test_increased_row_has_source_bg(self, tmp_path: Path) -> None:
        ln = _make_line(3, indicative="1000.00", confirmed="1500.00", category="increased")
        rows = self._run_with_lines([ln], tmp_path)
        assert rows[0]["_bg"] is not None
        assert HL_SOURCE_ONLY in rows[0]["_bg"]

    def test_new_in_confirmed_row_has_source_bg(self, tmp_path: Path) -> None:
        ln = _make_line(4, indicative=None, confirmed="1500.00", category="new_in_confirmed")
        rows = self._run_with_lines([ln], tmp_path)
        assert rows[0]["_bg"] is not None
        assert HL_SOURCE_ONLY in rows[0]["_bg"]

    def test_unchanged_row_has_no_bg(self, tmp_path: Path) -> None:
        ln = _make_line(5, category="unchanged")
        rows = self._run_with_lines([ln], tmp_path)
        assert rows[0]["_bg"] is None


# ---------------------------------------------------------------------------
# 6. run() — banner text structure
# ---------------------------------------------------------------------------


class TestRunBannerText:
    def test_banner_contains_line_count(self, tmp_path: Path) -> None:
        tool = SrpComparisonTool()
        lines = [_make_line(1), _make_line(2)]
        summary = _make_summary(lines=lines)
        with patch("tools.srp.frame.logic.generate_srp_comparison", return_value=summary):
            result = tool.run(
                {
                    "indicative_pdf": str(tmp_path / "ind.pdf"),
                    "confirmed_pdf": str(tmp_path / "conf.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert "2 lines compared" in result.banner_text

    def test_banner_contains_net_variance(self, tmp_path: Path) -> None:
        tool = SrpComparisonTool()
        summary = _make_summary()
        with patch("tools.srp.frame.logic.generate_srp_comparison", return_value=summary):
            result = tool.run(
                {
                    "indicative_pdf": str(tmp_path / "ind.pdf"),
                    "confirmed_pdf": str(tmp_path / "conf.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert "Net variance" in result.banner_text

    def test_warning_status_when_decreased(self, tmp_path: Path) -> None:
        tool = SrpComparisonTool()
        ln = _make_line(1, indicative="2000.00", confirmed="1500.00", category="decreased")
        summary = _make_summary(lines=[ln])
        with patch("tools.srp.frame.logic.generate_srp_comparison", return_value=summary):
            result = tool.run(
                {
                    "indicative_pdf": str(tmp_path / "ind.pdf"),
                    "confirmed_pdf": str(tmp_path / "conf.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.status == "warning"
        assert result.banner_level == "warning"


# ---------------------------------------------------------------------------
# 7. run() — error path
# ---------------------------------------------------------------------------


class TestRunErrorPath:
    def test_error_status(self, tmp_path: Path) -> None:
        tool = SrpComparisonTool()
        with patch(
            "tools.srp.frame.logic.generate_srp_comparison",
            side_effect=ValueError("bad file"),
        ):
            result = tool.run(
                {
                    "indicative_pdf": str(tmp_path / "missing.pdf"),
                    "confirmed_pdf": str(tmp_path / "missing2.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.status == "error"

    def test_error_banner_level_danger(self, tmp_path: Path) -> None:
        tool = SrpComparisonTool()
        with patch(
            "tools.srp.frame.logic.generate_srp_comparison",
            side_effect=ValueError("bad file"),
        ):
            result = tool.run(
                {
                    "indicative_pdf": str(tmp_path / "missing.pdf"),
                    "confirmed_pdf": str(tmp_path / "missing2.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.banner_level == "danger"

    def test_error_log_lines_include_exc_type(self, tmp_path: Path) -> None:
        tool = SrpComparisonTool()
        with patch(
            "tools.srp.frame.logic.generate_srp_comparison",
            side_effect=ValueError("bad file"),
        ):
            result = tool.run(
                {
                    "indicative_pdf": str(tmp_path / "missing.pdf"),
                    "confirmed_pdf": str(tmp_path / "missing2.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        combined = " ".join(ll.text for ll in result.log_lines)
        assert "ValueError" in combined


# ---------------------------------------------------------------------------
# 8. Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_tool_registered(self) -> None:
        import tools.srp  # noqa: F401
        from toolkit.registry import _registered

        registered_ids = [cls.id for cls in _registered]
        assert SrpComparisonTool.id in registered_ids

    def test_register_idempotent(self) -> None:
        import tools.srp  # noqa: F401
        from toolkit.registry import _registered

        srp_entries = [cls for cls in _registered if cls.id == "srp"]
        assert len(srp_entries) == 1, "register() must be idempotent"
