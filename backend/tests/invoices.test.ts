import { describe, it, expect, beforeAll, vi } from "vitest";
import { SELF, env } from "cloudflare:test";
import { findInvoiceById } from "../src/lib/db";

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
  // Mock fetch to intercept Resend API calls
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
  return `inv.${Date.now()}.${Math.random().toString(36).slice(2)}@school.vic.edu.au`;
}

/**
 * Drive the full register → verify-email → login flow.
 * Returns the user_id, the school_id created at registration, and the access_token.
 */
async function registerVerifyLogin(
  email: string,
  password = "password1234",
): Promise<{ user_id: string; school_id: string; access_token: string }> {
  await SELF.fetch("http://example.com/v1/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      password,
      first_name: "Test",
      last_name: "User",
      school_name: "Sunrise Secondary College",
      abn: "12345678901",
    }),
  });

  const userRow = await db()
    .prepare("SELECT id FROM users WHERE email = ?")
    .bind(email)
    .first<{ id: string }>();
  if (!userRow) throw new Error(`registerVerifyLogin: user not found for ${email}`);
  const user_id = userRow.id;

  const tokenRow = await db()
    .prepare(
      "SELECT token FROM email_tokens WHERE user_id = ? AND purpose = 'verify' ORDER BY rowid DESC LIMIT 1",
    )
    .bind(user_id)
    .first<{ token: string }>();
  if (!tokenRow) throw new Error("registerVerifyLogin: no verify token");

  await SELF.fetch("http://example.com/v1/auth/verify-email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: tokenRow.token }),
  });

  const loginRes = await SELF.fetch("http://example.com/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, device_id: "test-device" }),
  });
  const loginBody = await loginRes.json<{ access_token: string }>();

  const schoolRow = await db()
    .prepare("SELECT id FROM schools WHERE created_by = ? LIMIT 1")
    .bind(user_id)
    .first<{ id: string }>();
  if (!schoolRow) throw new Error("registerVerifyLogin: no school found");
  const school_id = schoolRow.id;

  return { user_id, school_id, access_token: loginBody.access_token };
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("invoices routes", () => {
  // ── 1. POST /v1/invoices 400 when body missing school_id ────────────────────
  it("POST /v1/invoices returns 400 when body missing school_id", async () => {
    const { access_token } = await registerVerifyLogin(uniqueEmail());

    const res = await SELF.fetch("http://example.com/v1/invoices", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${access_token}`,
      },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(400);
    const body = await res.json<{ error: string }>();
    expect(body.error).toBe("Validation error");
  });

  // ── 2. POST /v1/invoices 401 when no Bearer token ────────────────────────────
  it("POST /v1/invoices returns 401 when no Bearer token", async () => {
    const res = await SELF.fetch("http://example.com/v1/invoices", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ school_id: "sch_whatever" }),
    });
    expect(res.status).toBe(401);
  });

  // ── 3. POST /v1/invoices 403 when school doesn't exist or isn't linked ───────
  it("POST /v1/invoices returns 403 when school is not linked to user", async () => {
    const { access_token } = await registerVerifyLogin(uniqueEmail());

    const res = await SELF.fetch("http://example.com/v1/invoices", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${access_token}`,
      },
      body: JSON.stringify({ school_id: "sch_DOESNOTEXIST" }),
    });
    expect(res.status).toBe(403);
    const body = await res.json<{ error: string }>();
    expect(body.error).toBe("School not found or not linked to user");
  });

  it("POST /v1/invoices returns 403 when school belongs to a different user", async () => {
    const user1 = await registerVerifyLogin(uniqueEmail());
    const user2 = await registerVerifyLogin(uniqueEmail());

    // user2 tries to create an invoice for user1's school
    const res = await SELF.fetch("http://example.com/v1/invoices", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${user2.access_token}`,
      },
      body: JSON.stringify({ school_id: user1.school_id }),
    });
    expect(res.status).toBe(403);
  });

  // ── 4. POST /v1/invoices 201 happy path ─────────────────────────────────────
  it("POST /v1/invoices 201 happy path returns correct invoice shape", async () => {
    const { access_token, school_id } = await registerVerifyLogin(uniqueEmail());

    const res = await SELF.fetch("http://example.com/v1/invoices", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${access_token}`,
      },
      body: JSON.stringify({ school_id }),
    });
    expect(res.status).toBe(201);

    const body = await res.json<{
      invoice: {
        id: string;
        number: string;
        school_id: string;
        subtotal_cents: number;
        gst_cents: number;
        total_cents: number;
        currency: string;
        status: string;
        r2_key: string;
      };
      pdf_url: null;
    }>();

    expect(body.invoice).toBeDefined();
    expect(body.pdf_url).toBeNull();

    // Amounts
    expect(body.invoice.subtotal_cents).toBe(55000);
    expect(body.invoice.gst_cents).toBe(5500);
    expect(body.invoice.total_cents).toBe(60500);
    expect(body.invoice.currency).toBe("AUD");
    expect(body.invoice.status).toBe("issued");

    // Number format: SFT-YYYY-NNNN
    expect(body.invoice.number).toMatch(/^SFT-\d{4}-\d{4}$/);

    // school_id echoed correctly
    expect(body.invoice.school_id).toBe(school_id);

    // r2_key is the expected path pattern
    expect(body.invoice.r2_key).toBe(`invoices/${body.invoice.id}.pdf`);

    // Invoice is queryable in D1 via findInvoiceById
    const dbRow = await findInvoiceById(db(), body.invoice.id);
    expect(dbRow).not.toBeNull();
    expect(dbRow!.id).toBe(body.invoice.id);
    expect(dbRow!.total_cents).toBe(60500);
  });

  // ── 5. Sequential invoice numbers ────────────────────────────────────────────
  it("POST /v1/invoices returns sequential numbers for the same year", async () => {
    const { access_token, school_id } = await registerVerifyLogin(uniqueEmail());

    const res1 = await SELF.fetch("http://example.com/v1/invoices", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${access_token}`,
      },
      body: JSON.stringify({ school_id }),
    });
    expect(res1.status).toBe(201);
    const body1 = await res1.json<{ invoice: { number: string } }>();

    const res2 = await SELF.fetch("http://example.com/v1/invoices", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${access_token}`,
      },
      body: JSON.stringify({ school_id }),
    });
    expect(res2.status).toBe(201);
    const body2 = await res2.json<{ invoice: { number: string } }>();

    // Extract the sequence number (last 4 digits) from each number
    const seq1 = parseInt(body1.invoice.number.split("-")[2], 10);
    const seq2 = parseInt(body2.invoice.number.split("-")[2], 10);
    expect(seq2).toBe(seq1 + 1);
  });

  // ── 6. GET /v1/invoices/:id/pdf 404 for unknown id ───────────────────────────
  it("GET /v1/invoices/:id/pdf returns 404 for unknown invoice id", async () => {
    const { access_token } = await registerVerifyLogin(uniqueEmail());

    const res = await SELF.fetch(
      "http://example.com/v1/invoices/inv_DOESNOTEXIST/pdf",
      { headers: { Authorization: `Bearer ${access_token}` } },
    );
    expect(res.status).toBe(404);
    const body = await res.json<{ error: string }>();
    expect(body.error).toBe("Invoice not found");
  });

  // ── 7. GET /v1/invoices/:id/pdf 403 for another user's invoice ──────────────
  it("GET /v1/invoices/:id/pdf returns 403 for invoice from another user's school", async () => {
    const user1 = await registerVerifyLogin(uniqueEmail());
    const user2 = await registerVerifyLogin(uniqueEmail());

    // user1 creates an invoice
    const createRes = await SELF.fetch("http://example.com/v1/invoices", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${user1.access_token}`,
      },
      body: JSON.stringify({ school_id: user1.school_id }),
    });
    expect(createRes.status).toBe(201);
    const createBody = await createRes.json<{ invoice: { id: string } }>();
    const invoiceId = createBody.invoice.id;

    // user2 tries to access user1's invoice PDF
    const res = await SELF.fetch(
      `http://example.com/v1/invoices/${invoiceId}/pdf`,
      { headers: { Authorization: `Bearer ${user2.access_token}` } },
    );
    expect(res.status).toBe(403);
    const body = await res.json<{ error: string }>();
    expect(body.error).toBe("Forbidden");
  });

  // ── 8. GET /v1/invoices/:id/pdf 501 for valid own invoice ────────────────────
  it("GET /v1/invoices/:id/pdf returns 501 with stub message for own invoice", async () => {
    const { access_token, school_id } = await registerVerifyLogin(uniqueEmail());

    // Create an invoice first
    const createRes = await SELF.fetch("http://example.com/v1/invoices", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${access_token}`,
      },
      body: JSON.stringify({ school_id }),
    });
    expect(createRes.status).toBe(201);
    const createBody = await createRes.json<{ invoice: { id: string } }>();
    const invoiceId = createBody.invoice.id;

    // Now try to get the PDF — should return 501
    const res = await SELF.fetch(
      `http://example.com/v1/invoices/${invoiceId}/pdf`,
      { headers: { Authorization: `Bearer ${access_token}` } },
    );
    expect(res.status).toBe(501);
    const body = await res.json<{ error: string }>();
    expect(body.error).toBe("PDF rendering pending M4");
  });
});
