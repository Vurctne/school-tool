# `_agent-prompts/` — Sub-agent prompt templates

Created 2026-04-25 as part of the Orchestrator + Sub-agent reorganisation Step 4.

These six templates are what the orchestrator (Opus 4.7) substitutes into the `Agent` tool's `prompt` parameter when dispatching a sub-agent (Sonnet 4.6).

---

## Files

| File | Role | Use when… |
| --- | --- | --- |
| `discovery-agent.md` | Discovery (read-only investigation, structured report) | Inventorying existing code; reading external specs; field-layout reports on sample files |
| `implementer-agent.md` | Implementer (write new code, scoped) | Adding a new module / route / template / test fixture from scratch |
| `refactor-agent.md` | Refactor (modify existing code, preserve behaviour) | Splitting a dataclass; renaming a function; extracting a helper |
| `tester-agent.md` | Tester (write tests OR run tests) | Encoding a new assertion; running pytest/vitest; reporting failures verbatim |
| `code-reviewer-agent.md` | Code-reviewer (independent review, no shared context) | End-of-phase audit of all diffs |
| `fixer-agent.md` | Fixer (last-resort scoped fix after 2 prior failures) | Rare; only after Implementer/Tester has failed twice on the same scope |

---

## How the orchestrator dispatches a sub-agent

Mechanically:

```
1. Pick the template based on the task type.
2. Read the template file.
3. Substitute placeholders:
   - {{CONTEXT_SUMMARY}}         → full content of CONTEXT-SUMMARY.md
   - {{TASK_BRIEF}}              → the task description
   - {{FILES_IN_SCOPE}}          → exact paths (allowed read/write/edit)
   - {{ACCEPTANCE}}              → measurable success criteria
   - {{ROLE_SPECIFIC_FIELDS}}    → fields unique to a template (e.g. {{TESTS_TO_PRESERVE}} on refactor template)
4. Call mcp__Agent with:
   - subagent_type: "general-purpose" (or Explore for read-only Discovery)
   - model: "sonnet"
   - prompt: the substituted text
5. Read the agent's return value; verify against the contract; reject + re-dispatch if drift.
```

Sub-agents are **not** told to read files outside their `{{FILES_IN_SCOPE}}` list. Anything they need that's not in scope must come pre-quoted in `{{TASK_BRIEF}}`.

---

## Why placeholder substitution instead of inline embedding

The user's Step-4 spec said the templates must contain "CONTEXT-SUMMARY.md 的完整内容" as front-loaded context. Two ways to honour that:

- **(a) Inline copy:** paste CONTEXT-SUMMARY.md into each of 6 templates verbatim. Simpler at dispatch time but creates 6× maintenance burden — any CONTEXT-SUMMARY edit has to be replicated across all templates.
- **(b) Placeholder:** keep a single `CONTEXT-SUMMARY.md` and substitute it at dispatch time.

We use (b). Operationally identical from the sub-agent's perspective (it receives the full content in its prompt either way), but only one place to maintain.

---

## Conventions across all six templates

- Header is fixed: model line + one-sentence role.
- Body is structured into sections in a fixed order so the orchestrator's substitution is positional.
- Output format is **strictly markdown** (or unified diff inside a code block) — no JSON unless the role explicitly says so. Reason: the orchestrator reads the return text directly and structured markdown is faster to scan than JSON.
- Every template ends with a "Report-back format" section showing the exact shape of the response the orchestrator expects.
- Failure rule is consistent: one re-dispatch on same scope, then orchestrator escalates to Ivan.
