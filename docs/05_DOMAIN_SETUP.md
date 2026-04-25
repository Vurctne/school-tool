# Domain setup — `schooltool.com.au` on Cloudflare

A practical walkthrough for registering the domain, moving DNS to Cloudflare, and wiring `api.schooltool.com.au` + `admin.schooltool.com.au` to our Workers backend.

**Timeline**: ~90 minutes of your time spread across ~24 hours (DNS propagation is the long pole).

---

## Step 0 — ABN prerequisite (5 min)

A `.com.au` domain registration requires an **Australian Business Number** (ABN) or ACN, verified in real time against the [ABR register](https://abr.business.gov.au/). Options:

- **Use Xmotor's ABN (29 654 119 089)** — register the domain against Xmotor now, transfer to ZXW later when ZXW's ABN is issued. Transfer is a free form at your registrar.
- **Wait until ZXW Investment Pty Ltd has its ABN issued**, then register.

Either works. The domain is tied to the ABN in .au's rules, but the owner can transfer between entities.

---

## Step 1 — Register `schooltool.com.au` (~15 min)

`.com.au` is not available through Cloudflare Registrar. You need an AU-accredited registrar.

Recommended (ordered by price + reputation):
- **Synergy Wholesale** via a reseller like Crazy Domains, ~AU$22/yr. Fast, reliable.
- **VentraIP** — AU$25/yr, good support, clean UI.
- **Netregistry** — well-known, slightly pricier (~AU$30/yr).

Steps (identical at any registrar):

1. Open the registrar's site, search `schooltool.com.au`, confirm availability.
2. Add to cart, register for 2 years (longer gives slightly better trust signals; not critical).
3. At checkout: supply the ABN (29 654 119 089 for Xmotor, or ZXW's when issued). Registrar checks this against ABR live.
4. Fill in registrant contact (your name, Vurctne@gmail.com, address).
5. **DO NOT** buy the registrar's "web hosting", "email", "SSL" add-ons — Cloudflare handles all of that for free.
6. Pay. You'll get a confirmation email with the registration details within minutes.

---

## Step 2 — Add the domain to Cloudflare (~10 min)

1. Sign in at [dash.cloudflare.com](https://dash.cloudflare.com). Use the same account where `sft-api.<your-account>.workers.dev` lives.
2. Click **+ Add a site**.
3. Enter `schooltool.com.au`, click **Continue**.
4. Select the **Free plan** (covers us well past launch scale).
5. Cloudflare scans existing DNS at the registrar — since we didn't buy hosting, there'll be nothing to import. Click **Continue**.
6. Cloudflare gives you **two nameservers**, e.g.:
   ```
   alice.ns.cloudflare.com
   bob.ns.cloudflare.com
   ```
   (Yours will be different; Cloudflare assigns them.)

---

## Step 3 — Change nameservers at the AU registrar (~5 min + 1-24 hr propagation)

In your registrar's control panel:

1. Find **Domains** → `schooltool.com.au` → **Nameservers** (sometimes labelled *DNS servers*).
2. Switch from the registrar's default nameservers to **Custom nameservers**.
3. Paste the two Cloudflare nameservers from step 2.
4. Save.

Cloudflare will email you once the change propagates (usually 1–2 hours, can be up to 24). After this your domain is officially "on Cloudflare".

---

## Step 4 — Wire the subdomains to the Worker (~10 min)

Once Cloudflare reports the domain as active:

### Option A — Via Cloudflare dashboard (clicks)

1. In the domain's dashboard: **Workers & Pages** → **Routes** (or the Worker's detail page → **Custom Domains**).
2. Click **Add Custom Domain**.
3. Enter `api.schooltool.com.au`. Confirm. Cloudflare auto-issues a cert (~30 s).
4. Repeat for `admin.schooltool.com.au` (harmless to add now; admin Worker lands in M4).

### Option B — Via `wrangler` CLI (one command)

```powershell
cd backend
npx wrangler deployments list
# confirm the Worker name is sft-api

# Add custom domains:
npx wrangler deployment create-custom-domain --name api.schooltool.com.au
# or edit wrangler.toml (already prepared — see §5 below) then deploy
npx wrangler deploy
```

---

## Step 5 — Pre-wired code changes (already done in this repo)

I've pre-prepared the config so the switch is a single-line edit on your side.

### `backend/wrangler.toml`

A commented `[routes]` stanza sits ready:

```toml
# Uncomment once schooltool.com.au is live in Cloudflare.
# [[routes]]
# pattern = "api.schooltool.com.au/*"
# zone_name = "schooltool.com.au"
# custom_domain = true
```

Uncomment the three lines → `npx wrangler deploy` → the Worker now serves `api.schooltool.com.au/*`.

### `app_metadata.py` (desktop)

```python
API_BASE_URL = "https://sft-api.placeholder.workers.dev"
```

Change to:

```python
API_BASE_URL = "https://api.schooltool.com.au"
```

Then rebuild the MSIX (`Build MSIX.bat`) and redistribute.

### `store/` copy (M6)

The Microsoft Store listing privacy-policy URL becomes `https://schooltool.com.au/privacy`. I'll wire this at M6 when we write the Store listing, not earlier.

---

## Step 6 — Optional now, needed at M4 — email sending from the domain

When M4 lands (invoice PDFs + Resend for transactional email), you'll want emails from `noreply@schooltool.com.au` rather than the Resend sandbox domain. Resend needs three DNS records under the `schooltool.com.au` zone:

- `TXT` for SPF: `v=spf1 include:amazonses.com ~all`
- `CNAME` for DKIM: `resend._domainkey.schooltool.com.au → <value from Resend dashboard>`
- `TXT` for DMARC: `_dmarc.schooltool.com.au → v=DMARC1; p=none; rua=mailto:Vurctne@gmail.com`

Exact values come from the Resend dashboard's "Add domain" flow. I'll add a `docs/06_EMAIL_SETUP.md` walkthrough when M4 ships — flag to me if you want it sooner.

---

## After you're live — tell me two things

1. The nameserver pair Cloudflare assigned (first run of step 2).
2. Confirmation that `api.schooltool.com.au` resolves (you'll get an email from Cloudflare, or run `nslookup api.schooltool.com.au`).

Then I'll:
- Uncomment the `wrangler.toml` routes block.
- Flip `API_BASE_URL` in `app_metadata.py`.
- Rebuild the MSIX.
- Run the end-to-end smoke test from the desktop against the real domain.

~10 minutes of my work once your side is done.

---

## Cost summary

| Item | One-off | Recurring |
|---|---|---|
| `.com.au` domain, 2-year registration | ~AU$44 | ~AU$22/yr after |
| Cloudflare (Free plan) | $0 | $0 |
| SSL (Universal SSL via Cloudflare) | $0 | $0 |
| Resend (100 emails/day free tier, then $20/mo at 50k) | $0 | Free until volume |

**Expected total for v2.0.0 launch phase: ~AU$44 one-off, then AU$22/yr.**

---

## If you hit a snag

- **Registrar refuses the ABN** → the ABN probably has a status other than "active" at ABR. Check at [abr.business.gov.au](https://abr.business.gov.au/). Xmotor's 29 654 119 089 should work.
- **Cloudflare nameserver change not propagating** → allow 24 hours before worrying. Use [whatsmydns.net](https://www.whatsmydns.net/) to watch the propagation.
- **Worker not responding on `api.schooltool.com.au`** → check Cloudflare dashboard → Workers → Custom Domains; the cert issuance shows a green tick when ready (~30 s).
- **Anything else** → paste the error here and I'll debug.
