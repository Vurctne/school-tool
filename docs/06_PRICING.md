# Vic School Tool — Pricing Model (Credits)

**Decision date:** 2026-04-26
**Status:** canonical — supersedes the prior "$550 + GST per school per year" model in `docs/01_REQUIREMENTS.md §1` and `docs/04_BACKEND_DESIGN.md §3` / §7.
**Effective from:** v2.0.0 launch. Implementation in M4 (paused; resumes after M7 + M8 tool builds).

---

## 1. Sales unit

The product sells **credits**, not licences. A credit is a per-school, non-expiring voucher that the school spends to activate a paid tool for one year.

- **1 credit = 1 paid tool × 1 school × 1 year of access**
- Credits **do not expire**. A credit purchased in 2026 can be redeemed in 2030.
- Credits are **owned by a school**, not by a user. A user with access to multiple schools manages each school's balance independently. Credits cannot be transferred between schools.

## 2. Pricing tiers

GST-exclusive list prices. Australian schools registered for GST claim the GST back, so the GST-exclusive price is what the school's accountant compares.

| Pack | Credits | Price (ex GST) | GST (10 %) | Total (inc GST) | Per-credit (ex GST) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Single | 1 | $39.00 | $3.90 | $42.90 | $39.00 |
| Bundle 5 | 5 | $185.00 | $18.50 | $203.50 | $37.00 |
| Bundle 10 | 10 | $350.00 | $35.00 | $385.00 | $35.00 |

Discount logic: 5-pack saves $5 vs five singles ($185 vs $195). 10-pack saves $40 vs ten singles ($350 vs $390). Volume signal aimed at multi-tool / multi-year buyers.

Seller of record: **ZXW Investment Pty Ltd**, ABN `<TBD>`, GST registered.

## 3. Tool tier mapping (v2.0.0 launch + planned)

| Tool | Tier | Credit cost | Ships in |
| --- | --- | ---: | --- |
| HYIA Transfer Code Generator | **Free** | 0 | v2.0.0 (M1) |
| Master Budget Compass Autofill | **Free** | 0 | v2.0.0 (M3-a) |
| Sub-Program Budget Report | Paid | **1 credit / year** | v2.0.0 (M3-b) |
| SRP Comparison | **Free** | 0 | v2.1.0 (M7-a) |
| Operating Statement | Paid | **1 credit / year** | v2.1.0 (M7-b) |
| Camps / Activities Reconciliation | Paid | **1 credit / year** | v2.2.0 (M8) |

Free tools never gate on credits. Paid tools require an active licence; activating a paid tool for a school **debits 1 credit** from that school's balance and creates a 1-year licence.

If the credit cost ever changes per tool (e.g. Camps Reconciliation might justify 2 credits/year due to higher value), this table is the single source of truth — update here, audit downstream.

## 4. Account model — credit ownership

Credits live on the school, not the user. Implementation:

- New column on `schools` table: `credits_balance INTEGER NOT NULL DEFAULT 0`.
- New table `credit_purchases` (audit log of all credit additions):
  ```sql
  CREATE TABLE credit_purchases (
    id              TEXT PRIMARY KEY,         -- 'cp_<ulid>'
    school_id       TEXT NOT NULL REFERENCES schools(id),
    user_id         TEXT NOT NULL REFERENCES users(id),     -- who bought
    invoice_id      TEXT REFERENCES invoices(id),            -- null for admin grants
    credits         INTEGER NOT NULL,                        -- positive
    source          TEXT NOT NULL,                           -- 'purchase' | 'admin_grant' | 'admin_refund'
    created_at      INTEGER NOT NULL
  );
  ```
- New table `credit_redemptions` (audit log of credit spends):
  ```sql
  CREATE TABLE credit_redemptions (
    id              TEXT PRIMARY KEY,         -- 'cr_<ulid>'
    school_id       TEXT NOT NULL REFERENCES schools(id),
    licence_id      TEXT NOT NULL REFERENCES licences(id),   -- the activation
    user_id         TEXT NOT NULL REFERENCES users(id),       -- who activated
    credits         INTEGER NOT NULL,                         -- positive (debit amount)
    feature         TEXT NOT NULL,                            -- 'sub_program' | 'operating' | 'camps'
    created_at      INTEGER NOT NULL
  );
  ```

`schools.credits_balance` is the pre-aggregated total = `SUM(credit_purchases.credits) - SUM(credit_redemptions.credits)`. Reconciliation cron should verify this invariant nightly.

Existing `licences` table stays — each redemption creates a new row. The `source` column on `licences` becomes one of `purchase` (via credit) | `admin_grant` (free comp) | `admin_extend` (time bonus).

## 5. Purchase flow

Replaces the per-licence flow currently sketched in `docs/04_BACKEND_DESIGN.md §10`.

```
(in desktop app, after sign-in)
  ┌─ User → Service → Buy credits
  │    → opens credit-pack picker (1/5/10)
  │    → POST /v1/credit-purchases  body: {school_id, pack: '1' | '5' | '10'}
  │
  ├─ Server creates an invoice for the pack price (ex GST + 10 % GST)
  │    invoice number SFT-<YYYY>-<seq>; r2_key invoices/{id}.pdf
  │    PDF rendered at create time (M4 work — paused)
  │    Returns {invoice, pdf_url, school.credits_balance_after_pending}
  │
  ├─ User downloads invoice → forwards to school business office
  │
  ├─ User → Service → Upload signed PO → POST /v1/purchase-orders
  │    Server stores PO in R2, status=uploaded
  │
  │  (server OCR pipeline — M5)  OR  (admin manual review — M4)
  │
  ├─ On PO approval (admin) OR successful auto-match (M5):
  │    INSERT INTO credit_purchases (...)
  │    UPDATE schools SET credits_balance = credits_balance + N WHERE id = school_id
  │    Email user: "Your N credits have been added."
  │
  ▼
  └─ Later, user activates a paid tool:
       POST /v1/licences/activate  body: {school_id, feature, device_id}
       Server checks credits_balance >= 1
       Server INSERTs licences row, INSERTs credit_redemptions row,
              UPDATEs schools SET credits_balance -= 1
       Returns signed Ed25519 licence token (existing M3-b mechanism)
       Desktop caches licence.json, paid tool unlocks
```

Refunds, voids, admin grants, and admin extends all follow the same audit-trail pattern: every change writes a row to `admin_events` and a row to `credit_purchases` (positive or negative).

## 6. Admin actions (M4)

Per `docs/04_BACKEND_DESIGN.md §5.2` admin endpoints, updated for credit model:

| Endpoint | Purpose | Credit effect |
| --- | --- | --- |
| `POST /admin/schools/{id}/credits/grant` | Comp / pilot — give credits without invoice | `+N` to `credits_balance`, source `admin_grant` |
| `POST /admin/schools/{id}/credits/revoke` | Refund / chargeback — pull credits back | `-N` from `credits_balance`, source `admin_refund` |
| `POST /admin/licences/{id}/extend` | Free time extension — adds days to existing licence | No credit change; just `expires_at += days` |
| `POST /admin/purchase-orders/{id}/approve` | Approve PO → credits land | Inserts `credit_purchases`, updates balance |

The "extend a licence" admin action stays free (doesn't cost credits) — it's a goodwill bonus when the user had an outage / migration / etc.

## 7. UI implications

### Desktop User → Service section

The Service section needs to show:
- **Credit balance pill** at the top: `Balance: 4 credits — never expire`
- **List of active licences** for this school (which paid tools are currently active, when they expire)
- **"Buy credits"** primary CTA opens a modal: 1 / 5 / 10 pack picker → invoice flow
- **"Activate <tool>"** button on each paid tool (in the rail or in the tool's frame): clicking spends 1 credit, activates the tool for 1 year. Disabled if balance < 1; clicking the disabled state opens the Buy credits modal with a "you need at least 1 credit" banner.

### Admin dashboard

Pages updated:
- **School detail** — show credit balance + history (purchases + redemptions table)
- **Credit purchases — list** — global view of all credit purchase events
- **Credit grant button** on School detail — first-class for comps / pilots / refunds

### Tool help text

The current paid-tool help text in `tools/sub_program/frame.py` says:

> This is a paid tool. An active licence for your school is required.
> Licence fee: $550 + GST per school per year (Seller: ZXW Investment Pty Ltd).

After M4 (paused) lands, this should change to:

> This is a paid tool. Activating it for your school spends 1 credit and grants
> 1 year of access. Buy credits in User → Service.
> 1 credit = $39 ex GST (5-pack $185, 10-pack $350). Seller: ZXW Investment Pty Ltd.

Don't update yet — wait until M4 work resumes.

## 8. Open questions

These are non-blocking for tool builds (M7 + M8), but need answers before M4 implementation can begin:

1. **Discount math:** the 5-pack ($37/credit) and 10-pack ($35/credit) discounts are nice but not free — does Ivan want fixed discount tiers, or a dynamic "% off" displayed at checkout?
2. **First-purchase incentive:** any free credits for new accounts (e.g. 1 free credit on email-verify so users can try a paid tool once)? Currently spec says no.
3. **Tax invoice template:** the PDF must show "School Tool — N credits" as the line item, not "School Tool Pro — Annual licence" as the current placeholder template implies. Renumber template fields when M4 resumes.
4. **Refund policy:** under what conditions does Ivan grant credit refunds? Current spec is "out of scope; annual term" but credit model could support partial refunds easily. Decide before M4.
5. **Multi-school discount:** is there a discount for buying credits in bulk for an organisation that runs multiple schools? Current 10-pack is per-school. Doesn't currently support cross-school pooling. Decide before M4.

## 9. Migration note

When M4 work resumes:

1. Update `wrangler.toml` `[vars]` block — replace `PRICING_CENTS_SUBTOTAL`/`GST_RATE`/`PRICING_CENTS_TOTAL` with credit pack tables (or hard-code three tiers).
2. Update `lib/env.ts` `Bindings` interface accordingly.
3. Add D1 migration `0002_credits.sql` — adds `credits_balance` column on schools + creates `credit_purchases` and `credit_redemptions` tables.
4. Update `routes/invoices.ts` — `POST /v1/invoices` body becomes `{school_id, pack: '1' | '5' | '10'}`; line items reflect credit pack.
5. Update `routes/licences.ts` — `POST /v1/licences/activate` checks `credits_balance >= 1` before issuing the licence; debits balance on success.
6. Update tool help text in all paid tools' `frame.py`.
7. Update `docs/01_REQUIREMENTS.md` and `docs/04_BACKEND_DESIGN.md` to point at this file as the canonical pricing source, OR inline the credit model and remove the old prose.

---

**Last updated:** 2026-04-26 (file created; supersedes prior pricing prose in 01_REQUIREMENTS + 04_BACKEND_DESIGN).
