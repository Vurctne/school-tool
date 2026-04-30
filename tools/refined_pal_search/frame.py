"""Refined PAL Search — launcher tool that opens pal.schooltool.com.au."""

from __future__ import annotations

import webbrowser
from collections.abc import Callable
from typing import Any

from toolkit.base_tool import LogLine, ProgressFn, ToolResult
from toolkit.user_errors import friendly_error

# ---------------------------------------------------------------------------
# Target URL — externally hosted Refined PAL search interface.
# ---------------------------------------------------------------------------

PAL_URL = "https://pal.schooltool.com.au/"

# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------

_HELP_TEXT = """Refined PAL Search

This tool opens the Refined PAL Search web interface in your default browser.

Refined PAL is the searchable Productivity Allocation Library hosted at
pal.schooltool.com.au.


HOW TO USE

  1. Click "Open Refined PAL Search". Your default browser will open the
     PAL Search page at https://pal.schooltool.com.au/.
  2. Use the web interface to search for what you need.
  3. The web page is hosted externally — School Tool does not control the
     web page's contents or behaviour.


IMPORTANT NOTES

  * This is a free tool — no licence is required.
  * An internet connection is required to load the web page; School Tool
     itself remains fully offline.


SUPPORT

  This tool — feedback and questions:   Vurctne@gmail.com

Please send feedback to Vurctne@gmail.com
"""


class RefinedPalSearchTool:
    id = "refined-pal-search"
    group = "Search"
    label = "Refined PAL Search"
    short = "PAL"
    order = 10
    primary_button = "Open Refined PAL Search"
    # Round 19 — launcher tools have a single CTA and benefit from a larger
    # button. The shell registers "Large.Accent.TButton" at startup; tools
    # that don't declare ``primary_button_style`` keep the default size.
    primary_button_style = "Large.Accent.TButton"
    pdf_template = None
    pdf_body = None
    help_text = _HELP_TEXT
    # No requires_feature — this is a free tool.
    requires_feature = None

    # No file inputs and no output — the tool is a pure launcher that opens
    # the PAL URL in the user's default browser via webbrowser.open().
    inputs: list[Any] = []
    output = None

    def run(self, paths: dict[str, Any], progress: ProgressFn) -> ToolResult:
        """Open PAL_URL in the default browser; report success or failure."""
        progress(50, "Opening browser…")
        try:
            opened = webbrowser.open(PAL_URL)
        except Exception as exc:
            # This tool is a single-action launcher (open the URL in the
            # default browser).  Any exception here is unambiguously a
            # browser-launch failure, so we surface a tailored message
            # instead of relying on the generic friendly_error fallback.
            # We still wrap the exception via friendly_error so the
            # "Could not open the browser:" prefix triggers the right rule.
            fe = friendly_error(RuntimeError(f"Could not open the browser: {exc}"))
            return ToolResult(
                status="error",
                banner_level="danger",
                banner_text=fe.banner,
                log_lines=[
                    LogLine("WHAT WENT WRONG", tag="heading"),
                    LogLine(fe.message, tag="danger"),
                    LogLine("HOW TO FIX IT", tag="heading"),
                    LogLine(fe.advice, tag="muted"),
                    LogLine(f"URL to copy and paste: {PAL_URL}", tag="muted"),
                    LogLine("TECHNICAL DETAIL (for support)", tag="heading"),
                    LogLine(f"{type(exc).__name__}: {exc}", tag="muted"),
                ],
                output_path=None,
            )

        progress(100, "Done.")

        if opened:
            return ToolResult(
                status="success",
                banner_level="ok",
                banner_text=f"Opened {PAL_URL} in your default browser.",
                log_lines=[
                    LogLine("Refined PAL Search", tag="heading"),
                    LogLine(f"URL: {PAL_URL}", tag="ok"),
                ],
                output_path=None,
            )

        # webbrowser.open() returned False — no usable browser registered.
        return ToolResult(
            status="warning",
            banner_level="warning",
            banner_text="No default browser is set up on this PC.",
            log_lines=[
                LogLine("WHAT WENT WRONG", tag="heading"),
                LogLine(
                    "Windows didn't return a default browser, so we couldn't "
                    "open the link automatically.",
                    tag="warning",
                ),
                LogLine("HOW TO FIX IT", tag="heading"),
                LogLine(
                    "Set Edge or Chrome as your default browser in Windows "
                    "Settings → Apps → Default apps. Or, copy the URL below "
                    "and paste it into a browser manually.",
                    tag="muted",
                ),
                LogLine(f"URL to copy and paste: {PAL_URL}", tag="muted"),
            ],
            output_path=None,
        )

    def secondary_actions(self) -> list[tuple[str, Callable[..., None]]]:
        return []

    def clear(self) -> None:
        """No per-tool state to reset; shell handles UI-level reset."""
        return None

    def preview_update(self, key: str, value: float | str) -> ToolResult | None:
        """No live-preview inputs on this tool."""
        return None
