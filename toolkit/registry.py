from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from toolkit.base_tool import BaseTool

_registered: list[type[BaseTool]] = []

# Tools that are designed but not yet shipped, OR temporarily parked.
# Rendered in the rail under "In development" — greyed out, non-clickable.
# Each tuple: (group, label, short, reason)
#
# The exploratory entries (group "Exploratory") mirror docs/Tools_in_Development.md
# §"Exploratory / future ideas". Status: ⚪ — parked, not committed to a milestone.
# Surfacing them in the rail signals the roadmap to users without committing dates.
IN_DEVELOPMENT_TOOLS: list[tuple[str, str, str, str]] = [
    (
        "Reconciliation",
        "Fortnightly Salary Comparison",
        "FS",
        "In development — fortnightly salary variance check across pay periods.",
    ),
    (
        "Reconciliation",
        "Camps Reconciliation",
        "CR",
        "Coming soon. Sample exports needed before development can start.",
    ),
    (
        "Exploratory",
        "EOY Prepayments & Revenue in Advance",
        "EP",
        "Exploratory. Year-end accrual reclassification — prepayments + revenue "
        "received in advance, with adjusting journals.",
    ),
    (
        "Exploratory",
        "Family Invoice Import Prep",
        "FI",
        "Exploratory. Prepare family invoices for CASES21 import.",
    ),
    (
        "Exploratory",
        "Sub-Program Variance & Transactions",
        "SV",
        "Exploratory. Compile sub-program budget variance plus the underlying "
        "transactions in one workbook.",
    ),
    (
        "Exploratory",
        "PDF → Excel Data Cleaner",
        "PD",
        "Exploratory. General-purpose PDF table extractor that cleans up the result for Excel.",
    ),
]


def register(tool_cls: type[BaseTool]) -> None:
    if tool_cls not in _registered:
        _registered.append(tool_cls)


def all_tools() -> list[type[BaseTool]]:
    # Import every tool package so its __init__.py's register(...) call fires.
    import tools.hyia  # noqa: F401
    import tools.master_budget  # noqa: F401

    # Operating Statement is implemented but parked under "In development" for
    # Round 15's free-tier launch. To restore: uncomment the import + register
    # call below, AND remove the entry from IN_DEVELOPMENT_TOOLS.
    # import tools.operating
    # register(OperatingStatementTool)
    import tools.refined_pal_search  # noqa: F401
    import tools.srp  # noqa: F401
    import tools.sub_program  # noqa: F401

    return sorted(_registered, key=lambda c: (c.group, c.order, c.label))
