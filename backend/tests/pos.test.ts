import { describe, it, expect, beforeAll, vi } from "vitest";
import { SELF, env } from "cloudflare:test";
import { findPurchaseOrderById } from "../src/lib/db";

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
  return `po.${Date.now()}.${Math.random().toString(36).slice(2)}@school.vic.edu.au`;
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

/**
 * Create an invoice for the given user + school.
 * Returns the invoice id.
 */
async function createInvoice(
  access_token: string,
  school_id: string,
): Promise<string> {
  const res = await SELF.fetch("http://example.com/v1/invoices", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${access_token}`,
    },
    body: JSON.stringify({ school_id }),
  });
  if (res.status !== 201) {
    throw new Error(`createInvoice: expected 201, got ${res.status}`);
  }
  const body = await res.json<{ invoice: { id: string } }>();
  return body.invoice.id;
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("purchase orders routes", () => {
  // ── 1. POST 401 when no Bearer token ────────────────────────────────────────
  it("POST /v1/purchase-orders returns 401 when no Bearer token", async () => {
    const formData = new FormData();
    formData.append("invoice_id", "inv_WHATEVER");
    formData.append("file", new File([new Uint8Array(100).fill(0x41)], "test.pdf", { type: "application/pdf" }));

    const res = await SELF.fetch("http://example.com/v1/purchase-orders", {
      method: "POST",
      body: formData,
    });
    expect(res.status).toBe(401);
  });

  // ── 2. POST 400 when invoice_id missing ──────────────────────────────────────
  it("POST /v1/purchase-orders returns 400 when invoice_id is missing", async () => {
    const { access_token } = await registerVerifyLogin(uniqueEmail());

    const formData = new FormData();
    formData.append("file", new File([new Uint8Array(100).fill(0x41)], "test.pdf", { type: "application/pdf" }));

    const res = await SELF.fetch("http://example.com/v1/purchase-orders", {
      method: "POST",
      headers: { Authorization: `Bearer ${access_token}` },
      body: formData,
    });
    expect(res.status).toBe(400);
    const body = await res.json<{ error: string }>();
    expect(body.error).toMatch(/invoice_id/i);
  });

  // ── 3. POST 400 when file missing ────────────────────────────────────────────
  it("POST /v1/purchase-orders returns 400 when file is missing", async () => {
    const { access_token } = await registerVerifyLogin(uniqueEmail());

    const formData = new FormData();
    formData.append("invoice_id", "inv_WHATEVER");

    const res = await SELF.fetch("http://example.com/v1/purchase-orders", {
      method: "POST",
      headers: { Authorization: `Bearer ${access_token}` },
      body: formData,
    });
    expect(res.status).toBe(400);
    const body = await res.json<{ error: string }>();
    expect(body.error).toMatch(/file/i);
  });

  // ── 4. POST 413 when file > 10 MB ────────────────────────────────────────────
  it("POST /v1/purchase-orders returns 413 when file exceeds 10 MB", async () => {
    const { access_token } = await registerVerifyLogin(uniqueEmail());

    const bigFile = new File([new Uint8Array(11 * 1024 * 1024)], "big.pdf", { type: "application/pdf" });
    const formData = new FormData();
    formData.append("invoice_id", "inv_WHATEVER");
    formData.append("file", bigFile);

    const res = await SELF.fetch("http://example.com/v1/purchase-orders", {
      method: "POST",
      headers: { Authorization: `Bearer ${access_token}` },
      body: formData,
    });
    expect(res.status).toBe(413);
    const body = await res.json<{ error: string }>();
    expect(body.error).toBe("File too large; max 10 MB");
  });

  // ── 5. POST 404 when invoice_id references unknown invoice ───────────────────
  it("POST /v1/purchase-orders returns 404 when invoice_id is unknown", async () => {
    const { access_token } = await registerVerifyLogin(uniqueEmail());

    const formData = new FormData();
    formData.append("invoice_id", "inv_DOESNOTEXIST");
    formData.append("file", new File([new Uint8Array(100).fill(0x41)], "test.pdf", { type: "application/pdf" }));

    const res = await SELF.fetch("http://example.com/v1/purchase-orders", {
      method: "POST",
      headers: { Authorization: `Bearer ${access_token}` },
      body: formData,
    });
    expect(res.status).toBe(404);
    const body = await res.json<{ error: string }>();
    expect(body.error).toBe("Invoice not found");
  });

  // ── 6. POST 403 when invoice's school not linked to user ─────────────────────
  it("POST /v1/purchase-orders returns 403 when invoice belongs to another user", async () => {
    const user1 = await registerVerifyLogin(uniqueEmail());
    const user2 = await registerVerifyLogin(uniqueEmail());

    // user1 creates an invoice
    const invoiceId = await createInvoice(user1.access_token, user1.school_id);

    // user2 tries to upload a PO against user1's invoice
    const formData = new FormData();
    formData.append("invoice_id", invoiceId);
    formData.append("file", new File([new Uint8Array(100).fill(0x41)], "test.pdf", { type: "application/pdf" }));

    const res = await SELF.fetch("http://example.com/v1/purchase-orders", {
      method: "POST",
      headers: { Authorization: `Bearer ${user2.access_token}` },
      body: formData,
    });
    expect(res.status).toBe(403);
    const body = await res.json<{ error: string }>();
    expect(body.error).toBe("Forbidden");
  });

  // ── 7. POST 201 happy path ───────────────────────────────────────────────────
  it("POST /v1/purchase-orders 201 happy path returns correct shape and uploads to R2", async () => {
    const { access_token, school_id } = await registerVerifyLogin(uniqueEmail());
    const invoiceId = await createInvoice(access_token, school_id);

    const fileContent = new Uint8Array(100).fill(0x41);
    const formData = new FormData();
    formData.append("invoice_id", invoiceId);
    formData.append("file", new File([fileContent], "purchase_order.pdf", { type: "application/pdf" }));

    const res = await SELF.fetch("http://example.com/v1/purchase-orders", {
      method: "POST",
      headers: { Authorization: `Bearer ${access_token}` },
      body: formData,
    });
    expect(res.status).toBe(201);

    const body = await res.json<{
      purchase_order: {
        id: string;
        invoice_id: string;
        uploaded_by: string;
        original_filename: string;
        r2_key: string;
        status: string;
      };
    }>();

    expect(body.purchase_order).toBeDefined();
    expect(body.purchase_order.id).toMatch(/^po_/);
    expect(body.purchase_order.invoice_id).toBe(invoiceId);
    expect(body.purchase_order.status).toBe("uploaded");
    expect(body.purchase_order.original_filename).toBe("purchase_order.pdf");
    expect(body.purchase_order.r2_key).toMatch(/^pos\/po_.*\.pdf$/);

    // Verify R2 received the upload
    const r2Key = body.purchase_order.r2_key;
    const r2Obj = await (env as { R2: R2Bucket }).R2.get(r2Key);
    expect(r2Obj).not.toBeNull();
    const text = await r2Obj!.text();
    expect(text.length).toBe(100);

    // Verify DB row
    const dbRow = await findPurchaseOrderById(db(), body.purchase_order.id);
    expect(dbRow).not.toBeNull();
    expect(dbRow!.r2_key).toBe(r2Key);
  });

  // ── 8. GET /:id 404 for unknown id ───────────────────────────────────────────
  it("GET /v1/purchase-orders/:id returns 404 for unknown id", async () => {
    const { access_token } = await registerVerifyLogin(uniqueEmail());

    const res = await SELF.fetch(
      "http://example.com/v1/purchase-orders/po_DOESNOTEXIST",
      { headers: { Authorization: `Bearer ${access_token}` } },
    );
    expect(res.status).toBe(404);
    const body = await res.json<{ error: string }>();
    expect(body.error).toBe("Purchase order not found");
  });

  // ── 9. GET /:id 403 when PO belongs to another user's school ─────────────────
  it("GET /v1/purchase-orders/:id returns 403 when PO belongs to another user", async () => {
    const user1 = await registerVerifyLogin(uniqueEmail());
    const user2 = await registerVerifyLogin(uniqueEmail());

    // user1 uploads a PO
    const invoiceId = await createInvoice(user1.access_token, user1.school_id);
    const formData = new FormData();
    formData.append("invoice_id", invoiceId);
    formData.append("file", new File([new Uint8Array(100).fill(0x41)], "test.pdf", { type: "application/pdf" }));

    const createRes = await SELF.fetch("http://example.com/v1/purchase-orders", {
      method: "POST",
      headers: { Authorization: `Bearer ${user1.access_token}` },
      body: formData,
    });
    expect(createRes.status).toBe(201);
    const createBody = await createRes.json<{ purchase_order: { id: string } }>();
    const poId = createBody.purchase_order.id;

    // user2 tries to access user1's PO
    const res = await SELF.fetch(
      `http://example.com/v1/purchase-orders/${poId}`,
      { headers: { Authorization: `Bearer ${user2.access_token}` } },
    );
    expect(res.status).toBe(403);
    const body = await res.json<{ error: string }>();
    expect(body.error).toBe("Forbidden");
  });

  // ── 10. GET /:id 200 happy path ──────────────────────────────────────────────
  it("GET /v1/purchase-orders/:id returns 200 with the PO row for the owner", async () => {
    const { access_token, school_id } = await registerVerifyLogin(uniqueEmail());
    const invoiceId = await createInvoice(access_token, school_id);

    // Upload a PO first
    const formData = new FormData();
    formData.append("invoice_id", invoiceId);
    formData.append("file", new File([new Uint8Array(100).fill(0x41)], "my_po.pdf", { type: "application/pdf" }));

    const createRes = await SELF.fetch("http://example.com/v1/purchase-orders", {
      method: "POST",
      headers: { Authorization: `Bearer ${access_token}` },
      body: formData,
    });
    expect(createRes.status).toBe(201);
    const createBody = await createRes.json<{ purchase_order: { id: string } }>();
    const poId = createBody.purchase_order.id;

    // Now poll status
    const res = await SELF.fetch(
      `http://example.com/v1/purchase-orders/${poId}`,
      { headers: { Authorization: `Bearer ${access_token}` } },
    );
    expect(res.status).toBe(200);

    const body = await res.json<{
      purchase_order: {
        id: string;
        invoice_id: string;
        status: string;
        original_filename: string;
        r2_key: string;
      };
    }>();

    expect(body.purchase_order).toBeDefined();
    expect(body.purchase_order.id).toBe(poId);
    expect(body.purchase_order.invoice_id).toBe(invoiceId);
    expect(body.purchase_order.status).toBe("uploaded");
    expect(body.purchase_order.original_filename).toBe("my_po.pdf");
    expect(body.purchase_order.r2_key).toMatch(/^pos\/po_.*\.pdf$/);
  });
});
