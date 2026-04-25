import { describe, it, expect, beforeAll, vi } from "vitest";
import { SELF, env } from "cloudflare:test";

// ── DB migration helper ───────────────────────────────────────────────────────

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
  // Mock fetch to intercept Resend API calls
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : (input as Request).url;
    if (url === "https://api.resend.com/emails") {
      return new Response(JSON.stringify({ id: "mock-email-id" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    // For all other URLs (Workers runtime internals), use the real fetch
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

// ── Unique email helper ───────────────────────────────────────────────────────

function uniqueEmail(): string {
  return `test.${Date.now()}.${Math.random().toString(36).slice(2)}@school.vic.edu.au`;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

async function register(email: string, password = "password1234"): Promise<Response> {
  return SELF.fetch("http://example.com/v1/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      password,
      first_name: "Ada",
      last_name: "Lovelace",
      school_name: "Sunrise Secondary College",
      abn: "12345678901",
    }),
  });
}

async function getVerifyToken(userId: string): Promise<string | null> {
  const row = await db()
    .prepare(
      "SELECT token FROM email_tokens WHERE user_id = ? AND purpose = 'verify' AND consumed_at IS NULL ORDER BY rowid DESC LIMIT 1",
    )
    .bind(userId)
    .first<{ token: string }>();
  return row?.token ?? null;
}

async function getUserByEmail(email: string): Promise<{ id: string; email_verified_at: number | null } | null> {
  return db()
    .prepare("SELECT id, email_verified_at FROM users WHERE email = ?")
    .bind(email)
    .first<{ id: string; email_verified_at: number | null }>();
}

async function registerAndVerify(email: string, password = "password1234"): Promise<void> {
  await register(email, password);
  const user = await getUserByEmail(email);
  if (!user) throw new Error("User not found after register");
  const token = await getVerifyToken(user.id);
  if (!token) throw new Error("No verify token found");
  await SELF.fetch("http://example.com/v1/auth/verify-email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
}

async function login(email: string, password = "password1234"): Promise<{ token?: string; error?: string; user?: Record<string, unknown> }> {
  const res = await SELF.fetch("http://example.com/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, device_id: "device-abc-123" }),
  });
  return res.json<{ token?: string; error?: string; user?: Record<string, unknown> }>();
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("auth routes", () => {
  // ── 1. Register happy path ───────────────────────────────────────────────
  it("POST /register creates a user and school", async () => {
    const email = uniqueEmail();
    const res = await register(email);
    expect(res.status).toBe(200);
    const body = await res.json<{ ok: boolean }>();
    expect(body.ok).toBe(true);

    const user = await getUserByEmail(email);
    expect(user).not.toBeNull();
  });

  // ── 2. Register duplicate email is rejected ──────────────────────────────
  it("POST /register rejects duplicate email", async () => {
    const email = uniqueEmail();
    await register(email);
    const res2 = await register(email);
    expect(res2.status).toBe(409);
  });

  // ── 3. Register validates password length ────────────────────────────────
  it("POST /register rejects password shorter than 10 chars", async () => {
    const res = await register(uniqueEmail(), "short");
    expect(res.status).toBe(400);
  });

  // ── 4. Verify email happy path ───────────────────────────────────────────
  it("POST /verify-email marks email_verified_at", async () => {
    const email = uniqueEmail();
    await register(email);

    const user = await getUserByEmail(email);
    expect(user?.email_verified_at).toBeNull();

    const token = await getVerifyToken(user!.id);
    expect(token).not.toBeNull();

    const res = await SELF.fetch("http://example.com/v1/auth/verify-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    expect(res.status).toBe(200);
    const body = await res.json<{ ok: boolean }>();
    expect(body.ok).toBe(true);

    const after = await getUserByEmail(email);
    expect(after?.email_verified_at).toBeGreaterThan(0);
  });

  // ── 5. Verify rejects bad token ───────────────────────────────────────────
  it("POST /verify-email rejects an invalid token", async () => {
    const res = await SELF.fetch("http://example.com/v1/auth/verify-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: "deadbeef00000000" }),
    });
    expect(res.status).toBe(400);
  });

  // ── 6. Verify token is one-shot ───────────────────────────────────────────
  it("POST /verify-email rejects a token that has already been used", async () => {
    const email = uniqueEmail();
    await register(email);
    const user = await getUserByEmail(email);
    const token = await getVerifyToken(user!.id);

    await SELF.fetch("http://example.com/v1/auth/verify-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });

    const res2 = await SELF.fetch("http://example.com/v1/auth/verify-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    expect(res2.status).toBe(400);
  });

  // ── 7. Login requires verified email ─────────────────────────────────────
  it("POST /login rejects unverified user", async () => {
    const email = uniqueEmail();
    await register(email);
    const body = await login(email);
    expect(body.error).toBeDefined();
  });

  // ── 8. Login returns JWT ──────────────────────────────────────────────────
  it("POST /login returns a JWT after verification", async () => {
    const email = uniqueEmail();
    await registerAndVerify(email);

    const body = await login(email);
    expect(body.access_token).toBeDefined();
    expect(typeof body.access_token).toBe("string");
    expect(body.user).toBeDefined();
  });

  // ── 9. Login returns user row ─────────────────────────────────────────────
  it("POST /login response includes user with correct email", async () => {
    const email = uniqueEmail();
    await registerAndVerify(email);

    const body = await login(email);
    expect(body.user?.email).toBe(email);
  });

  // ── 10. Login rejects wrong password ────────────────────────────────────
  it("POST /login rejects wrong password", async () => {
    const email = uniqueEmail();
    await registerAndVerify(email);

    const res = await SELF.fetch("http://example.com/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password: "wrongpassword!", device_id: "dev" }),
    });
    expect(res.status).toBe(401);
  });

  // ── 11. Password reset flow ───────────────────────────────────────────────
  it("POST /password-reset/request always returns ok (anti-enumeration)", async () => {
    const res = await SELF.fetch("http://example.com/v1/auth/password-reset/request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "nonexistent@example.com" }),
    });
    expect(res.status).toBe(200);
    const body = await res.json<{ ok: boolean }>();
    expect(body.ok).toBe(true);
  });

  it("password reset flow: request and confirm work end-to-end", async () => {
    const email = uniqueEmail();
    await registerAndVerify(email);

    // Request a reset
    const reqRes = await SELF.fetch("http://example.com/v1/auth/password-reset/request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    expect(reqRes.status).toBe(200);

    // Get the reset token from DB
    const user = await getUserByEmail(email);
    const tokenRow = await db()
      .prepare("SELECT token FROM email_tokens WHERE user_id = ? AND purpose = 'reset' AND consumed_at IS NULL ORDER BY rowid DESC LIMIT 1")
      .bind(user!.id)
      .first<{ token: string }>();
    expect(tokenRow?.token).toBeDefined();

    // Confirm reset with new password
    const confirmRes = await SELF.fetch("http://example.com/v1/auth/password-reset/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: tokenRow!.token, new_password: "newpassword1234" }),
    });
    expect(confirmRes.status).toBe(200);

    // Old password no longer works
    const oldLogin = await login(email, "password1234");
    expect(oldLogin.error).toBeDefined();

    // New password works
    const newLogin = await login(email, "newpassword1234");
    expect(newLogin.access_token).toBeDefined();
  });

  // ── 13. Password change requires correct old password ────────────────────
  it("POST /password/change rejects wrong old password", async () => {
    const email = uniqueEmail();
    await registerAndVerify(email);
    const loginBody = await login(email);
    const token = loginBody.access_token!;

    const res = await SELF.fetch("http://example.com/v1/auth/password/change", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ old_password: "wrongold1234", new_password: "newpassword1234" }),
    });
    expect(res.status).toBe(400);
  });

  it("POST /password/change works with correct old password", async () => {
    const email = uniqueEmail();
    await registerAndVerify(email);
    const loginBody = await login(email);
    const token = loginBody.access_token!;

    const res = await SELF.fetch("http://example.com/v1/auth/password/change", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ old_password: "password1234", new_password: "newpassword5678" }),
    });
    expect(res.status).toBe(200);
    const body = await res.json<{ ok: boolean }>();
    expect(body.ok).toBe(true);
  });

  // ── 15. Unauthenticated change password returns 401 ──────────────────────
  it("POST /password/change without auth returns 401", async () => {
    const res = await SELF.fetch("http://example.com/v1/auth/password/change", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ old_password: "password1234", new_password: "newpassword1234" }),
    });
    expect(res.status).toBe(401);
  });
});
