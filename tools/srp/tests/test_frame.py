"""Tests for tools/srp/frame.py -- BaseTool conformance + run() paths."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import patch

from toolkit.base_tool import FileInput
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
    # Use whichever values are present to compute variance
    vals = [v for v in (ind, conf) if v is not None]
    if len(vals) == 2:
        _diff = vals[1] - vals[0]
        _var: Decimal | None = _diff
        _denom: Decimal = vals[0]
        pct: Decimal | None = (
            (_diff / _denom * Decimal("100")).quantize(Decimal("0.01"))
            if _denom != Decimal("0")
            else Decimal("0")
        )
    elif len(vals) == 1:
        _var = None
        pct = None
    else:
        _var = None
        pct = None
    # Build adjacent_variances for the ind->conf pair if both present
    adj: list[tuple[str, Decimal | None]] = []
    if ind is not None and conf is not None:
        adj = [("Indicative\u2192Confirmed", conf - ind)]
    return SrpLine(
        ref=ref,
        section=section,
        description=description,
        indicative=ind,
        confirmed=conf,
        revised1=None,
        revised2=None,
        category=category,  # type: ignore[arg-type]
        adjacent_variances=adj,
        variance_ind_to_conf=_var if (ind is not None and conf is not None) else None,
        variance_conf_to_rev1=None,
        variance_rev1_to_rev2=None,
        variance=_var,
        pct=pct,
    )


def _make_summary(
    lines: list[SrpLine] | None = None,
    output_path: Path | None = None,
    has_revised1: bool = False,
    has_revised2: bool = False,
    version_labels: list[str] | None = None,
) -> SrpSummary:
    if lines is None:
        lines = [_make_line(1, description="Alpha"), _make_line(2, description="Beta")]
    if output_path is None:
        output_path = Path("/tmp/srp_output.xlsx")
    if version_labels is None:
        if has_revised2:
            version_labels = ["Indicative", "Confirmed", "Revised", "Previous Year Revised"]
        elif has_revised1:
            version_labels = ["Indicative", "Confirmed", "Revised"]
        else:
            version_labels = ["Indicative", "Confirmed"]
    total_ind = sum((ln.indicative for ln in lines if ln.indicative is not None), Decimal("0"))
    total_conf = sum((ln.confirmed for ln in lines if ln.confirmed is not None), Decimal("0"))
    counts: dict[str, int] = {}
    for ln in lines:
        counts[ln.category] = counts.get(ln.category, 0) + 1
    return SrpSummary(
        lines=lines,
        total_first=total_ind,
        total_last=total_conf,
        total_indicative=total_ind,
        total_confirmed=total_conf,
        counts=counts,
        output_path=output_path,
        version_labels=version_labels,
        has_revised1=has_revised1,
        has_revised2=has_revised2,
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
        """SRP is a free tool -- requires_feature must not be set on the class."""
        assert not hasattr(SrpComparisonTool, "requires_feature") or (
            getattr(SrpComparisonTool, "requires_feature", None) is None
        ), "SRP is a free tool; requires_feature must not be set (or must be None)"


# ---------------------------------------------------------------------------
# 2. Inputs
# ---------------------------------------------------------------------------


class TestInputs:
    def test_inputs_has_four_items(self) -> None:
        """All 4 inputs present (all now optional)."""
        assert len(SrpComparisonTool.inputs) == 4

    def test_first_input_is_file_prev_year_revised(self) -> None:
        # Round 41 — first slot is now Previous Year — Revised Budget.
        fi = SrpComparisonTool.inputs[0]
        assert isinstance(fi, FileInput)
        assert fi.key == "prev_year_revised_pdf"
        assert "optional" in fi.label.lower()

    def test_second_input_is_file_indicative(self) -> None:
        # Round 41 — order changed: prev_year_revised is now first.
        fi = SrpComparisonTool.inputs[1]
        assert isinstance(fi, FileInput)
        assert fi.key == "indicative_pdf"
        assert "optional" in fi.label.lower()

    def test_third_input_is_file_confirmed(self) -> None:
        fi = SrpComparisonTool.inputs[2]
        assert isinstance(fi, FileInput)
        assert fi.key == "confirmed_pdf"
        assert "optional" in fi.label.lower()

    def test_fourth_input_is_file_revised(self) -> None:
        fi = SrpComparisonTool.inputs[3]
        assert isinstance(fi, FileInput)
        assert fi.key == "revised_pdf"
        assert "optional" in fi.label.lower() or "revised" in fi.label.lower()

    def test_output_is_none(self) -> None:
        """output picker removed -- output is auto-derived in run()."""
        assert SrpComparisonTool.output is None

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
        assert HL_MISMATCH in SrpComparisonTool.help_text

    def test_mentions_hl_source_only_interpolated(self) -> None:
        assert HL_SOURCE_ONLY in SrpComparisonTool.help_text

    def test_free_tool_mentioned(self) -> None:
        assert "free" in SrpComparisonTool.help_text.lower()

    def test_mentions_revised(self) -> None:
        assert "Revised" in SrpComparisonTool.help_text

    def test_mentions_open_output_folder(self) -> None:
        assert "Open output folder" in SrpComparisonTool.help_text

    def test_mentions_any_two(self) -> None:
        """Help text must explain that any 2 versions are enough."""
        text = SrpComparisonTool.help_text.lower()
        assert "any 2" in text or "at least 2" in text or "any two" in text


# ---------------------------------------------------------------------------
# 4. run() -- happy path (all unchanged, 2-way)
# ---------------------------------------------------------------------------


class TestRunHappyPath:
    def _run(self, tmp_path: Path, summary: SrpSummary) -> Any:
        tool = SrpComparisonTool()
        with patch("tools.srp.frame.logic.generate_srp_comparison", return_value=summary):
            return tool.run(
                {
                    "indicative_pdf": str(tmp_path / "ind.pdf"),
                    "confirmed_pdf": str(tmp_path / "conf.pdf"),
                },
                _noop_progress,
            )

    def test_success_status(self, tmp_path: Path) -> None:
        result = self._run(tmp_path, _make_summary())
        assert result.status == "success"

    def test_table_rows_populated(self, tmp_path: Path) -> None:
        lines = [_make_line(1, description="Alpha"), _make_line(2, description="Beta")]
        result = self._run(tmp_path, _make_summary(lines=lines))
        assert result.table_rows is not None
        assert len(result.table_rows) == 2

    def test_table_columns_present(self, tmp_path: Path) -> None:
        result = self._run(tmp_path, _make_summary())
        assert result.table_columns is not None
        keys = [col["key"] for col in result.table_columns]
        assert "ref" in keys
        assert "section" in keys
        assert "description" in keys
        assert "indicative" in keys
        assert "confirmed" in keys
        assert "category" in keys

    def test_output_path_set(self, tmp_path: Path) -> None:
        out = tmp_path / "out.xlsx"
        result = self._run(tmp_path, _make_summary(output_path=out))
        assert result.output_path == out

    def test_metrics_present(self, tmp_path: Path) -> None:
        result = self._run(tmp_path, _make_summary())
        assert result.metrics is not None
        assert len(result.metrics) >= 3
        labels = [m[0] for m in result.metrics]
        assert "Net variance" in labels

    def test_last_output_path_set_after_run(self, tmp_path: Path) -> None:
        """_last_output_path must be set after a successful run."""
        out = tmp_path / "out.xlsx"
        summary = _make_summary(output_path=out)
        tool = SrpComparisonTool()
        assert tool._last_output_path is None
        with patch("tools.srp.frame.logic.generate_srp_comparison", return_value=summary):
            tool.run(
                {
                    "indicative_pdf": str(tmp_path / "ind.pdf"),
                    "confirmed_pdf": str(tmp_path / "conf.pdf"),
                },
                _noop_progress,
            )
        assert tool._last_output_path is not None

    def test_run_auto_derives_output_path(self, tmp_path: Path) -> None:
        """run() must build an output path next to the FIRST provided file."""
        ind = tmp_path / "2026_SRP_Indicative.pdf"
        ind.write_bytes(b"")
        out = tmp_path / "auto_out.xlsx"
        summary = _make_summary(output_path=out)
        tool = SrpComparisonTool()
        captured: dict[str, Any] = {}

        def fake_generate(**kwargs: Any) -> SrpSummary:
            captured.update(kwargs)
            return summary

        with patch("tools.srp.frame.logic.generate_srp_comparison", side_effect=fake_generate):
            tool.run(
                {
                    "indicative_pdf": str(ind),
                    "confirmed_pdf": str(tmp_path / "conf.pdf"),
                },
                _noop_progress,
            )

        assert "output_file" in captured
        derived: Path = captured["output_file"]
        assert derived.parent == tmp_path, "output must be next to the first provided file"
        assert derived.name.startswith("SRP_Compare_"), f"unexpected name: {derived.name}"
        assert derived.suffix == ".xlsx"

    def test_run_auto_derives_output_path_non_indicative(self, tmp_path: Path) -> None:
        """When indicative is absent, output must be next to the first provided file."""
        conf = tmp_path / "2026_SRP_Confirmed.pdf"
        conf.write_bytes(b"")
        rev1 = tmp_path / "2026_SRP_Rev1.pdf"
        rev1.write_bytes(b"")
        out = tmp_path / "auto_out.xlsx"
        summary = _make_summary(
            output_path=out,
            version_labels=["Confirmed", "Revised"],
        )
        tool = SrpComparisonTool()
        captured: dict[str, Any] = {}

        def fake_generate(**kwargs: Any) -> SrpSummary:
            captured.update(kwargs)
            return summary

        with patch("tools.srp.frame.logic.generate_srp_comparison", side_effect=fake_generate):
            tool.run(
                {
                    "confirmed_pdf": str(conf),
                    "revised_pdf": str(rev1),
                },
                _noop_progress,
            )

        assert "output_file" in captured
        derived = captured["output_file"]
        # Output must be next to conf (the first provided file), not rev1
        assert derived.parent == tmp_path
        assert derived.name.startswith("SRP_Compare_")

    def test_run_optional_revised_not_passed_when_empty(self, tmp_path: Path) -> None:
        """Empty revised1/revised2 paths must resolve to None."""
        out = tmp_path / "out.xlsx"
        summary = _make_summary(output_path=out)
        tool = SrpComparisonTool()
        captured: dict[str, Any] = {}

        def fake_generate(**kwargs: Any) -> SrpSummary:
            captured.update(kwargs)
            return summary

        with patch("tools.srp.frame.logic.generate_srp_comparison", side_effect=fake_generate):
            tool.run(
                {
                    "indicative_pdf": str(tmp_path / "ind.pdf"),
                    "confirmed_pdf": str(tmp_path / "conf.pdf"),
                    "revised_pdf": "",
                    "prev_year_revised_pdf": "  ",
                },
                _noop_progress,
            )

        assert captured.get("revised_pdf") is None
        assert captured.get("prev_year_revised_pdf") is None

    def test_run_passes_revised_pdfs_when_provided(self, tmp_path: Path) -> None:
        """Non-empty revised1/revised2 paths must be forwarded."""
        r1 = tmp_path / "rev1.pdf"
        out = tmp_path / "out.xlsx"
        summary = _make_summary(output_path=out, has_revised1=True)
        tool = SrpComparisonTool()
        captured: dict[str, Any] = {}

        def fake_generate(**kwargs: Any) -> SrpSummary:
            captured.update(kwargs)
            return summary

        with patch("tools.srp.frame.logic.generate_srp_comparison", side_effect=fake_generate):
            tool.run(
                {
                    "indicative_pdf": str(tmp_path / "ind.pdf"),
                    "confirmed_pdf": str(tmp_path / "conf.pdf"),
                    "revised_pdf": str(r1),
                },
                _noop_progress,
            )

        # Round 41 — UI key "revised_pdf" maps to logic kwarg "revised1_pdf".
        assert captured.get("revised1_pdf") == r1

    # -----------------------------------------------------------------------
    # New: any-2-of-4 tests (Round 18)
    # -----------------------------------------------------------------------

    def test_run_with_only_two_inputs_ind_rev1_succeeds(self, tmp_path: Path) -> None:
        """Ind + Rev1 (skipping Confirmed) should succeed."""
        ind = tmp_path / "ind.pdf"
        rev1 = tmp_path / "rev1.pdf"
        out = tmp_path / "out.xlsx"
        summary = _make_summary(output_path=out, version_labels=["Indicative", "Revised"])
        tool = SrpComparisonTool()
        with patch("tools.srp.frame.logic.generate_srp_comparison", return_value=summary):
            result = tool.run(
                {
                    "indicative_pdf": str(ind),
                    "revised_pdf": str(rev1),
                },
                _noop_progress,
            )
        assert result.status == "success"

    def test_run_with_only_two_inputs_conf_rev2_succeeds(self, tmp_path: Path) -> None:
        """Conf + Rev2 (skipping Indicative and Rev1) should succeed."""
        conf = tmp_path / "conf.pdf"
        rev2 = tmp_path / "rev2.pdf"
        out = tmp_path / "out.xlsx"
        summary = _make_summary(
            output_path=out, version_labels=["Confirmed", "Previous Year Revised"]
        )
        tool = SrpComparisonTool()
        with patch("tools.srp.frame.logic.generate_srp_comparison", return_value=summary):
            result = tool.run(
                {
                    "confirmed_pdf": str(conf),
                    "prev_year_revised_pdf": str(rev2),
                },
                _noop_progress,
            )
        assert result.status == "success"

    def test_run_with_one_input_returns_error(self, tmp_path: Path) -> None:
        """Single file -> error ToolResult (no call to logic)."""
        tool = SrpComparisonTool()
        result = tool.run(
            {"indicative_pdf": str(tmp_path / "ind.pdf")},
            _noop_progress,
        )
        assert result.status == "error"
        assert result.banner_level == "danger"
        assert "2" in result.banner_text

    def test_run_with_zero_inputs_returns_error(self, tmp_path: Path) -> None:
        """No files -> error ToolResult."""
        tool = SrpComparisonTool()
        result = tool.run({}, _noop_progress)
        assert result.status == "error"
        assert result.banner_level == "danger"

    def test_run_picks_first_provided_for_output_path(self, tmp_path: Path) -> None:
        """When indicative absent, output_file is next to the first provided file."""
        conf = tmp_path / "2026_Confirmed.pdf"
        conf.write_bytes(b"")
        rev1 = tmp_path / "sub" / "2026_Rev1.pdf"
        rev1.parent.mkdir()
        rev1.write_bytes(b"")
        out = tmp_path / "out.xlsx"
        summary = _make_summary(output_path=out, version_labels=["Confirmed", "Revised"])
        captured: dict[str, Any] = {}

        def fake_generate(**kwargs: Any) -> SrpSummary:
            captured.update(kwargs)
            return summary

        tool = SrpComparisonTool()
        with patch("tools.srp.frame.logic.generate_srp_comparison", side_effect=fake_generate):
            tool.run(
                {
                    "confirmed_pdf": str(conf),
                    "revised_pdf": str(rev1),
                },
                _noop_progress,
            )

        assert "output_file" in captured
        derived = captured["output_file"]
        # Must be next to conf (tmp_path), not rev1 (tmp_path/sub)
        assert derived.parent == tmp_path


# ---------------------------------------------------------------------------
# 5. run() -- _bg set correctly per category
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
                },
                _noop_progress,
            )
        assert result.table_rows is not None
        return result.table_rows

    def test_removed_row_has_mismatch_bg(self, tmp_path: Path) -> None:
        ln = _make_line(2, indicative="1000.00", confirmed=None, category="removed")
        rows = self._run_with_lines([ln], tmp_path)
        assert rows[0]["_bg"] is not None
        assert HL_MISMATCH in rows[0]["_bg"]

    def test_new_row_has_source_bg(self, tmp_path: Path) -> None:
        ln = _make_line(4, indicative=None, confirmed="1500.00", category="new")
        rows = self._run_with_lines([ln], tmp_path)
        assert rows[0]["_bg"] is not None
        assert HL_SOURCE_ONLY in rows[0]["_bg"]

    def test_changed_net_increase_has_source_bg(self, tmp_path: Path) -> None:
        ln = _make_line(3, indicative="1000.00", confirmed="1500.00", category="changed")
        rows = self._run_with_lines([ln], tmp_path)
        assert rows[0]["_bg"] is not None
        assert HL_SOURCE_ONLY in rows[0]["_bg"]

    def test_changed_net_decrease_has_mismatch_bg(self, tmp_path: Path) -> None:
        ln = _make_line(1, indicative="2000.00", confirmed="1500.00", category="changed")
        rows = self._run_with_lines([ln], tmp_path)
        assert rows[0]["_bg"] is not None
        assert HL_MISMATCH in rows[0]["_bg"]

    def test_unchanged_row_has_no_bg(self, tmp_path: Path) -> None:
        ln = _make_line(5, category="unchanged")
        rows = self._run_with_lines([ln], tmp_path)
        assert rows[0]["_bg"] is None


# ---------------------------------------------------------------------------
# 6. run() -- 3-way / 4-way table columns present
# ---------------------------------------------------------------------------


class TestRunMultiVersionColumns:
    def test_two_way_columns_count(self, tmp_path: Path) -> None:
        """2 inputs: Ref+Sec+Desc+V1+V2+Var+%+Cat = 8 columns."""
        lines = [_make_line(1)]
        summary = _make_summary(lines=lines, version_labels=["Indicative", "Confirmed"])
        tool = SrpComparisonTool()
        with patch("tools.srp.frame.logic.generate_srp_comparison", return_value=summary):
            result = tool.run(
                {
                    "indicative_pdf": str(tmp_path / "ind.pdf"),
                    "confirmed_pdf": str(tmp_path / "conf.pdf"),
                },
                _noop_progress,
            )
        assert result.table_columns is not None
        # 3 fixed + 2 version + 1 variance + 2 trailing (%,cat) = 8
        assert len(result.table_columns) == 8

    def test_three_way_columns_count(self, tmp_path: Path) -> None:
        """3 inputs: 3 fixed + 3 version + 2 variance + 2 trailing = 10 columns."""
        lines = [_make_line(1)]
        summary = _make_summary(
            lines=lines,
            version_labels=["Indicative", "Confirmed", "Revised"],
            has_revised1=True,
        )
        tool = SrpComparisonTool()
        with patch("tools.srp.frame.logic.generate_srp_comparison", return_value=summary):
            result = tool.run(
                {
                    "indicative_pdf": str(tmp_path / "ind.pdf"),
                    "confirmed_pdf": str(tmp_path / "conf.pdf"),
                    "revised_pdf": str(tmp_path / "rev1.pdf"),
                },
                _noop_progress,
            )
        assert result.table_columns is not None
        assert len(result.table_columns) == 10

    def test_four_way_columns_count(self, tmp_path: Path) -> None:
        """4 inputs: 3 fixed + 4 version + 3 variance + 2 trailing = 12 columns."""
        lines = [_make_line(1)]
        summary = _make_summary(
            lines=lines,
            version_labels=["Indicative", "Confirmed", "Revised", "Previous Year Revised"],
            has_revised1=True,
            has_revised2=True,
        )
        tool = SrpComparisonTool()
        with patch("tools.srp.frame.logic.generate_srp_comparison", return_value=summary):
            result = tool.run(
                {
                    "indicative_pdf": str(tmp_path / "ind.pdf"),
                    "confirmed_pdf": str(tmp_path / "conf.pdf"),
                    "revised_pdf": str(tmp_path / "rev1.pdf"),
                    "prev_year_revised_pdf": str(tmp_path / "rev2.pdf"),
                },
                _noop_progress,
            )
        assert result.table_columns is not None
        assert len(result.table_columns) == 12

    def test_table_columns_adapt_to_two_inputs_no_indicative(self, tmp_path: Path) -> None:
        """Conf + Rev1 (skipping Ind): 2 version columns, 1 variance column."""
        lines = [_make_line(1)]
        summary = _make_summary(
            lines=lines,
            version_labels=["Confirmed", "Revised"],
        )
        tool = SrpComparisonTool()
        with patch("tools.srp.frame.logic.generate_srp_comparison", return_value=summary):
            result = tool.run(
                {
                    "confirmed_pdf": str(tmp_path / "conf.pdf"),
                    "revised_pdf": str(tmp_path / "rev1.pdf"),
                },
                _noop_progress,
            )
        assert result.table_columns is not None
        keys = [col["key"] for col in result.table_columns]
        assert "confirmed" in keys
        assert "revised1" in keys
        assert "var_0_1" in keys
        assert "indicative" not in keys


# ---------------------------------------------------------------------------
# 7. run() -- banner text structure
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
                },
                _noop_progress,
            )
        assert "Net variance" in result.banner_text

    def test_warning_status_when_removed(self, tmp_path: Path) -> None:
        """Category=removed (net decrease) should produce warning status."""
        tool = SrpComparisonTool()
        ln = _make_line(1, indicative="2000.00", confirmed=None, category="removed")
        summary = _make_summary(lines=[ln])
        with patch("tools.srp.frame.logic.generate_srp_comparison", return_value=summary):
            result = tool.run(
                {
                    "indicative_pdf": str(tmp_path / "ind.pdf"),
                    "confirmed_pdf": str(tmp_path / "conf.pdf"),
                },
                _noop_progress,
            )
        assert result.status == "warning"
        assert result.banner_level == "warning"


# ---------------------------------------------------------------------------
# 8. run() -- error path
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
                },
                _noop_progress,
            )
        combined = " ".join(ll.text for ll in result.log_lines)
        assert "ValueError" in combined

    def test_error_path_does_not_set_last_output(self, tmp_path: Path) -> None:
        """_last_output_path must stay None when run() errors."""
        tool = SrpComparisonTool()
        with patch(
            "tools.srp.frame.logic.generate_srp_comparison",
            side_effect=ValueError("bad file"),
        ):
            tool.run(
                {
                    "indicative_pdf": str(tmp_path / "missing.pdf"),
                    "confirmed_pdf": str(tmp_path / "missing2.pdf"),
                },
                _noop_progress,
            )
        assert tool._last_output_path is None


# ---------------------------------------------------------------------------
# 9. secondary_actions
# ---------------------------------------------------------------------------


class TestSecondaryActions:
    def test_has_open_output_folder_action(self) -> None:
        """secondary_actions must include "Open output folder"."""
        tool = SrpComparisonTool()
        actions = tool.secondary_actions()
        labels = [a[0] for a in actions]
        assert "Open output folder" in labels

    def test_open_output_folder_is_callable(self) -> None:
        tool = SrpComparisonTool()
        actions = tool.secondary_actions()
        action_map = {a[0]: a[1] for a in actions}
        assert callable(action_map["Open output folder"])


# ---------------------------------------------------------------------------
# 10. clear()
# ---------------------------------------------------------------------------


class TestClear:
    def test_clear_resets_last_output_path(self, tmp_path: Path) -> None:
        out = tmp_path / "out.xlsx"
        summary = _make_summary(output_path=out)
        tool = SrpComparisonTool()
        with patch("tools.srp.frame.logic.generate_srp_comparison", return_value=summary):
            tool.run(
                {
                    "indicative_pdf": str(tmp_path / "ind.pdf"),
                    "confirmed_pdf": str(tmp_path / "conf.pdf"),
                },
                _noop_progress,
            )
        assert tool._last_output_path is not None
        tool.clear()
        assert tool._last_output_path is None


# ---------------------------------------------------------------------------
# 11. Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_tool_registered(self) -> None:
        import tools.srp  # noqa: F401
        from toolkit.registry import _registered

        registered_ids = [cls.id for cls in _registered]
        assert SrpComparisonTool.id in registered_ids

    def test_register_idempotent(self) -> None:
        pass  #
