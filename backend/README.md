# School Tool Backend

Cloudflare Workers API for School Tool v2.0. Implements the full HTTP API described in `docs/04_BACKEND_DESIGN.md`.

**Stack**: TypeScript + Hono on Cloudflare Workers · D1 (SQLite) · R2 (object storage) · Cloudflare Queues · Workers AI · Resend (transactional email).

Source of truth: [`docs/04_BACKEND_DESIGN.md`](../docs/04_BACKEND_DESIGN.md).

---

## Prerequisites

- Node.js ≥ 20
- pnpm (or npm)
- Cloudflare account with Workers, D1, R2, Queues, and AI enabled
- `wrangler` CLI authenticated: `npx wrangler login`

---

## First-time setup

### 1. Install dependencies

```bash
cd backend
pnpm install
```

### 2. Create D1 database

```bash
wrangler d1 create sft
```

Copy the returned `database_id` into `wrangler.toml` under `[[d1_databases]]`.

Then apply the schema migration:

```bash
wrangler d1 execute sft --file=migrations/0001_init.sql
```

### 3. Create R2 bucket

```bash
wrangler r2 bucket create sft-assets
```

### 4. Create the OCR queue

```bash
wrangler queues create sft-ocr
```

### 5. Provision secrets

Each secret is stored encrypted in Cloudflare — never in git or `wrangler.toml`.

```bash
wrangler secret put JWT_SECRET_USER
wrangler secret put JWT_SECRET_ADMIN
wrangler secret put ADMIN_PASSWORD_ARGON2_HASH
wrangler secret put ADMIN_TOTP_SECRET
wrangler secret put LICENCE_SIGNING_PRIVATE_KEY_ED25519
wrangler secret put RESEND_API_KEY
```

**Generating secrets:**

```bash
# JWT secrets — 32-byte random hex
openssl rand -hex 32

# Ed25519 keypair (licence signing)
# Generate with Node or Python; store the base64-encoded private key.
# Embed the matching public key in toolkit/licence.py (desktop binary).

# Argon2id hash for admin password
# Use hash-wasm locally or the Workers playground to generate the hash.
```

---

## Local development

Miniflare (bundled with wrangler) runs the Worker locally with D1, R2, and Queue stubs.

```bash
pnpm run dev
# → http://localhost:8787
# → http://localhost:8787/healthz
```

Type-check without running:

```bash
pnpm run check
```

Run tests:

```bash
pnpm run test
```

---

## Deploy

```bash
pnpm run deploy
```

This deploys to `https://sft-api.<your-account>.workers.dev`.

For a custom domain (`api.xmotor.com.au`), uncomment the `routes` block in `[env.production]` in `wrangler.toml` and add the zone to your Cloudflare account.

---

## Bindings summary

| Binding | Type | Purpose |
|---|---|---|
| `DB` | D1Database | All application data (users, licences, invoices, POs) |
| `R2` | R2Bucket | Invoice PDFs (`invoices/{id}.pdf`) and PO uploads (`pos/{id}.pdf`) |
| `AI` | Ai | OCR inference via `@cf/meta/llama-3.2-11b-vision-instruct` (M5) |
| `OCR_QUEUE` | Queue producer | Enqueue PO OCR jobs after upload |
| Cron `0 15 * * *` | Trigger | Nightly renewal reminder emails (01:00 AEST) |

---

## Observability

- **Logs**: `console.log` → Workers Logs. Live tail: `wrangler tail`.
- **Liveness**: `GET /healthz` — always returns `{"ok":true}` if the Worker is alive.
- **Readiness**: `GET /readyz` — hits D1; returns `{"ok":false}` + 503 if D1 is unreachable.
- **Audit trail**: every admin action writes a row to `admin_events` in D1.

Workers Logs retain 7 days on the free plan. Upgrade to the paid plan ($5/mo) for 30-day D1 auto-snapshots and higher log retention.

---

## SLA expectations

- Workers free tier: 100,000 requests/day, 10 ms CPU/request (burst to 50 ms). Well within expected launch traffic.
- D1: 5M reads/day, 100K writes/day on free; upgrade to paid ($5/mo) for higher limits and daily auto-backups.
- R2: 10 GB storage + 1M Class A / 10M Class B ops per month free.

---

## Security notes

- Passwords hashed with Argon2id (64 MB memory, 3 iterations, 4 parallelism) via `hash-wasm` WASM in Workers.
- Licence tokens signed with Ed25519; private key held as a Cloudflare secret, never in git.
- R2 bucket is private; PDFs served via signed URLs (5-minute TTL).
- Admin login requires password + TOTP (30-minute JWT sessions).
- Rate limiting enforced at the Cloudflare edge (configure in the dashboard under Rate Limiting Rules).
