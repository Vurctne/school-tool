"""Tests for tools/refined_pal_search/frame.py."""

from __future__ import annotations

from unittest.mock import patch

from tools.refined_pal_search.frame import PAL_URL, RefinedPalSearchTool


def _noop_progress(_pct: int, _msg: str) -> None:
    return None


# ---------------------------------------------------------------------------
# Structural conformance
# ---------------------------------------------------------------------------


class TestStructuralConformance:
    def test_id(self) -> None:
        assert RefinedPalSearchTool.id == "refined-pal-search"

    def test_group(self) -> None:
        assert RefinedPalSearchTool.group == "Search"

    def test_label(self) -> None:
        assert RefinedPalSearchTool.label == "Refined PAL Search"

    def test_short(self) -> None:
        assert RefinedPalSearchTool.short == "PAL"

    def test_primary_button(self) -> None:
        assert RefinedPalSearchTool.primary_button == "Open Refined PAL Search"

    def test_primary_button_style_is_large(self) -> None:
        # Round 19 — launcher tools opt into the larger button style.
        assert RefinedPalSearchTool.primary_button_style == "Large.Accent.TButton"

    def test_no_inputs(self) -> None:
        assert RefinedPalSearchTool.inputs == []

    def test_no_output(self) -> None:
        assert RefinedPalSearchTool.output is None

    def test_requires_feature_is_none(self) -> None:
        assert RefinedPalSearchTool.requires_feature is None

    def test_pal_url(self) -> None:
        assert PAL_URL == "https://pal.schooltool.com.au/"

    def test_help_text_mentions_pal(self) -> None:
        assert "PAL" in RefinedPalSearchTool.help_text


# ---------------------------------------------------------------------------
# run() — opens browser
# ---------------------------------------------------------------------------


class TestRun:
    def test_run_calls_webbrowser_open_with_pal_url(self) -> None:
        tool = RefinedPalSearchTool()
        with patch(
            "tools.refined_pal_search.frame.webbrowser.open", return_value=True
        ) as mock_open:
            result = tool.run({}, _noop_progress)

        mock_open.assert_called_once_with(PAL_URL)
        assert result.status == "success"
        assert PAL_URL in result.banner_text

    def test_run_returns_warning_when_no_browser(self) -> None:
        tool = RefinedPalSearchTool()
        with patch("tools.refined_pal_search.frame.webbrowser.open", return_value=False):
            result = tool.run({}, _noop_progress)

        assert result.status == "warning"
        # Plain-English banner; URL is surfaced in the log lines so the user
        # can copy and paste it into a browser manually (Round 20).
        assert "default browser" in result.banner_text.lower()
        assert any(PAL_URL in line.text for line in result.log_lines)

    def test_run_returns_error_on_exception(self) -> None:
        tool = RefinedPalSearchTool()
        with patch(
            "tools.refined_pal_search.frame.webbrowser.open",
            side_effect=RuntimeError("simulated browser launch failure"),
        ):
            result = tool.run({}, _noop_progress)

        assert result.status == "error"
        # Round 20 — banner is plain English; the original Python error is
        # preserved in the log lines for support diagnosis.
        assert "browser" in result.banner_text.lower()
        assert any("simulated browser launch failure" in line.text for line in result.log_lines)


# ---------------------------------------------------------------------------
# Secondary actions / clear / preview_update — Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    def test_secondary_actions_empty(self) -> None:
        tool = RefinedPalSearchTool()
        assert tool.secondary_actions() == []

    def test_clear_does_not_raise(self) -> None:
        tool = RefinedPalSearchTool()
        # clear() is annotated -> None per Protocol; just verify it runs cleanly.
        tool.clear()

    def test_preview_update_returns_none(self) -> None:
        tool = RefinedPalSearchTool()
        assert tool.preview_update("anything", 42.0) is None


# --
