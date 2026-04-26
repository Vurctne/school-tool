"""Tests for tools/operating/frame.py -- BaseTool conformance + run() paths."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import patch

from toolkit.base_tool import CurrencyInput, FileInput, NumberInput, OutputSpec
from toolkit.tokens import HL_MISMATCH, HL_SOURCE_ONLY
from tools.operating.frame import OperatingStatementTool
from tools.operating.logic import OpStatLine, OpStatSummary

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _noop_progress(pct: int, msg: str) -> None:
    pass


def _make_line(
    gl_code: int = 70001,
    description: str = "Cash SRP Funding",
    section: str = "REVENUE",
    subsection: str = "Dep't Grants",
    ytd_prior: str = "100000",
    ytd_current: str = "110000",
    movement: str = "10000",
    pct: str = "10.0",
    is_favourable: bool | None = True,
    exceeds_threshold: bool = True,
) -> OpStatLine:
    return OpStatLine(
        gl_code=gl_code,
        description=description,
        section=section,
        subsection=subsection,
        ytd_prior=Decimal(ytd_prior),
        ytd_current=Decimal(ytd_current),
        movement=Decimal(movement),
        pct=Decimal(pct),
        is_favourable=is_favourable,
        exceeds_threshold=exceeds_threshold,
    )


def _make_summary(
    lines: list[OpStatLine] | None = None,
    output_path: Path | None = None,
) -> OpStatSummary:
    if lines is None:
        lines = [_make_line()]
    if output_path is None:
        output_path = Path("/tmp/output.xlsx")
    _zero = Decimal("0")
    revenue_movement: Decimal = sum((ln.movement for ln in lines if ln.section == "REVENUE"), _zero)
    expenditure_movement: Decimal = sum(
        (ln.movement for ln in lines if ln.section == "EXPENDITURE"), _zero
    )
    operating_result_movement: Decimal = revenue_movement - expenditure_movement
    return OpStatSummary(
        lines=lines,
        revenue_movement=revenue_movement,
        expenditure_movement=expenditure_movement,
        operating_result_movement=operating_result_movement,
        period_current="31 March 2026",
        period_prior="28 February 2026",
        output_path=output_path,
    )


# ---------------------------------------------------------------------------
# 1. Structural conformance
# ---------------------------------------------------------------------------


class TestStructuralConformance:
    def test_id(self) -> None:
        assert OperatingStatementTool.id == "operating"

    def test_group(self) -> None:
        assert OperatingStatementTool.group == "Reconciliation"

    def test_label(self) -> None:
        assert OperatingStatementTool.label == "Operating Statement"

    def test_short(self) -> None:
        assert OperatingStatementTool.short == "OS"

    def test_order(self) -> None:
        assert isinstance(OperatingStatementTool.order, int)
        assert OperatingStatementTool.order == 20

    def test_primary_button(self) -> None:
        assert OperatingStatementTool.primary_button == "Generate comparison"

    def test_requires_feature(self) -> None:
        assert OperatingStatementTool.requires_feature == "operating"

    def test_has_run(self) -> None:
        tool = OperatingStatementTool()
        assert callable(tool.run)

    def test_has_secondary_actions(self) -> None:
        tool = OperatingStatementTool()
        actions = tool.secondary_actions()
        assert isinstance(actions, list)

    def test_has_help_text(self) -> None:
        assert isinstance(OperatingStatementTool.help_text, str)
        assert len(OperatingStatementTool.help_text) > 100

    def test_pdf_template_none(self) -> None:
        assert OperatingStatementTool.pdf_template is None

    def test_pdf_body_none(self) -> None:
        assert OperatingStatementTool.pdf_body is None


# ---------------------------------------------------------------------------
# 2. Inputs
# ---------------------------------------------------------------------------


class TestInputs:
    def test_inputs_has_four_items(self) -> None:
        assert len(OperatingStatementTool.inputs) == 4

    def test_first_input_is_current_file(self) -> None:
        fi = OperatingStatementTool.inputs[0]
        assert isinstance(fi, FileInput)
        assert fi.key == "current_file"

    def test_second_input_is_prior_file(self) -> None:
        fi = OperatingStatementTool.inputs[1]
        assert isinstance(fi, FileInput)
        assert fi.key == "prior_file"

    def test_third_input_is_currency(self) -> None:
        ci = OperatingStatementTool.inputs[2]
        assert isinstance(ci, CurrencyInput)
        assert ci.key == "threshold_dollars"

    def test_fourth_input_is_number(self) -> None:
        ni = OperatingStatementTool.inputs[3]
        assert isinstance(ni, NumberInput)
        assert ni.key == "threshold_pct"

    def test_output_suffix_xlsx(self) -> None:
        assert OperatingStatementTool.output is not None
        assert isinstance(OperatingStatementTool.output, OutputSpec)
        assert OperatingStatementTool.output.suffix == ".xlsx"


# ---------------------------------------------------------------------------
# 3. Help text
# ---------------------------------------------------------------------------


class TestHelpText:
    def test_help_text_non_empty(self) -> None:
        ht = OperatingStatementTool.help_text
        assert len(ht) > 200

    def test_help_text_contains_hl_mismatch(self) -> None:
        assert HL_MISMATCH in OperatingStatementTool.help_text

    def test_help_text_contains_hl_source_only(self) -> None:
        assert HL_SOURCE_ONLY in OperatingStatementTool.help_text

    def test_help_text_mentions_operating_statement(self) -> None:
        assert "Operating Statement" in OperatingStatementTool.help_text

    def test_help_text_mentions_threshold(self) -> None:
        ht = OperatingStatementTool.help_text.lower()
        assert "threshold" in ht

    def test_help_text_mentions_licence(self) -> None:
        ht = OperatingStatementTool.help_text.lower()
        assert "licence" in ht


# ---------------------------------------------------------------------------
# 4. run() -- happy path
# ---------------------------------------------------------------------------


class TestRunHappyPath:
    def test_success_status(self, tmp_path: Path) -> None:
        tool = OperatingStatementTool()
        summary = _make_summary()
        with patch(
            "tools.operating.frame.logic.generate_opstat_comparison",
            return_value=summary,
        ):
            result = tool.run(
                {
                    "current_file": str(tmp_path / "current.pdf"),
                    "prior_file": str(tmp_path / "prior.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.status == "success"

    def test_table_rows_populated(self, tmp_path: Path) -> None:
        tool = OperatingStatementTool()
        lines = [_make_line(70001), _make_line(73002, section="REVENUE")]
        summary = _make_summary(lines=lines)
        with patch(
            "tools.operating.frame.logic.generate_opstat_comparison",
            return_value=summary,
        ):
            result = tool.run(
                {
                    "current_file": str(tmp_path / "current.pdf"),
                    "prior_file": str(tmp_path / "prior.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.table_rows is not None
        assert len(result.table_rows) == 2

    def test_table_columns_keys(self, tmp_path: Path) -> None:
        tool = OperatingStatementTool()
        summary = _make_summary()
        with patch(
            "tools.operating.frame.logic.generate_opstat_comparison",
            return_value=summary,
        ):
            result = tool.run(
                {
                    "current_file": str(tmp_path / "current.pdf"),
                    "prior_file": str(tmp_path / "prior.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.table_columns is not None
        keys = [col["key"] for col in result.table_columns]
        assert "gl_code" in keys
        assert "description" in keys
        assert "section" in keys
        assert "movement" in keys
        assert "pct" in keys

    def test_output_path_set(self, tmp_path: Path) -> None:
        tool = OperatingStatementTool()
        out = tmp_path / "out.xlsx"
        summary = _make_summary(output_path=out)
        with patch(
            "tools.operating.frame.logic.generate_opstat_comparison",
            return_value=summary,
        ):
            result = tool.run(
                {
                    "current_file": str(tmp_path / "current.pdf"),
                    "prior_file": str(tmp_path / "prior.pdf"),
                    "output_file": str(out),
                },
                _noop_progress,
            )
        assert result.output_path == out

    def test_metrics_present(self, tmp_path: Path) -> None:
        tool = OperatingStatementTool()
        summary = _make_summary()
        with patch(
            "tools.operating.frame.logic.generate_opstat_comparison",
            return_value=summary,
        ):
            result = tool.run(
                {
                    "current_file": str(tmp_path / "current.pdf"),
                    "prior_file": str(tmp_path / "prior.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.metrics is not None
        assert len(result.metrics) >= 2


# ---------------------------------------------------------------------------
# 5. run() -- adverse row produces warning
# ---------------------------------------------------------------------------


class TestRunWarningPath:
    def test_adverse_row_produces_warning_status(self, tmp_path: Path) -> None:
        tool = OperatingStatementTool()
        adverse_line = _make_line(
            section="REVENUE",
            movement="-10000",
            ytd_prior="110000",
            ytd_current="100000",
            is_favourable=False,
            exceeds_threshold=True,
        )
        summary = _make_summary(lines=[adverse_line])
        with patch(
            "tools.operating.frame.logic.generate_opstat_comparison",
            return_value=summary,
        ):
            result = tool.run(
                {
                    "current_file": str(tmp_path / "current.pdf"),
                    "prior_file": str(tmp_path / "prior.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.status == "warning"
        assert result.banner_level == "warning"

    def test_adverse_row_has_mismatch_bg(self, tmp_path: Path) -> None:
        tool = OperatingStatementTool()
        adverse_line = _make_line(
            section="REVENUE",
            movement="-10000",
            ytd_prior="110000",
            ytd_current="100000",
            is_favourable=False,
            exceeds_threshold=True,
        )
        summary = _make_summary(lines=[adverse_line])
        with patch(
            "tools.operating.frame.logic.generate_opstat_comparison",
            return_value=summary,
        ):
            result = tool.run(
                {
                    "current_file": str(tmp_path / "current.pdf"),
                    "prior_file": str(tmp_path / "prior.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.table_rows is not None
        row = result.table_rows[0]
        assert row["_bg"] is not None
        assert HL_MISMATCH in row["_bg"]

    def test_favourable_row_has_source_only_bg(self, tmp_path: Path) -> None:
        tool = OperatingStatementTool()
        fav_line = _make_line(
            section="REVENUE",
            is_favourable=True,
            exceeds_threshold=True,
        )
        summary = _make_summary(lines=[fav_line])
        with patch(
            "tools.operating.frame.logic.generate_opstat_comparison",
            return_value=summary,
        ):
            result = tool.run(
                {
                    "current_file": str(tmp_path / "current.pdf"),
                    "prior_file": str(tmp_path / "prior.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.table_rows is not None
        row = result.table_rows[0]
        assert row["_bg"] is not None
        assert HL_SOURCE_ONLY in row["_bg"]

    def test_below_threshold_row_has_no_bg(self, tmp_path: Path) -> None:
        tool = OperatingStatementTool()
        no_flag_line = _make_line(exceeds_threshold=False)
        summary = _make_summary(lines=[no_flag_line])
        with patch(
            "tools.operating.frame.logic.generate_opstat_comparison",
            return_value=summary,
        ):
            result = tool.run(
                {
                    "current_file": str(tmp_path / "current.pdf"),
                    "prior_file": str(tmp_path / "prior.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.table_rows is not None
        assert result.table_rows[0]["_bg"] is None


# ---------------------------------------------------------------------------
# 6. run() -- error path
# ---------------------------------------------------------------------------


class TestRunErrorPath:
    def test_error_status(self, tmp_path: Path) -> None:
        tool = OperatingStatementTool()
        with patch(
            "tools.operating.frame.logic.generate_opstat_comparison",
            side_effect=ValueError("bad PDF"),
        ):
            result = tool.run(
                {
                    "current_file": str(tmp_path / "missing.pdf"),
                    "prior_file": str(tmp_path / "missing2.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.status == "error"
        assert result.banner_level == "danger"

    def test_error_log_includes_exc_type(self, tmp_path: Path) -> None:
        tool = OperatingStatementTool()
        with patch(
            "tools.operating.frame.logic.generate_opstat_comparison",
            side_effect=ValueError("bad PDF"),
        ):
            result = tool.run(
                {
                    "current_file": str(tmp_path / "missing.pdf"),
                    "prior_file": str(tmp_path / "missing2.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        combined = " ".join(ll.text for ll in result.log_lines)
        assert "ValueError" in combined


# ---------------------------------------------------------------------------
# 7. run() -- threshold defaults
# ---------------------------------------------------------------------------


class TestThresholdDefaults:
    def test_blank_thresholds_use_defaults(self, tmp_path: Path) -> None:
        """When threshold keys are absent, defaults ($5000 / 10%) are used."""
        tool = OperatingStatementTool()
        summary = _make_summary()
        captured: dict[str, Any] = {}

        def fake_generate(**kwargs: Any) -> OpStatSummary:
            captured.update(kwargs)
            return summary

        with patch(
            "tools.operating.frame.logic.generate_opstat_comparison",
            side_effect=fake_generate,
        ):
            tool.run(
                {
                    "current_file": str(tmp_path / "current.pdf"),
                    "prior_file": str(tmp_path / "prior.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                    # threshold_dollars and threshold_pct deliberately absent
                },
                _noop_progress,
            )

        assert captured.get("threshold_dollars") == Decimal("5000")
        assert captured.get("threshold_pct") == 10


# ---------------------------------------------------------------------------
# 8. Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_tool_registered(self) -> None:
        import tools.operating  # noqa: F401
        from toolkit.registry import _registered

        registered_ids = [cls.id for cls in _registered]
        assert OperatingStatementTool.id in registered_ids
