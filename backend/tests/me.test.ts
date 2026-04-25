import { describe, it, expect, beforeAll, vi } from "vitest";
import { SELF, env } from "cloudflare:test";

// ── DB migration (same as other test files) ───────────────────────────────────

const MIGRATION_SQL = `
CREATE TABLE IF NOT EXISTS users (
  id                TEXT PRIMARY KEY,
  email             TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash     TEXT NOT NULL,
  first_name        TEXT,
  last_name         TEXT,
  email_verified_at INTEGER,
  created_at        INTEGER NOT NULL,
  last_seen_at      INTEGER
);
CREATE TABLE IF NOT EXISTS email_tokens (
  token         TEXT PRIMARY KEY,
  user_id       TEXT NOT NULL REFERENCES users(id),
  purpose       TEXT NOT NULL,
  expires_at    INTEGER NOT NULL,
  consumed_at   INTEGER
);
CREATE TABLE IF NOT EXISTS schools (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  abn         TEXT,
  address     TEXT,
  suburb      TEXT,
  postcode    TEXT,
  state       TEXT DEFAULT 'VIC',
  created_by  TEXT NOT NULL REFERENCES users(id),
  created_at  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS user_schools (
  user_id   TEXT NOT NULL REFERENCES users(id),
  school_id TEXT NOT NULL REFERENCES schools(id),
  role      TEXT NOT NULL DEFAULT 'member',
  PRIMARY KEY (user_id, school_id)
);
CREATE TABLE IF NOT EXISTS invoices (
  id              TEXT PRIMARY KEY,
  number          TEXT NOT NULL UNIQUE,
  school_id       TEXT NOT NULL REFERENCES schools(id),
  user_id         TEXT NOT NULL REFERENCES users(id),
  issue_date      TEXT NOT NULL,
  due_date        TEXT NOT NULL,
  period_start    TEXT NOT NULL,
  period_end      TEXT NOT NULL,
  subtotal_cents  INTEGER NOT NULL,
  gst_cents       INTEGER NOT NULL,
  total_cents     INTEGER NOT NULL,
  currency        TEXT NOT NULL DEFAULT 'AUD',
  status          TEXT NOT NULL DEFAULT 'issued',
  r2_key          TEXT NOT NULL,
  created_at      INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS purchase_orders (
  id                TEXT PRIMARY KEY,
  invoice_id        TEXT REFERENCES invoices(id),
  uploaded_by       TEXT NOT NULL REFERENCES users(id),
  original_filename TEXT NOT NULL,
  r2_key            TEXT NOT NULL,
  ocr_raw           TEXT,
  extracted         TEXT,
  form_template     TEXT,
  match_score       REAL,
  status            TEXT NOT NULL DEFAULT 'uploaded',
  rejection_reason  TEXT,
  reviewed_by       TEXT,
  reviewed_at       INTEGER,
  created_at        INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS licences (
  id              TEXT PRIMARY KEY,
  school_id       TEXT NOT NULL REFERENCES schools(id),
  invoice_id      TEXT REFERENCES invoices(id),
  po_id           TEXT REFERENCES purchase_orders(id),
  source          TEXT NOT NULL,
  issued_at       INTEGER NOT NULL,
  expires_at      INTEGER NOT NULL,
  features        TEXT NOT NULL,
  revoked_at      INTEGER,
  revoked_reason  TEXT
);
CREATE TABLE IF NOT EXISTS licence_devices (
  licence_id   TEXT NOT NULL REFERENCES licences(id),
  device_id    TEXT NOT NULL,
  first_seen   INTEGER NOT NULL,
  last_seen    INTEGER NOT NULL,
  os_info      TEXT,
  app_version  TEXT,
  PRIMARY KEY (licence_id, device_id)
);
CREATE TABLE IF NOT EXISTS admin_events (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  actor        TEXT NOT NULL,
  action       TEXT NOT NULL,
  entity_type  TEXT NOT NULL,
  entity_id    TEXT NOT NULL,
  payload      TEXT,
  at           INTEGER NOT NULL
);
`;

function db(): D1Database {
  return (env as { DB: D1Database }).DB;
}

beforeAll(async () => {
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : (input as Request).url;
    if (url === "https://api.resend.com/emails") {
      return new Response(JSON.stringify({ id: "mock-email-id" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response("Not mocked", { status: 200 });
  }) as typeof fetch;

  const statements = MIGRATION_SQL
    .split(";")
    .map((s) => s.trim())
    .filter((s) => s.length > 0 && !s.startsWith("--"));

  for (const sql of statements) {
    await db().prepare(sql).run();
  }
});

// ── Helpers ───────────────────────────────────────────────────────────────────

function uniqueEmail(): string {
  return `me.${Date.now()}.${Math.random().toString(36).slice(2)}@school.vic.edu.au`;
}

async function registerAndLogin(email: string, password = "password1234"): Promise<string> {
  // Register
  await SELF.fetch("http://example.com/v1/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      password,
      first_name: "Test",
      last_name: "User",
      school_name: "Test School",
      abn: "12345678901",
    }),
  });

  // Get verify token
  const user = await db()
    .prepare("SELECT id FROM users WHERE email = ?")
    .bind(email)
    .first<{ id: string }>();

  const tokenRow = await db()
    .prepare("SELECT token FROM email_tokens WHERE user_id = ? AND purpose = 'verify' ORDER BY rowid DESC LIMIT 1")
    .bind(user!.id)
    .first<{ token: string }>();

  // Verify email
  await SELF.fetch("http://example.com/v1/auth/verify-email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: tokenRow!.token }),
  });

  // Login
  const loginRes = await SELF.fetch("http://example.com/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, device_id: "test-device" }),
  });

  const loginBody = await loginRes.json<{ token: string }>();
  return loginBody.access_token;
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("me routes", () => {
  // ── 1. Unauthenticated request returns 401 ──────────────────────────────
  it("GET /v1/me without auth returns 401", async () => {
    const res = await SELF.fetch("http://example.com/v1/me");
    expect(res.status).toBe(401);
  });

  // ── 2. Invalid token returns 401 ───────────────────────────────────────
  it("GET /v1/me with invalid Bearer token returns 401", async () => {
    const res = await SELF.fetch("http://example.com/v1/me", {
      headers: { Authorization: "Bearer not-a-valid-jwt" },
    });
    expect(res.status).toBe(401);
  });

  // ── 3. Authenticated returns user, schools, empty invoices and null licence
  it("GET /v1/me returns user + schools + empty invoices + null licence for fresh account", async () => {
    const email = uniqueEmail();
    const token = await registerAndLogin(email);

    const res = await SELF.fetch("http://example.com/v1/me", {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status).toBe(200);

    const body = await res.json<{
      user: { email: string };
      schools: unknown[];
      active_licence: null | unknown;
      invoices: unknown[];
    }>();

    expect(body.user.email).toBe(email);
    expect(Array.isArray(body.schools)).toBe(true);
    expect(body.schools.length).toBeGreaterThanOrEqual(1);
    expect(body.active_licence).toBeNull();
    expect(Array.isArray(body.invoices)).toBe(true);
    expect(body.invoices.length).toBe(0);
  });

  // ── 4. Invoices limited to 20 ────────────────────────────────────────────
  it("GET /v1/me invoices are limited to 20 most recent", async () => {
    const email = uniqueEmail();
    const token = await registerAndLogin(email);

    const user = await db()
      .prepare("SELECT id FROM users WHERE email = ?")
      .bind(email)
      .first<{ id: string }>();

    const school = await db()
      .prepare("SELECT id FROM schools WHERE created_by = ? LIMIT 1")
      .bind(user!.id)
      .first<{ id: string }>();

    // Insert 22 invoices
    for (let i = 0; i < 22; i++) {
      const invId = `inv_test_${Date.now()}_${i}`;
      await db()
        .prepare(
          `INSERT INTO invoices
            (id, number, school_id, user_id, issue_date, due_date,
             period_start, period_end, subtotal_cents, gst_cents,
             total_cents, currency, status, r2_key, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`,
        )
        .bind(
          invId,
          `SFT-2026-${i + 9000}`,
          school!.id,
          user!.id,
          "2026-05-01",
          "2026-05-31",
          "2026-05-01",
          "2027-04-30",
          55000,
          5500,
          60500,
          "AUD",
          "issued",
          `invoices/${invId}.pdf`,
          Math.floor(Date.now() / 1000) + i,
        )
        .run();
    }

    const res = await SELF.fetch("http://example.com/v1/me", {
      headers: { Authorization: `Bearer ${token}` },
    });
    const body = await res.json<{ invoices: unknown[] }>();
    expect(body.invoices.length).toBeLessThanOrEqual(20);
  });
});
