import { describe, it, expect, beforeAll, vi } from "vitest";
import { SELF, env } from "cloudflare:test";

// ── DB migration ──────────────────────────────────────────────────────────────

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
  return `schools.${Date.now()}.${Math.random().toString(36).slice(2)}@school.vic.edu.au`;
}

async function registerAndLogin(email: string, password = "password1234"): Promise<string> {
  await SELF.fetch("http://example.com/v1/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      password,
      first_name: "Test",
      last_name: "User",
      school_name: "Primary School",
      abn: "12345678901",
    }),
  });

  const user = await db()
    .prepare("SELECT id FROM users WHERE email = ?")
    .bind(email)
    .first<{ id: string }>();

  const tokenRow = await db()
    .prepare("SELECT token FROM email_tokens WHERE user_id = ? AND purpose = 'verify' ORDER BY rowid DESC LIMIT 1")
    .bind(user!.id)
    .first<{ token: string }>();

  await SELF.fetch("http://example.com/v1/auth/verify-email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: tokenRow!.token }),
  });

  const loginRes = await SELF.fetch("http://example.com/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, device_id: "test-device" }),
  });

  const loginBody = await loginRes.json<{ token: string }>();
  return loginBody.access_token;
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("schools routes", () => {
  // ── 1. Create a second school ─────────────────────────────────────────────
  it("POST /v1/schools creates a second school linked as member", async () => {
    const email = uniqueEmail();
    const token = await registerAndLogin(email);

    const res = await SELF.fetch("http://example.com/v1/schools", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        name: "Second Secondary College",
        abn: "98765432100",
        address: "2 School Rd",
        suburb: "Carlton",
        postcode: "3053",
        state: "VIC",
      }),
    });
    expect(res.status).toBe(201);

    const body = await res.json<{ school: { id: string; name: string } }>();
    expect(body.school).toBeDefined();
    expect(body.school.name).toBe("Second Secondary College");

    // Verify the link is 'member' role
    const user = await db()
      .prepare("SELECT id FROM users WHERE email = ?")
      .bind(email)
      .first<{ id: string }>();

    const link = await db()
      .prepare("SELECT role FROM user_schools WHERE user_id = ? AND school_id = ?")
      .bind(user!.id, body.school.id)
      .first<{ role: string }>();

    expect(link?.role).toBe("member");
  });

  // ── 2. Create school without auth returns 401 ────────────────────────────
  it("POST /v1/schools without auth returns 401", async () => {
    const res = await SELF.fetch("http://example.com/v1/schools", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "Unauth School" }),
    });
    expect(res.status).toBe(401);
  });

  // ── 3. GET /:id returns the school for a member ──────────────────────────
  it("GET /v1/schools/:id returns school for a linked user", async () => {
    const email = uniqueEmail();
    const token = await registerAndLogin(email);

    // Create a second school
    const createRes = await SELF.fetch("http://example.com/v1/schools", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ name: "Test Linked School", abn: "11223344556" }),
    });
    const createBody = await createRes.json<{ school: { id: string } }>();
    const schoolId = createBody.school.id;

    const res = await SELF.fetch(`http://example.com/v1/schools/${schoolId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status).toBe(200);

    const body = await res.json<{ school: { id: string; name: string } }>();
    expect(body.school.id).toBe(schoolId);
    expect(body.school.name).toBe("Test Linked School");
  });

  // ── 4. GET /:id returns 404 for non-member ───────────────────────────────
  it("GET /v1/schools/:id returns 404 for a school the user is not linked to", async () => {
    const email1 = uniqueEmail();
    const email2 = uniqueEmail();

    // User1 creates a school via registration
    const token2 = await registerAndLogin(email2);
    await registerAndLogin(email1); // user1 registers, creating their own school

    // Get user1's school id
    const user1 = await db()
      .prepare("SELECT id FROM users WHERE email = ?")
      .bind(email1)
      .first<{ id: string }>();

    const school1 = await db()
      .prepare("SELECT id FROM schools WHERE created_by = ? LIMIT 1")
      .bind(user1!.id)
      .first<{ id: string }>();

    // User2 tries to access user1's school
    const res = await SELF.fetch(`http://example.com/v1/schools/${school1!.id}`, {
      headers: { Authorization: `Bearer ${token2}` },
    });
    expect(res.status).toBe(404);
  });

  // ── 5. GET /:id without auth returns 401 ────────────────────────────────
  it("GET /v1/schools/:id without auth returns 401", async () => {
    const res = await SELF.fetch("http://example.com/v1/schools/sch_nonexistent");
    expect(res.status).toBe(401);
  });

  // ── 6. Create school validation: name required ───────────────────────────
  it("POST /v1/schools returns 400 if name is missing", async () => {
    const email = uniqueEmail();
    const token = await registerAndLogin(email);

    const res = await SELF.fetch("http://example.com/v1/schools", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ abn: "12345678901" }),
    });
    expect(res.status).toBe(400);
  });
});
