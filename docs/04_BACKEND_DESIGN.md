# Vic School Tool — Monetization Backend Design *(revised)*

> **Revision note**: hosting moved to **Cloudflare Workers + D1 + R2**; seller is **ZXW Investment Pty Ltd**; price **$550 + GST** per school per year; first paid tool is **Sub-Program Budget Report**; user registration is required before paid-tool use; desktop has a **User tab** (account · service · invoices · support); in-app renewal prompts at 60 / 30 / 7-day-daily cadence; admin can **manually extend licence time** for any user.
>
> v2.0.0 launches with backend enabled; Master Budget joins the shell as a free tier in v2.1.0.

---

## 1. Scope & premises

### In scope at v2.0.0 launch
- Proposed free/paid tool split (see §2).
- User registration (email + password + school name + ABN).
- Email verification, sign-in, forgot-password, change-password.
- Annual invoice generation (tax invoice PDF, ZXW Investment Pty Ltd, ABN <ABN TBD>, GST status TBD, $550 + $55 GST = **$605 inc GST**).
- PO upload, storage, manual admin review (M4).
- OCR + automated matching against two standard forms (M5).
- Signed licence tokens consumed by the desktop.
- Admin dashboard: users, invoices, POs, licences, **manual time-extension**, audit log.
- In-app renewal prompts (60d / 30d / last-7d daily).
- Desktop User tab: account, service status, invoices, support mailto.

### Explicitly deferred
- Card payments / Stripe — v3.
- Multi-tier pricing, per-tool licences — v3.
- Offline grace periods > 14 days — keep at 14 at launch.
- Refunds / prorated cancellations — out of scope; annual term.

### Principles
- **Free tools work 100 % offline** with zero server calls — preserves v1 privacy posture for Master Budget once it joins the shell in v2.1.
- **Paid tools do one server hit per year at activation**, then fully offline (signed token cached locally).
- **Server collects the minimum**: email, school profile, licence status, PO metadata. Tool file contents never touch the server.

---

## 2. Free / paid split *(Recommended — can flip based on feedback)*

| Tool | Tier | Ships in |
|---|---|---|
| Sub-Program Budget Report | **Paid** | v2.0.0 (first tool) |
| Master Budget | **Free** | v2.1.0 (migrated from v1.0.2, which keeps shipping free independently until then) |
| SRP Comparison | **Free** (candidate to flip paid if MRR shortfall) | v2.1.0 |
| Operating Statement | **Paid** | v2.1.0 |
| Camps Reconciliation | **Paid** | v2.1.0 |

**Positioning copy**: *"Reconcile for free, report to Council with Pro."*

---

## 3. Licensing model — device-bound annual token

### 3.1 Licence file cached on the desktop
Path: `%LOCALAPPDATA%\Packages\<MSIX-family>\LocalCache\licence.json`.

```json
{
  "licence_id":  "lic_01HXYZABC…",
  "school_id":   "sch_01HXYZABC…",
  "school_name": "Example Secondary College",
  "email":       "user@example.edu.au",
  "device_id":   "a8c31e3b-…",
  "issued_at":   "2026-05-01T08:12:04Z",
  "expires_at":  "2027-05-01T08:12:04Z",
  "features":    ["sub_program"],
  "signature":   "ed25519:…base64…"
}
```

- Signature: Ed25519 over canonical JSON of every field except `signature`.
- Public key embedded in the desktop binary at `toolkit/licence.py`.
- Private key held by Cloudflare Workers as an encrypted secret (`wrangler secret put LICENCE_SIGNING_PRIVATE_KEY_ED25519`). Never in git.

### 3.2 Client-side verification (every launch + paid-tool click)
1. Read `licence.json` → verify Ed25519 signature → `expires_at > now`.
2. Check `feature ∈ features` for the tool being opened.
3. **Grace period**: expired ≤ 14 days still allows use with a persistent banner; beyond 14 days the paid tools lock.
4. **No network call in the hot path.** Server only contacted at activation, user-initiated *Refresh licence*, and annual renewal.

### 3.3 Renewal prompt schedule *(new)*
Computed on launch against `expires_at`:

| Days left | Prompt behaviour |
|---|---|
| > 60 | none |
| = 60 | modal once ever (flagged in `licence.json.prompts.{d60}: true`) |
| = 30 | modal once ever (flagged `d30`) |
| 7 → 1 | modal once per calendar day (keyed by `last_prompted_on`) |
| ≤ 0 and > −14 | persistent warning banner, tools still work |
| ≤ −14 | paid tools lock |

The *Renew* button opens the **User tab → Service** section and auto-generates a renewal invoice (reuses the M4 invoice flow).

### 3.4 Device binding
`device_id` is a UUIDv4 generated on first launch. Server records up to **3 devices per licence**; a 4th activation silently replaces the least-recently-seen. Hard-capped — admin handles escalations.

---

## 4. Data model *(D1 — SQLite dialect)*

```sql
-- users of the desktop app
CREATE TABLE users (
  id                TEXT PRIMARY KEY,               -- ulid 'usr_...'
  email             TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash     TEXT NOT NULL,                  -- argon2id
  first_name        TEXT,
  last_name         TEXT,
  email_verified_at INTEGER,                        -- unix seconds
  created_at        INTEGER NOT NULL,
  last_seen_at      INTEGER
);

CREATE TABLE email_tokens (                         -- verification + password reset
  token         TEXT PRIMARY KEY,                   -- cryptographically random
  user_id       TEXT NOT NULL REFERENCES users(id),
  purpose       TEXT NOT NULL,                      -- 'verify' | 'reset'
  expires_at    INTEGER NOT NULL,
  consumed_at   INTEGER
);

CREATE TABLE schools (
  id          TEXT PRIMARY KEY,                     -- 'sch_...'
  name        TEXT NOT NULL,
  abn         TEXT,                                 -- 11-digit AU Business Number
  address     TEXT,
  suburb      TEXT,
  postcode    TEXT,
  state       TEXT DEFAULT 'VIC',
  created_by  TEXT NOT NULL REFERENCES users(id),
  created_at  INTEGER NOT NULL
);

CREATE TABLE user_schools (                         -- a user can belong to ≥1 school
  user_id   TEXT NOT NULL REFERENCES users(id),
  school_id TEXT NOT NULL REFERENCES schools(id),
  role      TEXT NOT NULL DEFAULT 'member',         -- 'owner' | 'member'
  PRIMARY KEY (user_id, school_id)
);

CREATE TABLE invoices (
  id              TEXT PRIMARY KEY,                 -- 'inv_...'
  number          TEXT NOT NULL UNIQUE,             -- 'SFT-2026-0001'
  school_id       TEXT NOT NULL REFERENCES schools(id),
  user_id         TEXT NOT NULL REFERENCES users(id),
  issue_date      TEXT NOT NULL,                    -- ISO date
  due_date        TEXT NOT NULL,                    -- ISO date
  period_start    TEXT NOT NULL,
  period_end      TEXT NOT NULL,
  subtotal_cents  INTEGER NOT NULL,                 -- 55000 for $550
  gst_cents       INTEGER NOT NULL,                 -- 5500  for $55
  total_cents     INTEGER NOT NULL,                 -- 60500 for $605
  currency        TEXT NOT NULL DEFAULT 'AUD',
  status          TEXT NOT NULL DEFAULT 'issued',   -- issued | matched | paid | void
  r2_key          TEXT NOT NULL,                    -- invoices/{id}.pdf
  created_at      INTEGER NOT NULL
);

CREATE TABLE purchase_orders (
  id                TEXT PRIMARY KEY,               -- 'po_...'
  invoice_id        TEXT REFERENCES invoices(id),
  uploaded_by       TEXT NOT NULL REFERENCES users(id),
  original_filename TEXT NOT NULL,
  r2_key            TEXT NOT NULL,                  -- pos/{id}.pdf
  ocr_raw           TEXT,                           -- JSON
  extracted         TEXT,                           -- JSON
  form_template     TEXT,                           -- 'doe_standard_a' | 'doe_standard_b' | null
  match_score       REAL,
  status            TEXT NOT NULL DEFAULT 'uploaded',
  rejection_reason  TEXT,
  reviewed_by       TEXT,
  reviewed_at       INTEGER,
  created_at        INTEGER NOT NULL
);

CREATE TABLE licences (
  id              TEXT PRIMARY KEY,                 -- 'lic_...'
  school_id       TEXT NOT NULL REFERENCES schools(id),
  invoice_id      TEXT REFERENCES invoices(id),     -- null for comped / admin-granted
  po_id           TEXT REFERENCES purchase_orders(id),
  source          TEXT NOT NULL,                    -- 'purchase' | 'admin_grant' | 'admin_extend'
  issued_at       INTEGER NOT NULL,
  expires_at      INTEGER NOT NULL,
  features        TEXT NOT NULL,                    -- JSON array
  revoked_at      INTEGER,
  revoked_reason  TEXT
);

CREATE TABLE licence_devices (
  licence_id   TEXT NOT NULL REFERENCES licences(id),
  device_id    TEXT NOT NULL,
  first_seen   INTEGER NOT NULL,
  last_seen    INTEGER NOT NULL,
  os_info      TEXT,
  app_version  TEXT,
  PRIMARY KEY (licence_id, device_id)
);

CREATE TABLE admin_events (                         -- audit trail, append-only
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  actor        TEXT NOT NULL,
  action       TEXT NOT NULL,                       -- 'po.approve', 'licence.extend', …
  entity_type  TEXT NOT NULL,
  entity_id    TEXT NOT NULL,
  payload      TEXT,                                -- JSON
  at           INTEGER NOT NULL
);
```

D1 quirks respected: no `JSONB` → `TEXT` with JSON strings; no `TIMESTAMPTZ` → unix-seconds `INTEGER`; no enums → `TEXT` with app-level validation.

---

## 5. HTTP API *(Hono on Workers)*

Base URL at launch: `https://sft-api.<your-account>.workers.dev`. Custom domain (e.g. `api.xmotor.com.au`) is a one-line `wrangler.toml` change — see §8.5.

### 5.1 Client endpoints (desktop → Worker)

| Method | Path | Body / Purpose |
|---|---|---|
| `POST` | `/v1/auth/register` | `{email, password, first_name, last_name, school_name, abn}` → creates user + school + sends verification email |
| `POST` | `/v1/auth/verify-email` | `{token}` → marks `email_verified_at` |
| `POST` | `/v1/auth/login` | `{email, password, device_id}` → JWT (90-day HS256) |
| `POST` | `/v1/auth/password-reset/request` | `{email}` → email with reset token |
| `POST` | `/v1/auth/password-reset/confirm` | `{token, new_password}` |
| `POST` | `/v1/auth/password/change` | `{old_password, new_password}` (auth) |
| `GET`  | `/v1/me` | → user + school + licence summary + invoice history |
| `POST` | `/v1/schools` | `{name, abn, address, suburb, postcode}` → school (for user linking a second school later) |
| `POST` | `/v1/invoices` | `{school_id}` → creates invoice, renders PDF to R2, returns signed URL |
| `GET`  | `/v1/invoices/{id}/pdf` | → 302 to R2 signed URL (5-min TTL) |
| `POST` | `/v1/purchase-orders` | multipart `{invoice_id, file}` → stored in R2, enqueues OCR job |
| `GET`  | `/v1/purchase-orders/{id}` | status poll |
| `POST` | `/v1/licences/activate` | `{device_id, os_info, app_version}` → signed licence token (or 404 if no approved licence) |
| `POST` | `/v1/licences/refresh` | same as activate; idempotent |

### 5.2 Admin endpoints (dashboard → Worker)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/admin/auth/login` | password + TOTP → admin JWT |
| `GET`  | `/admin/dashboard` | counters: users, invoices, POs pending, MRR, last-7d signups |
| `GET`  | `/admin/users?q=&limit=&offset=` | search + paginate |
| `GET`  | `/admin/users/{id}` | detail + invoices + POs + licences + devices |
| `GET`  | `/admin/invoices` | list + filter |
| `GET`  | `/admin/purchase-orders?status=needs_review` | queue |
| `GET`  | `/admin/purchase-orders/{id}` | detail (PDF, extracted fields, invoice panel) |
| `POST` | `/admin/purchase-orders/{id}/approve` | issues licence (features default = `["sub_program"]`, period = 1 yr) |
| `POST` | `/admin/purchase-orders/{id}/reject` | `{reason}` |
| **`POST`** | **`/admin/licences/{id}/extend`** | **`{days: int, reason: string}` — shifts `expires_at` forward by N days, logs to `admin_events`** |
| **`POST`** | **`/admin/users/{id}/grant-licence`** | **`{school_id, days: int, features: [], reason: string}` — creates a licence with `source='admin_grant'` for users with no active licence** |
| `POST` | `/admin/licences/{id}/revoke` | `{reason}` |
| `GET`  | `/admin/events?entity_type=&entity_id=&limit=` | audit log |

### 5.3 Auth specifics
- **Client password**: Argon2id (via `hash-wasm` in Workers), min 10 chars. Lockout after 10 failed logins / 15 min per email-IP pair.
- **Admin**: single user. Password + TOTP (otpauth://totp/...). JWT 30-min expiry, rotated on activity.
- **Rate limiting**: Cloudflare Rate Limiting Rules on `/v1/auth/*` (10 req/min/IP) and `/admin/*` (60 req/min/IP).
- **CORS**: `api.` allows `app://*` origin for desktop; `admin.` is same-origin.

### 5.4 Manual admin actions — what they do behind the scenes

**Extend a licence** (`POST /admin/licences/{id}/extend`):
```ts
async function extendLicence(id: string, days: number, reason: string, actor: string) {
  const lic = await db.first('SELECT * FROM licences WHERE id = ?', [id]);
  if (!lic) throw new NotFound();
  const newExpiry = Math.max(lic.expires_at, nowSeconds()) + days * 86400;
  await db.run('UPDATE licences SET expires_at = ?, revoked_at = NULL WHERE id = ?',
               [newExpiry, id]);
  await db.run(
    'INSERT INTO admin_events (actor, action, entity_type, entity_id, payload, at) VALUES (?,?,?,?,?,?)',
    [actor, 'licence.extend', 'licence', id,
     JSON.stringify({ days, reason, new_expires_at: newExpiry }), nowSeconds()]
  );
  // Optional: queue an email to the user notifying them of the extension.
}
```

**Grant a fresh licence to a user with nothing active** (`POST /admin/users/{id}/grant-licence`): same shape, but inserts a new `licences` row with `source='admin_grant'`, `invoice_id=null`, `po_id=null`. Useful for: comp'd pilot schools, PO stuck in procurement, trial extensions, refund resolution.

Both actions invalidate the desktop's cached licence only **on next Refresh** — the user hits *Refresh licence* in the User tab and the server re-issues the signed token with the new expiry. No forced sync needed because nothing is broken if the user delays the refresh.

---

## 6. OCR + PO matching pipeline *(M5)*

Unchanged in shape from the Alicloud version; the Worker orchestrates it.

```
Upload → R2:pos/{po_id}.pdf
   │
   ▼ enqueue job (Cloudflare Queues)
   │
   ▼ consumer Worker
     1. Fetch PDF from R2.
     2. If text-native: pdfjs-dist extraction.
     3. If image/scanned: call OCR provider (Cloudflare AI `@cf/meta/llama-3.2-11b-vision-instruct` for layout+fields; falls back to Google Document AI if accuracy is thin).
     4. Classify template by pHash of first page (low-res render via Cloudflare Browser Rendering) → 'doe_standard_a' | 'doe_standard_b' | null.
     5. Extract fields by template-specific regex + layout boxes:
        {po_number, po_date, school_name, school_abn, supplier_name,
         invoice_ref, amount_incl_gst, amount_ex_gst, authorised_by,
         authorised_date, signature_present}
     6. Cross-check vs invoice:
        invoice_ref  ==  invoices.number                           (HARD)
        amount_incl_gst  ≈  invoices.total_cents / 100, ±$0.50     (HARD)
        school_abn  matches  schools.abn if set                    (soft)
        signature_present  ==  true                                (HARD)
        po_date  ∈ [issue_date, issue_date + 60d]                  (HARD)
     7. score = weighted sum.
     8. score ≥ 0.95  →  auto-issue licence.
        0.70–0.95     →  'needs_review'.
        < 0.70        →  'needs_review', flagged 'low_confidence'.
```

Every status is admin-overridable — OCR is never 100 %. Audit rows write to `admin_events`.

---

## 7. Invoice PDF *(ZXW Investment-branded tax invoice)*

Rendered by the Worker. PDF engine choice is **Cloudflare Browser Rendering API** (headless Chromium on Cloudflare edge, renders our HTML template to PDF). Fallback: `@react-pdf/renderer` if Browser Rendering quota or latency becomes a problem.

Template fields at render time:

```
SELLER                          BUYER
ZXW Investment Pty Ltd                  <school_name>
ABN <ABN TBD>              ABN <school.abn>
<seller_address>                <school.address>, <suburb> <state> <postcode>
Vurctne@gmail.com

TAX INVOICE — SFT-2026-0001
Issue date  01/05/2026      Due date  31/05/2026
Period      01/05/2026 → 30/04/2027

 Description                                              Amount
 School Tool Pro — Annual licence             $550.00
 GST 10 %                                                 $55.00
 ─────────────────────────────────────────────────────
 Total (inc GST)                                         $605.00

Payment: EFT to <BSB> <Acc>, reference <invoice_number>
Return signed Purchase Order to Vurctne@gmail.com
```

Seller **bank details** (BSB + account number) and **address** are still pending from Ivan — the template parameterises both so they drop in without a code change. GST is **enabled** (ZXW Investment is GST-registered).

Invoice numbering: `SFT-<yyyy>-<seq>` where `seq` is a D1 monotonic counter per year.

PDF is uploaded to R2 at `invoices/{invoice_id}.pdf`, accessed via signed URL (5-min TTL).

---

## 8. Hosting — Cloudflare Workers *(revised)*

### 8.1 Why Cloudflare
- Free tier covers launch-scale traffic (100k req/day; well under expected).
- No server to operate, no OS patching, no backups to manage (D1 auto-backs-up).
- Workers already integrates with R2 (object storage), Queues (OCR job queue), Browser Rendering (PDF), AI (OCR inference), Rate Limiting, Email Workers.
- The Cloudflare MCP is already wired into this session, so I can provision D1, R2, secrets, and deploy directly from here when M2 starts.

### 8.2 Project layout
```
backend/
├── wrangler.toml                 ← bindings: D1, R2, Queue, AI, secrets
├── package.json                  ← hono, zod, arctic (auth), hash-wasm (argon2), …
├── src/
│   ├── index.ts                  ← Hono app mount
│   ├── routes/
│   │   ├── auth.ts               ← register / verify / login / reset / change
│   │   ├── me.ts
│   │   ├── invoices.ts
│   │   ├── pos.ts
│   │   ├── licences.ts
│   │   └── admin/                ← separate subdomain mount
│   │       ├── users.ts
│   │       ├── invoices.ts
│   │       ├── pos.ts
│   │       ├── licences.ts       ← includes /extend + /grant-licence
│   │       └── events.ts
│   ├── lib/
│   │   ├── db.ts                 ← D1 wrapper
│   │   ├── jwt.ts
│   │   ├── argon2.ts
│   │   ├── ed25519.ts            ← licence signing
│   │   ├── mailer.ts             ← Resend via HTTP
│   │   ├── r2.ts                 ← signed URLs
│   │   └── ocr.ts                ← pluggable OCR provider
│   ├── workers/
│   │   ├── ocr_consumer.ts       ← Queue consumer for OCR jobs
│   │   └── renewal_reminder.ts   ← Cron trigger, nightly
│   └── templates/
│       ├── invoice.html
│       ├── invoice.css
│       └── emails/
│           ├── verify.html
│           ├── reset.html
│           ├── approved.html
│           └── extended.html
├── migrations/
│   └── 0001_init.sql
└── tests/
```

### 8.3 Bindings (`wrangler.toml` excerpt)
```toml
name = "sft-api"
main = "src/index.ts"
compatibility_date = "2026-04-01"

[[d1_databases]]
binding = "DB"
database_name = "sft"
database_id = "<from wrangler d1 create>"

[[r2_buckets]]
binding = "R2"
bucket_name = "sft-assets"

[[queues.producers]]
binding = "OCR_QUEUE"
queue = "sft-ocr"

[[queues.consumers]]
queue = "sft-ocr"
max_batch_size = 10

[ai]
binding = "AI"

[triggers]
crons = ["0 15 * * *"]  # 01:00 AEST nightly — renewal reminder emails
```

### 8.4 Secrets (`wrangler secret`)
- `LICENCE_SIGNING_PRIVATE_KEY_ED25519` — base64 Ed25519 private key.
- `JWT_SECRET_USER`, `JWT_SECRET_ADMIN` — independent HS256 keys.
- `ADMIN_PASSWORD_ARGON2_HASH`, `ADMIN_TOTP_SECRET`.
- `RESEND_API_KEY` — transactional email.
- `SELLER_BANK_BSB`, `SELLER_BANK_ACCOUNT`, `SELLER_ADDRESS` — invoice template fields.

### 8.5 Domain — required or not?
**Not strictly required.** Cloudflare gives you `https://sft-api.<your-account>.workers.dev` and `https://sft-admin.<your-account>.workers.dev` out of the box with valid TLS. That's launchable.

**Recommended before go-live** for three reasons: (1) invoices and emails sent from `*.workers.dev` look unprofessional to school finance offices; (2) Microsoft Store reviewers are happier with a mapped custom domain in the privacy URL; (3) domain swap later is painless but email already sent with the old URL ages badly.

Cheapest clean path: buy `xmotor.com.au` (~$25/yr via VentraIP or the Cloudflare registrar), point it at the Workers app, configure `api.xmotor.com.au` and `admin.xmotor.com.au`. One-line `wrangler.toml` route change, no code edit. We can launch `*.workers.dev` on M4 and swap to `xmotor.com.au` on M6 without re-deploys to the client — the desktop reads the API root from `app_metadata.API_BASE_URL`, which ships in every release.

### 8.6 Backup posture
- D1 auto-snapshots daily, 30-day retention on the paid plan ($5/mo) — sufficient.
- R2 versioning enabled on the bucket.
- Weekly export of D1 via `wrangler d1 export` to a second R2 bucket for extra belt + braces.

### 8.7 Observability
- `console.log` → Workers Logs (real-time tail + 7-day retention).
- `GET /healthz` — shallow liveness.
- `GET /readyz` — hits D1, R2, Queue.
- `admin_events` table = built-in audit log.

---

## 9. Desktop client changes

### 9.1 Account storage
- JWT + `device_id` stored in `%LOCALAPPDATA%\Packages\<MSIX>\LocalCache\account.dat`, protected with **Windows DPAPI** (`win32crypt.CryptProtectData`) — only the same user on the same machine can decrypt.
- `licence.json` adjacent to `account.dat`, contents signed (§3.1).

### 9.2 New modules
```
toolkit/
  licence.py       ← Ed25519 verify, read/write licence.json, prompt-schedule calc
  account.py       ← register / login / verify / reset / change password flows
  api_client.py    ← httpx wrapper around the server API
  crypto_win.py    ← DPAPI wrapper for account.dat
```

### 9.3 User tab
Lives in the left rail below the divider. One top-level `UserFrame` with four sub-sections (vertical stack, not tabs — matches the `Instructions` / `About` pattern):

**Account**
- Sign-in state before auth: Email, Password, *Sign in*, *Forgot password*, *Register*.
- Registration state: Email, Password, Confirm password, First name, Last name, School name, ABN, *Create account*. On submit → "Check your inbox — click the verification link, then sign back in."
- Signed-in state: Email (read-only), School name, ABN, *Change password*, *Sign out*.

**Service**
- Status pill: `No licence` / `Invoice issued` / `PO uploaded` / `Under review` / `Active until YYYY-MM-DD` / `Expired (grace period ends in N days)` / `Expired`.
- Bound devices list: name, OS, last-seen.
- Buttons: *Generate annual invoice* → *Download invoice* (post-generation) → *Upload signed PO* drop-zone → *Refresh licence*.
- When a licence is active: *Renew licence* button (opens the same flow with next period's dates pre-filled).

**Invoices**
- List all issued invoices with columns: Number, Issue date, Period, Total (inc GST), Status, *Download PDF*.

**Support**
- Big button *Email support* → `mailto:Vurctne@gmail.com` pre-filled with app version, device OS, user email, licence status, last error. Below it: a static `Feedback welcome — Vurctne@gmail.com` line.

### 9.4 Locked-tool behaviour
Paid tools (v2.0.0: `sub_program` only) are visible in the left rail with a lock glyph (●). Clicking a locked tool:
- Not signed in → navigate to **User → Account** with a banner *"Sign in to continue."*
- Signed in but no active licence → navigate to **User → Service**, show the three-step flow.
- Signed in with licence → render the tool normally.

Free tools (once Master Budget arrives in v2.1) skip all of this and render immediately.

### 9.5 Renewal prompts — implementation
On every main-window focus, `licence.py.maybe_prompt(now)` runs:
```python
def maybe_prompt(now: datetime) -> Prompt | None:
    lic = load_licence()
    if lic is None: return None
    days_left = (lic.expires_at - now).days
    if days_left == 60 and not lic.prompts.get("d60"):
        lic.prompts["d60"] = True; save_licence(lic)
        return Prompt("60 days", "Your licence expires in 60 days. Renew now?")
    if days_left == 30 and not lic.prompts.get("d30"):
        lic.prompts["d30"] = True; save_licence(lic)
        return Prompt("30 days", "Your licence expires in 30 days. Renew now?")
    if 1 <= days_left <= 7:
        today = now.date().isoformat()
        if lic.prompts.get("last_prompted_on") != today:
            lic.prompts["last_prompted_on"] = today; save_licence(lic)
            return Prompt(f"{days_left} days left",
                          f"Your licence expires in {days_left} day(s). Renew now?")
    return None
```

Modal has two buttons: *Renew* (opens User → Service → generates renewal invoice) and *Remind me later* (closes modal; flags don't re-fire for today).

### 9.6 Privacy copy update
v1's "no network calls" copy is replaced in `store/PRIVACY_POLICY.md` to describe:
- What's collected (email, school + ABN, PO content + original PDF, device id, app version, IP).
- Why (registration, invoicing, licensing, support).
- Where (Cloudflare Workers/D1/R2, region = Asia-Pacific).
- How long (live data; PO PDFs purged 7 years after licence expiry per ATO obligation).
- How to delete (email Vurctne@gmail.com).

### 9.7 No-server fallback
If the server is unreachable during activation: persistent banner, paid tool locked. Free tools (v2.1+) unaffected. The desktop is never bricked by a server outage.

---

## 10. End-to-end flow

```
 (in desktop app, first launch)
  ┌─ Click Sub-Program Budget Report in the rail
  │    → locked screen: "Sign in to continue."
  │
  ├─ User → Account → Register
  │    → verification email → click link → user returns to Sign in
  │
  ├─ User → Service → Generate annual invoice
  │    → school details form (pre-filled from registration) → POST /v1/invoices
  │    → receives signed PDF URL → opens in default viewer
  │    → user forwards invoice to school business office
  │
  ├─ User → Service → Upload signed PO
  │    → multipart POST /v1/purchase-orders
  │    → banner: "Thanks — usually instant, up to 1 business day."
  │
  │  (server OCR pipeline — M5)
  │
  ├─ auto_matched  →  licence issued, confirmation email
  ├─ needs_review  →  admin approves in dashboard → licence issued
  └─ admin_grant   →  admin clicks 'Grant licence' in /admin/users/{id} → licence issued  (§5.4)
  └─ admin_extend  →  admin extends an existing licence → expires_at shifts  (§5.4)
  │
  ▼ (back in desktop)
  └─ User → Service → Refresh licence
       → POST /v1/licences/activate → signed token
       → licence.json written, Sub-Program tool unlocks
```

---

## 11. Admin dashboard — what Ivan sees

Server-rendered HTML + HTMX at `https://sft-admin.<acct>.workers.dev` (later `admin.xmotor.com.au`). Tailwind via CDN. No SPA build.

Pages:
- **Overview** — counters: active licences, users, schools, POs pending review, MRR ($605 × active licences / 12), last-7d signups, last-7d invoices, last-7d approvals.
- **Users** — searchable list. Detail page: profile, schools, invoices, POs, licences, bound devices, *Grant licence* button, *Extend licence* button, sign-in-as (impersonate — audited).
- **Invoices** — filter by status, download PDF, mark paid manually.
- **POs — Needs review** — default landing page after login. Row → detail: PDF viewer iframe next to extracted fields, cross-check indicators (green / amber / red), invoice context panel, *Approve* / *Reject (with reason)*.
- **Licences** — list with expiry, devices. Row actions: *Extend N days*, *Revoke*.
- **Audit log** — tail of `admin_events`, filterable.

The two new operations Ivan specifically asked for — **extend time** and **grant a licence from scratch** — are first-class buttons on the user detail page and on the licence detail page, and every use logs a row in `admin_events`.

---

## 12. Security posture

1. **TLS**: Cloudflare's edge, auto-renewed.
2. **Password hashing**: Argon2id in WASM inside the Worker (`hash-wasm`), 64 MB memory cost, 3 iterations, 4 parallelism.
3. **Licence signing key**: Cloudflare secret; rotate ⇒ ship new desktop release with new public key (old licences honored until re-activation).
4. **R2 bucket private**; PDFs fetched only through signed URLs (≤ 5 min TTL).
5. **PO PDFs retained 7 years** after licence expiry (ATO tax record obligation). Purge job: nightly cron Worker.
6. **Admin**: password + TOTP; session 30 min; IP allowlist optional (TBD — may be impractical if Ivan works from multiple places).
7. **Rate limiting** on auth endpoints + brute-force lockout.
8. **Parameterised SQL via D1 prepared statements**; no string building.
9. **CORS** locked to `app://*` for client API; same-origin for admin.
10. **Privacy policy v2** shipped with v2.0.0 MSIX.

---

## 13. Open decisions (blocking or near-blocking)

1. **Seller address + bank details** — ZXW Investment Pty Ltd's registered address + BSB + account number for EFT. Blocks the first live invoice.
2. **Two standard PO forms** — both PDFs into `Samples/` (you said they're coming). Hard blocker for M5 OCR.
3. **Custom domain** — stay on `*.workers.dev` for launch and swap later, OR buy `xmotor.com.au` now. Either works; the swap is painless.
4. **Admin IP allowlist** — worth having or too restrictive? Default: off.
5. **Resend or alternative ESP** — Resend pairs nicely with Cloudflare Workers; alternatives are Postmark, Mailchannels. Default: Resend.
6. **Admin 2FA recovery** — lose your phone, how do you recover? Default: backup codes generated at setup, printed and kept offline.

---

## 14. Admin-operations cheat sheet

Because you flagged *"I should be able to add time for users"*, here's what's ready out of the box:

| Situation | Admin action | Result |
|---|---|---|
| PO approved after school paid by EFT without PO | `POST /admin/users/{id}/grant-licence` with `{days: 365, reason: "Paid by EFT; PO waived"}` | New licence row, user refreshes in app |
| User reports the tool wouldn't run for 2 weeks while their school IT was broken | `POST /admin/licences/{id}/extend` with `{days: 14, reason: "Outage compensation"}` | `expires_at += 14 days`, event logged |
| Pilot school, no invoice yet | Grant licence with `source='admin_grant'` and `days: 90` | 90-day free licence |
| Admin misclick | Set `revoked_at` via `POST /admin/licences/{id}/revoke`; re-grant cleanly if needed | Licence refuses to re-activate on refresh |

All of these write to `admin_events` for audit. The desktop honors whatever the server says the next time it refreshes the licence — no forced sync.

---

## TL;DR

- Ship v2.0.0 as Sub-Program Budget Report + User tab + backend. Backend is Cloudflare Workers + D1 + R2.
- $550 + GST per school annual, invoiced by ZXW Investment Pty Ltd (ABN <ABN TBD>).
- Registration before paid-tool use: email + password + school + ABN.
- User tab: Account · Service · Invoices · Support (support email Vurctne@gmail.com).
- Renewal prompts at 60 / 30 / last-7-daily.
- Admin dashboard with **grant licence** and **extend licence time** as first-class buttons; every action audited.
- Custom domain optional at launch; recommended before public release.
- M2 through M6 wire it all up; v2.0.0 ships to Microsoft Store at end of M6.
