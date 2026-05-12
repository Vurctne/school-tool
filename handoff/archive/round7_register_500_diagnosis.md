# Round 7 handoff — register HTTP 500 diagnosis + imp-11 scope-creep cleanup

**Date:** 2026-04-26
**Orchestrator:** Opus 4.7 (no sub-agent dispatched this round — surgical fixes inline)
**Round goal:** unblock manual registration so Plan A Step 3 (admin licence grant via D1 INSERT) can proceed.

---

## Symptoms going into the round

User screenshot (post-imp-11) showed:

1. **HTTP 500** on Create account with: email `vurctne@gmail.com`, password (10 chars), first/last `zili Wang`, school `MGC`, ABN `123321`.
   Error banner read: `Registration failed: HTTP 500: {'error': 'Internal Server Error'}`
2. **Layout bug** — a "Confirm password" field rendered *below* the Create account button (out of flow).
3. **Status pill** showed "No licence" (expected — user not signed in).

---

## Diagnostics performed

### Live API probes (curl from sandbox)

| Probe | Result |
|---|---|
| `GET /healthz` | `200 {"ok":true}` — Worker alive |
| `GET /readyz` | `200 {"ok":true}` — D1 reachable |
| `POST /v1/auth/register` (zod-invalid: short password) | `400` with proper `issues[]` |
| `POST /v1/auth/register` (clean valid payload) | **`500 Internal Server Error`** — reproduced |

### D1 state check

```sql
SELECT name FROM sqlite_master WHERE type='table';
-- → admin_events, email_tokens, invoices, licence_devices, licences,
--   purchase_orders, schools, sqlite_sequence, user_schools, users
SELECT count(*) FROM users;   -- 0
SELECT count(*) FROM schools; -- 0
SELECT count(*) FROM email_tokens; -- 0
```

All migrations have run. No partial inserts — the failure happens **before** `insertUser` writes
a row, OR there is no transaction and a downstream step throws but the row landed (in which
case the count would be ≥ 1 — it isn't, so failure is upstream).

### Conclusion

The 500 is from one of: `findUserByEmail`, `hashPassword` (argon2id WASM in Workers), `insertUser`,
`insertSchool`, `linkUserSchool`, or `insertEmailToken`. Hono's default error response strips the
exception message — we cannot tell from the response which one without instrumentation.

---

## Changes landed this round

### 1. `backend/src/routes/auth.ts` — TEMP DIAG: stage-tracking try/catch

Wrapped the body of `POST /register` in a `try { … } catch (err) { … }` that:

- Tracks a `stage` string variable through each step (`find_user`, `hash_password`, `insert_user`,
  `insert_school`, `link_user_school`, `insert_email_token`, `wait_until`).
- On exception: logs `{event: "auth.register.error", stage, error}` to Worker console, AND
  returns `500 {error: "register failed at stage=<stage>: <name>: <message>"}` so the actual
  failure surfaces in the response body.

This is a **diagnostic patch** — once we identify the failing stage, we should remove the verbose
500 body (it leaks internals) and return the bland generic 500 again. Tracked as TODO at the bottom
of this file.

### 2. `toolkit/user_frame.py` — removed imp-11 scope-creep

imp-11 was dispatched for 4 items: password show/hide toggle, password-rule hint label, plain-English
error rendering, mousewheel-scoped scrollable canvas. It also added a 5th, unrequested item — a
"Confirm password" field. The field was placed in a sibling `confirm_frame` packed *after* `reg_frame`
in the parent container, so it rendered below the Create account button (visible in user screenshot).

**Removed:**

- `confirm_frame` Frame and its `pack()` / `pack_forget()` calls.
- `confirm_pw_var` StringVar and `_lbl_password_row(confirm_frame, "Confirm password", …)` row.
- `_build_registration_form` second-frame parameter — now takes only `reg_frame`.
- `_toggle_register` reference to `confirm_frame.pack_forget()` / `.pack(fill="x")`.
- `_do_register` `confirm` local + `password != confirm` check.
- `_FIELD_LABELS["confirm_password"]` mapping (no longer used).

**Kept (imp-11's actual delivered items):**

- `_PasswordRow` class with Show/Hide toggle (line 138).
- "At least 10 characters." hint label below password in registration form (line 610).
- `_humanise_validation_error()` + `_format_error()` for plain-English server validation messages
  (lines 46 / 94).
- Scrollable canvas with `<Enter>` / `<Leave>` mousewheel scoping (line 282).

### 3. `ORCHESTRATION-STATUS.md` — closed imp-11

Moved imp-11 from "Active" to "Recently closed" with outcome note. Cumulative sub-agent count
held at 19 (Round 7 was orchestrator-direct, no dispatch).

---

## What user needs to do (action checklist)

In **PowerShell on Windows** (NOT in Cowork — sandbox can't do `git` / `wrangler deploy`):

```powershell
# 1. Deploy the diagnostic patch.
cd D:\Software\Productivity\Vic_School_Finance_Tools\backend
npx wrangler deploy

# 2. Trigger the failure once we have visibility.
curl -X POST https://sft-api.mfiking.workers.dev/v1/auth/register `
  -H "Content-Type: application/json" `
  -d '{"email":"diag@example.com","password":"diagpass123","first_name":"D","last_name":"Iag","school_name":"DiagSchool","abn":"99"}'

# 3. Paste the response body back into chat.
```

Expected response shape (after deploy):

```json
{"error": "register failed at stage=<one of: find_user|hash_password|insert_user|insert_school|link_user_school|insert_email_token|wait_until>: <ErrorName>: <message>"}
```

Once we have the stage + message, the fix is usually one of:

| Likely stage | Likely cause | Likely fix |
|---|---|---|
| `hash_password` | hash-wasm WASM blocked in Workers runtime | Add WASM static import or fall through harder to PBKDF2 |
| `insert_user` | Schema mismatch / NOT NULL violation | Inspect `0001_init.sql` vs `insertUser` bind list |
| `insert_school` | Same | Same |
| `insert_email_token` | FK to users(id) not yet committed (D1 statement isolation) | Reorder or use D1 batch |
| `wait_until` | `sendVerificationEmail` throws *synchronously* before `.catch` attaches | Wrap in `try {} catch {}` outer, not inner |

---

## Rollback plan

After we identify the failing stage and fix it, **the diagnostic 500 body must be reverted** (it
echoes internal exception messages, which is an info-leak we don't want long-term):

```typescript
// REVERT TO:
return c.json({ error: "Internal Server Error" }, 500);
```

Or, better, route through Hono's `app.onError(...)` in `index.ts` so all 500s get the same bland
treatment.

Also: re-add a `confirm-password` field if user wants one (currently removed as scope creep) —
but only inside `reg_frame` between the password hint and First name, NOT in a separate frame.

---

## Cross-FS sync note

When verifying user_frame.py syntax via `python -c "ast.parse(...)"` from the bash mount, the
file showed 614 null bytes from offset 39007. This is the Cowork sandbox cross-FS sync issue
already documented in CLAUDE.md gotchas — Windows-side Read shows a clean 1099-line file. The
**Windows-side file is what runs at runtime**; the bash null bytes are a sandbox-mount artifact
and harmless to the deployed app. Skip the bash-side ast.parse check until the mount catches up
(or force-rewrite via the documented `pathlib.Path(p).write_text(p.read_text())` workaround).

---

## Round 7 finding + fix

After deploy, curl returned:

```
500 {"error":"register failed at stage=hash_password: NotSupportedError: Pbkdf2 failed: iteration counts above 100000 are not supported (requested 310000)."}
```

Two things going on:

1. **Argon2id (the primary path) threw silently in production Workers.** hash-wasm's argon2id call
   failed; the `catch {}` block ate the error without logging, so we never noticed in earlier
   testing. Production-runtime WASM compilation appears restricted in this build.
2. **PBKDF2 fallback violates Workers' Web Crypto cap.** `PBKDF2_ITERATIONS = 310_000` exceeds
   Workers' hard limit of 100_000.  Web Crypto returns `NotSupportedError` and the request 500s.

### Fix landed (deploy needed)

- `backend/src/lib/argon2.ts`:
  - `PBKDF2_ITERATIONS = 100_000` (was 310_000) — sit at Workers' cap.
  - Argon2id `try/catch` now logs `console.warn({event: "argon2.hash.fallback_pbkdf2", error: …})`
    so future runs surface the WASM error instead of silently degrading.
  - Same logging added to `verifyPassword`.
  - Doc comment updated to reflect the Workers PBKDF2 cap.
- `backend/src/routes/auth.ts`:
  - Verbose 500 body reverted to bland `{"error":"Internal Server Error"}` — exception text only
    goes to `console.error` now (visible via `wrangler tail`), not the response body. Stage tracking
    via `stage` variable is kept because it has zero leak risk.

### Security note

Dropping PBKDF2 from 310k to 100k iterations is a measurable security degradation but not crypto
malpractice — Apple iCloud Keychain used PBKDF2-SHA-256 at 100k iterations for years.  For a pilot
serving ~dozens of school business managers this is acceptable.  The proper fix is making argon2id
work in Workers; tracked as a follow-up below.

### Follow-up: get argon2id working in Workers

Likely root cause: hash-wasm bundles WASM as a base64 string and calls `WebAssembly.compile(buffer)`
at runtime. Some Workers compatibility regimes require WASM to be statically imported (`import wasm
from './foo.wasm'`) so the bundler can register the module.  Two paths to try:

- **Path A:** swap to `@noble/hashes/argon2` (pure-JS argon2id).  No WASM, no compatibility risk,
  ~3-5× slower than WASM but acceptable for one hash per registration.
- **Path B:** import hash-wasm's argon2 sub-module via its static-WASM entry point if one exists,
  or vendor the .wasm file and import it statically.

Defer to a follow-up round — current PBKDF2-100k path unblocks registration immediately.

---

## Round 7 follow-up: verification email did not arrive

User reported "did not receive the link" after the green "Check your inbox" banner appeared.

### Diagnosis

`backend/src/lib/mailer.ts:38` sets the Resend `from` header to:

```typescript
from: `School Tool <${env.SUPPORT_EMAIL}>`
```

Where `env.SUPPORT_EMAIL = "Vurctne@gmail.com"` (from `wrangler.toml [vars]`). **Resend rejects
this** — `gmail.com` is not (and cannot be) a Resend-verified domain. Only Google can sign DKIM
for `gmail.com`.

The send happens inside `c.executionCtx.waitUntil(sendVerificationEmail(...).catch(...))`, so the
catch logs `{event: "mailer.verify.error", ...}` to the Worker console but the HTTP response is
already 200 by then. Visible only via `wrangler tail`.

### Manual unblock used this round

Hit `POST /v1/auth/verify-email` directly with the token pulled from D1:

```bash
TOKEN=$(d1_query "SELECT token FROM email_tokens WHERE user_id='usr_01KQ4X28ZP869QWBWJ1KGXCJ68' AND consumed_at IS NULL LIMIT 1")
curl -X POST https://sft-api.mfiking.workers.dev/v1/auth/verify-email \
  -H "Content-Type: application/json" -d "{\"token\":\"$TOKEN\"}"
# → {"ok":true}
```

D1 confirms `email_verified_at = 2026-04-26 12:47:47`. User can now sign in.

### Permanent fix paths (NOT done this round — own axis)

1. **Stopgap (one-line change):** swap `from` to `"School Tool <onboarding@resend.dev>"`. Resend's
   onboarding sender works without domain verification BUT will only deliver to the email registered
   on the Resend account. Good for dev/internal testing, not real customers.
2. **Production fix:** verify `schooltool.com.au` in Resend (requires the domain to be registered —
   already a Phase 7 / M6 blocker per CLAUDE.md "Open blockers"). Add DKIM + SPF + DMARC records.
   Switch `from` to `"School Tool <noreply@schooltool.com.au>"`. Keep `Vurctne@gmail.com` only as
   a `Reply-To` header so support replies still come back to the right inbox.
3. **For test accounts going forward:** the manual `verify-email` curl above is the unblock —
   keep it in your back pocket while domain isn't verified.

Tracked separately. Did NOT add to this round's deploy because it doesn't block the immediate test
loop (sign in → licence grant → test paid tools).

---

## Open items going forward

- [x] **(this round)** Get stage+message from a deployed register call.
- [x] **(this round)** Fix the actual register failure (PBKDF2 100k cap).
- [x] **(this round)** Revert diagnostic 500 verbose body.
- [x] **(this round)** Manually verify Vurctne@gmail.com via direct API call.
- [ ] **(user, this round)** Sign in to the desktop app with `vurctne@gmail.com` + the password
      you used at registration. Confirm the User tab flips from sign-in form to signed-in view.
- [x] **(after sign-in)** Plan A Step 3 — admin licence grant via D1 INSERT for the test account.
      Inserted `lic_0001MYW2M0BBQRVA9N0M2A0VXM` (school `sch_01KQ4X28ZPFW6P152TBXCM9XC4`,
      features `["sub_program","operating"]`, expires 2027-04-26 12:52:16 UTC, source
      `admin_grant`). Audit row written to `admin_events`.
- [x] **(after Step 3)** Discovered `toolkit/licence.py` uses placeholder
      `__EMBEDDED_AT_BUILD_TIME__` for `PUBLIC_KEY_BASE64`; signature verification fails closed
      so the pill stayed "Expired" after Refresh. Fixed: `PUBLIC_KEY_BASE64` now reads from
      `app_metadata.LICENCE_PUBLIC_KEY` via `_load_public_key_b64()` at module load. Tests
      that patch `lic.PUBLIC_KEY_BASE64` continue to work unchanged.
- [ ] **(user)** Restart desktop app to pick up `licence.py` change, click Refresh licence,
      expect pill = "Active until 2027-04-26".
- [ ] **(after pill flips active)** Plan A Step 4 — open Sub-Program Budget Report; confirm
      it's clickable from the left rail and not blocked by the licence gate. Run a sample
      PDF through it end-to-end.
- [ ] **(future polish)** Make argon2id work in Workers (Path A or Path B above) and lift the
      degraded PBKDF2 fallback.
- [ ] **(future polish)** Fix the mailer FROM (Path 1 stopgap or Path 2 production above).

---

## Context for next round

- D1 database id: `d39a34c5-4247-40ec-be19-bcc914bcd4fe` (binding `DB`).
- Worker URL: `https://sft-api.mfiking.workers.dev`.
- Pricing model decisions are documented in `docs/06_PRICING.md` (this round did not touch pricing).
- Phases 4 (M8 Camps), 5 (M4 build with credits), 6 (M5 OCR), 7 (M6 release) remain in their
  current paused/blocked state — Round 7 was a pure unblock-the-test-loop dispatch.
