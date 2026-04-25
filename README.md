# School Tool v2.0.0

A Windows desktop application for Victorian Government school business managers. Ships as an MSIX through the Microsoft Store on DoE-managed Windows 11 laptops.

## What it is

The School Tool is a multi-tool shell that brings finance automation to school business offices. v2.0.0 ships three tools:

| Tool | Short | Group | Tier |
|---|---|---|---|
| HYIA Transfer Code Generator | HY | Banking | Free |
| Master Budget Compass Autofill | MB | Budget | Free |
| Sub-Program Budget Report | SP | Budget | Paid — $550 + GST/school/year |

The shell provides a unified left-rail tool picker, shared status bar, and consistent file-picker / result surfaces across all tools. Adding a new tool is a single registry entry plus a `BaseTool` subclass.

## Project structure

```
app_metadata.py      — version, author, support email, MSIX installer ID
toolkit/             — shell chrome, primitives, tokens, base_tool contract (M1)
tools/               — one sub-package per tool (hyia, master_budget, sub_program, …)
tests/               — shell-level and end-to-end smoke tests
docs/                — requirements, architecture decisions, roadmap (source of truth)
msix/                — AppxManifest template and PowerShell build scripts
packaging/           — PyInstaller spec
backend/             — Cloudflare Workers API (populated in M2)
scripts/             — build-time utilities (token porter, asset generator)
resources/           — bundled static files (DoE spec PDFs, etc.)
design_system/       — read-only design reference; do not edit
```

## Source of truth

`docs/` is authoritative:
- `docs/01_REQUIREMENTS.md` — product scope and per-tool specs
- `docs/02_ARCHITECTURE.md` — ADRs (project layout, BaseTool contract, threading, logging)
- `docs/03_ROADMAP.md` — milestone delivery plan

`design_system/` is read-only design reference. Do not modify it.

## Contribution flow

1. Install dev dependencies: `pip install -e ".[dev]"`
2. Format and lint: `ruff format . && ruff check .`
3. Type-check: `mypy .`
4. Test: `pytest`

All four must pass before merging. CI enforces them on every push and pull request.

Every Python file must begin with `from __future__ import annotations`.

## Publisher

Developed by Vurctne. Legal seller on invoices: ZXW Investment Pty Ltd (ABN <ABN TBD>).
Support: Vurctne@gmail.com
