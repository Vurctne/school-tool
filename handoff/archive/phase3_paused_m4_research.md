# Phase 3 (M4 build) — PAUSED

**Started:** 2026-04-26 05:30 UTC
**Paused:** 2026-04-26 06:00 UTC (decision: build all 6 tools first, defer M4 + payment flow)
**Orchestrator:** Opus 4.7
**Sub-agents dispatched before pause:** 1 (disco-2)

---

## Why paused

Two-part user decision on 2026-04-26:

1. **No Workers Paid Plan upgrade right now.** disco-2 surfaced that `@react-pdf/renderer` exceeds the Workers Free plan's 3 MB gzip bundle limit (community reports 4-7 MB gzipped). The three options were:
   - Upgrade to Workers Paid ($5/mo) — unblocks react-pdf and Queues
   - Switch to `pdf-lib` (~500 KB) — manual PDF layout, ~30-50% more implementer work
   - Defer PDF rendering — leave `GET /v1/invoices/:id/pdf` as 501 stub

   Ivan picked **defer** (effectively option 3), but extended the scope of "defer" to all of M4: invoice PDF + admin dashboard + admin auth + PO upload UI all wait.

2. **Pricing model pivot from per-licence to credit-based.** Old: $550 + GST per school per year per paid tool. New: credit packs (1 / 5 / 10 credits at $39 / $185 / $350 ex GST), 1 credit per paid tool per school per year, no expiry, credits owned by school. Documented in [`docs/06_PRICING.md`](../docs/06_PRICING.md) (canonical from 2026-04-26).

   The pricing change affects **invoice template wording** (line item is "N credits" not "Annual licence"), **DB schema** (new `credit_purchases` + `credit_redemptions` tables, plus a `credits_balance` column on `schools`), and **purchase + activation flows**. None of this is wired today.

Rather than build M4 against a soon-to-be-obsolete pricing model, we pause and resume after the credit design fully settles.

---

## What was already done in this aborted Phase 3 attempt

Just one thing — a Discovery dispatch (disco-2) that produced an architectural research report covering:

1. **PDF rendering strategy** — render at invoice creation time, store in R2; `GET /:id/pdf` becomes a 302 redirect to a signed URL. (Strategy "A" in the report.)
2. **Invoice template field map** — every field in `docs/04_BACKEND_DESIGN.md §7` mapped to its DB / env / computed source. **Note:** under the credit model these mappings are partially obsolete — line items become per-credit-pack instead of "Annual licence — $550".
3. **Admin auth design** — mirror existing `requireUser()` shape with `requireAdmin()` middleware, 30-min JWT TTL, hand-written HMAC-SHA1 TOTP (~50 lines), D1-backed lockout counter.
4. **Admin dashboard pattern** — same Worker, Hono sub-app at `/admin`, server-rendered HTML + HTMX `hx-post` / `hx-swap="outerHTML"` for partial updates, Tailwind via CDN.
5. **Desktop billing UI** — replace 4 stub `_coming_m4` calls in `toolkit/user_frame.py:_build_service_section()` with real `api_client` calls, `tk.filedialog.askopenfilename` for PO upload (no `tkinterdnd2` dep).

The full report is in this conversation's transcript at the disco-2 dispatch return (2026-04-26 around 05:50 UTC). Future M4 resumption should re-read that report — most of it survives the credit-pricing pivot. **Sections that need re-doing under the credit model:**
- Section 1 PDF strategy: still valid (render at create time, store in R2). Trigger now is `POST /v1/credit-purchases` not `POST /v1/invoices`.
- Section 2 Invoice template: field list largely valid (seller, buyer, amounts, dates) but the line item changes to "N credits" + per-pack pricing. Re-check.
- Sections 3, 4, 5: untouched by pricing pivot.

---

## When M4 resumes

Pre-conditions:
- M7 build done (Phase 3 next iteration: SRP Comparison + Operating Statement)
- M8 build done or formally postponed (Camps Reconciliation; blocked on samples)
- Open questions in `docs/06_PRICING.md §8` answered (5 design questions: discount math, first-purchase incentive, tax invoice line-item wording, refund policy, multi-school discount)
- Decision on Workers Paid Plan re-confirmed (the credit checkout flow + PDF rendering may still need it; or pdf-lib path may have become viable in the interim)

What changes vs the original M4 plan:
- New D1 migration `0002_credits.sql` adds `schools.credits_balance`, `credit_purchases`, `credit_redemptions` tables.
- `routes/invoices.ts:POST /v1/invoices` body changes to `{school_id, pack: '1'|'5'|'10'}`.
- `routes/licences.ts:POST /v1/licences/activate` debits 1 credit before issuing licence.
- New `routes/credit_purchases.ts` (or merge into existing routes) for the credit-pack purchase flow.
- Tool help text in all paid `frame.py` files updates from "Licence fee: $550 + GST" to credit-based language.
- `wrangler.toml` `[vars]` PRICING_CENTS_* replaced.

---

## Status of artefacts produced in this aborted phase

- `docs/06_PRICING.md` — **kept**, now canonical pricing doc.
- This file (`handoff/phase3_paused_m4_research.md`) — **kept**, M4-resume reference.
- No code in the repo was modified during the disco-2 dispatch. (Discovery agents are read-only.) No backend / frontend / test files were touched. M4 can resume from a clean baseline whenever Ivan decides.

---

## Next phase (renumbering)

| Old plan | New plan | Status |
| --- | --- | --- |
| Phase 3 (M4 build) | **paused** — resumes as Phase 5+ after tool builds | **this file** |
| Phase 4 (M5 OCR) | paused | |
| Phase 5 (M6 Store) | paused | |
| Phase 6 (M7 SRP+OS) | **new Phase 3** | active next |
| Phase 7 (M8 Camps) | new Phase 4 | blocked-on-samples |
| —— | new Phase 5 | M4 build with credit pricing |
| —— | new Phase 6 | M5 OCR (if still relevant) |
| —— | new Phase 7 | M6 Store submission |

`ORCHESTRATION-PLAN.md` and `ORCHESTRATION-STATUS.md` reflect the new ordering.
