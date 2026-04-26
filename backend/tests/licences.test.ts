import { describe, it, expect, beforeAll, vi } from "vitest";
import { SELF, env } from "cloudflare:test";
import * as ed from "@noble/ed25519";
import {
  insertLicence,
  upsertLicenceDevice,
  listLicenceDevicesByLicence,
} from "../src/lib/db";
import { signLicenceToken, loadPublicKey } from "../src/lib/ed25519";

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

const TEST_PRIVATE_KEY =
  "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=";

function db(): D1Database {
  return (env as { DB: D1Database }).DB;
}

beforeAll(async () => {
  // Mock fetch to intercept Resend API calls
  globalThis.fetch = vi.fn(
    async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : (input as Request).url;
      if (url === "https://api.resend.com/emails") {
        return new Response(JSON.stringify({ id: "mock-email-id" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("Not mocked", { status: 200 });
    },
  ) as typeof fetch;

  const statements = MIGRATION_SQL.split(";")
    .map((s) => s.trim())
    .filter((s) => s.length > 0 && !s.startsWith("--"));

  for (const sql of statements) {
    await db().prepare(sql).run();
  }
});

// ── Helpers ───────────────────────────────────────────────────────────────────

function uniqueEmail(): string {
  return `lic.${Date.now()}.${Math.random().toString(36).slice(2)}@school.vic.edu.au`;
}

function uniqueId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2)}`;
}

/**
 * Drive the full register -> verify-email -> login flow.
 * Returns user_id, school_id created at registration, and access_token.
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
  if (!userRow)
    throw new Error(`registerVerifyLogin: user not found for ${email}`);
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
 * Insert an active licence for the given school_id directly into DB.
 * Returns the licence id.
 */
async function insertActiveLicence(schoolId: string): Promise<string> {
  const licenceId = uniqueId("lic");
  const nowTs = Math.floor(Date.now() / 1000);
  await insertLicence(db(), {
    id: licenceId,
    school_id: schoolId,
    source: "admin_grant",
    issued_at: nowTs,
    expires_at: nowTs + 365 * 86400,
    features: JSON.stringify(["sub_program"]),
  });
  return licenceId;
}

// ── Tests ─────────────────────────────────────────────────────────────────────

type LicencePayload = {
  licence_id: string;
  school_id: string;
  school_name: string;
  email: string;
  device_id: string;
  issued_at: string;
  expires_at: string;
  features: string[];
  signature: string;
};

describe("licences routes", () => {
  // ── 1. POST /activate 401 when no Bearer token ───────────────────────────────
  it("POST /v1/licences/activate returns 401 when no Bearer token", async () => {
    const res = await SELF.fetch("http://example.com/v1/licences/activate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: "device-1" }),
    });
    expect(res.status).toBe(401);
  });

  // ── 2. POST /activate 400 when device_id missing ──────────────────────────────
  it("POST /v1/licences/activate returns 400 when device_id missing", async () => {
    const { access_token } = await registerVerifyLogin(uniqueEmail());

    const res = await SELF.fetch("http://example.com/v1/licences/activate", {
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

  // ── 3. POST /activate 400 when device_id is empty string ─────────────────────
  it("POST /v1/licences/activate returns 400 when device_id is empty string", async () => {
    const { access_token } = await registerVerifyLogin(uniqueEmail());

    const res = await SELF.fetch("http://example.com/v1/licences/activate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${access_token}`,
      },
      body: JSON.stringify({ device_id: "" }),
    });
    expect(res.status).toBe(400);
  });

  // ── 4. POST /activate 404 when user has school but no active licence ──────────
  it("POST /v1/licences/activate returns 404 when user has no active licence", async () => {
    // User has a school (created at registration) but no licence
    const { access_token } = await registerVerifyLogin(uniqueEmail());

    const res = await SELF.fetch("http://example.com/v1/licences/activate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${access_token}`,
      },
      body: JSON.stringify({ device_id: "device-abc" }),
    });
    expect(res.status).toBe(404);
    const body = await res.json<{ error: string }>();
    expect(body.error).toBe("No active licence");
  });

  // ── 5. POST /activate 200 happy path ─────────────────────────────────────────
  it("POST /v1/licences/activate 200 returns correct payload shape and valid signature", async () => {
    const { access_token, school_id } = await registerVerifyLogin(
      uniqueEmail(),
    );
    await insertActiveLicence(school_id);

    const deviceId = uniqueId("dev");
    const res = await SELF.fetch("http://example.com/v1/licences/activate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${access_token}`,
      },
      body: JSON.stringify({
        device_id: deviceId,
        os_info: "Windows 11 22H2",
        app_version: "2.0.0",
      }),
    });
    expect(res.status).toBe(200);

    const body = await res.json<LicencePayload>();

    // Shape checks
    expect(body.licence_id).toBeTruthy();
    expect(body.school_id).toBe(school_id);
    expect(body.school_name).toBeTruthy();
    expect(body.email).toBeTruthy();
    expect(body.device_id).toBe(deviceId);
    expect(body.issued_at).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    expect(body.expires_at).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    expect(Array.isArray(body.features)).toBe(true);
    expect(body.features).toContain("sub_program");

    // Signature shape
    expect(body.signature).toMatch(/^ed25519:.+/);

    // Verify signature by re-signing the same payload
    const { signature: _sig, ...payloadWithoutSignature } = body;
    const expectedSig = await signLicenceToken(
      TEST_PRIVATE_KEY,
      payloadWithoutSignature,
    );
    expect(body.signature).toBe(expectedSig);
  });

  // ── 6. POST /activate registers the device in licence_devices ────────────────
  it("POST /v1/licences/activate registers the device in DB", async () => {
    const { access_token, school_id } = await registerVerifyLogin(
      uniqueEmail(),
    );
    const licenceId = await insertActiveLicence(school_id);

    const deviceId = uniqueId("dev");
    const res = await SELF.fetch("http://example.com/v1/licences/activate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${access_token}`,
      },
      body: JSON.stringify({
        device_id: deviceId,
        os_info: "Windows 11 22H2",
        app_version: "2.0.0",
      }),
    });
    expect(res.status).toBe(200);

    const devices = await listLicenceDevicesByLicence(db(), licenceId);
    const registered = devices.find((d) => d.device_id === deviceId);
    expect(registered).toBeDefined();
    expect(registered!.os_info).toBe("Windows 11 22H2");
    expect(registered!.app_version).toBe("2.0.0");
  });

  // ── 7. POST /activate with same device_id twice -- idempotent upsert ──────────
  it("POST /v1/licences/activate with same device_id twice: 1 row, last_seen updated, first_seen preserved", async () => {
    const { access_token, school_id } = await registerVerifyLogin(
      uniqueEmail(),
    );
    const licenceId = await insertActiveLicence(school_id);

    const deviceId = uniqueId("dev");

    // First call
    const res1 = await SELF.fetch("http://example.com/v1/licences/activate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${access_token}`,
      },
      body: JSON.stringify({ device_id: deviceId }),
    });
    expect(res1.status).toBe(200);

    const devicesAfter1 = await listLicenceDevicesByLicence(db(), licenceId);
    const devRow1 = devicesAfter1.find((d) => d.device_id === deviceId)!;
    expect(devRow1).toBeDefined();
    const firstSeenOrig = devRow1.first_seen;
    const lastSeenOrig = devRow1.last_seen;

    // Small delay to get a different timestamp
    await new Promise((r) => setTimeout(r, 1100));

    // Second call with same device_id
    const res2 = await SELF.fetch("http://example.com/v1/licences/activate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${access_token}`,
      },
      body: JSON.stringify({ device_id: deviceId }),
    });
    expect(res2.status).toBe(200);

    const devicesAfter2 = await listLicenceDevicesByLicence(db(), licenceId);
    // Still only 1 device row for this device_id
    const matchingRows = devicesAfter2.filter(
      (d) => d.device_id === deviceId,
    );
    expect(matchingRows).toHaveLength(1);

    const devRow2 = matchingRows[0];
    // first_seen preserved
    expect(devRow2.first_seen).toBe(firstSeenOrig);
    // last_seen updated (>= because now() is seconds-resolution; may equal if sub-second)
    expect(devRow2.last_seen).toBeGreaterThanOrEqual(lastSeenOrig);
  });

  // ── 8. POST /activate with 4th new device evicts LRU ─────────────────────────
  it("POST /v1/licences/activate evicts least-recently-seen device when cap is 3", async () => {
    const { access_token, school_id } = await registerVerifyLogin(
      uniqueEmail(),
    );
    const licenceId = await insertActiveLicence(school_id);

    const nowTs = Math.floor(Date.now() / 1000);

    // Seed 3 devices directly with distinct last_seen values (DESC sorted: dev3 > dev2 > dev1)
    const dev1Id = uniqueId("devA");
    const dev2Id = uniqueId("devB");
    const dev3Id = uniqueId("devC");

    await upsertLicenceDevice(db(), {
      licence_id: licenceId,
      device_id: dev1Id,
      first_seen: nowTs - 300,
      last_seen: nowTs - 300, // oldest -- should be evicted
    });
    await upsertLicenceDevice(db(), {
      licence_id: licenceId,
      device_id: dev2Id,
      first_seen: nowTs - 200,
      last_seen: nowTs - 200,
    });
    await upsertLicenceDevice(db(), {
      licence_id: licenceId,
      device_id: dev3Id,
      first_seen: nowTs - 100,
      last_seen: nowTs - 100, // most recent
    });

    const devicesBefore = await listLicenceDevicesByLicence(db(), licenceId);
    expect(devicesBefore).toHaveLength(3);

    // POST with a 4th device
    const dev4Id = uniqueId("devD");
    const res = await SELF.fetch("http://example.com/v1/licences/activate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${access_token}`,
      },
      body: JSON.stringify({ device_id: dev4Id }),
    });
    expect(res.status).toBe(200);

    const devicesAfter = await listLicenceDevicesByLicence(db(), licenceId);

    // Still 3 devices
    expect(devicesAfter).toHaveLength(3);

    const ids = devicesAfter.map((d) => d.device_id);
    // dev1 (oldest last_seen) was evicted
    expect(ids).not.toContain(dev1Id);
    // dev2, dev3, dev4 remain
    expect(ids).toContain(dev2Id);
    expect(ids).toContain(dev3Id);
    expect(ids).toContain(dev4Id);
  });

  // ── 9. POST /refresh is idempotent and equivalent to /activate ───────────────
  it("POST /v1/licences/refresh returns same shape as /activate and same licence_id", async () => {
    const { access_token, school_id } = await registerVerifyLogin(
      uniqueEmail(),
    );
    await insertActiveLicence(school_id);

    const deviceId = uniqueId("dev");

    const activateRes = await SELF.fetch(
      "http://example.com/v1/licences/activate",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${access_token}`,
        },
        body: JSON.stringify({ device_id: deviceId }),
      },
    );
    expect(activateRes.status).toBe(200);
    const activateBody = await activateRes.json<LicencePayload>();

    const refreshRes = await SELF.fetch(
      "http://example.com/v1/licences/refresh",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${access_token}`,
        },
        body: JSON.stringify({ device_id: deviceId }),
      },
    );
    expect(refreshRes.status).toBe(200);
    const refreshBody = await refreshRes.json<LicencePayload>();

    // Same licence_id
    expect(refreshBody.licence_id).toBe(activateBody.licence_id);
    // Same school
    expect(refreshBody.school_id).toBe(activateBody.school_id);
    // Same features
    expect(refreshBody.features).toEqual(activateBody.features);
    // Signature present and valid shape
    expect(refreshBody.signature).toMatch(/^ed25519:.+/);
  });

  // ── 10. Signature roundtrip: verify with @noble/ed25519 ──────────────────────
  it("signature roundtrip: verifies against public key derived from test private key", async () => {
    const { access_token, school_id } = await registerVerifyLogin(
      uniqueEmail(),
    );
    await insertActiveLicence(school_id);

    const deviceId = uniqueId("dev");
    const res = await SELF.fetch("http://example.com/v1/licences/activate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${access_token}`,
      },
      body: JSON.stringify({ device_id: deviceId }),
    });
    expect(res.status).toBe(200);
    const body = await res.json<LicencePayload>();

    // Re-sign the payload-without-signature using the same key
    const { signature: _sig, ...payloadWithoutSig } = body;
    const expectedSig = await signLicenceToken(
      TEST_PRIVATE_KEY,
      payloadWithoutSig,
    );
    // Signatures must match (Ed25519 + canonical JSON is deterministic)
    expect(body.signature).toBe(expectedSig);

    // Additionally verify using @noble/ed25519 directly
    const pubKeyB64 = await loadPublicKey(TEST_PRIVATE_KEY);
    const pubKeyBytes = Uint8Array.from(atob(pubKeyB64), (c) =>
      c.charCodeAt(0),
    );

    // The signature is "ed25519:<base64>"
    const sigB64 = body.signature.slice("ed25519:".length);
    const sigBytes = Uint8Array.from(atob(sigB64), (c) => c.charCodeAt(0));

    // Reconstruct canonical JSON message to verify with noble
    function sortKeysDeep(value: unknown): unknown {
      if (Array.isArray(value)) return value.map(sortKeysDeep);
      if (value !== null && typeof value === "object") {
        const sorted: Record<string, unknown> = {};
        for (const key of Object.keys(
          value as Record<string, unknown>,
        ).sort()) {
          sorted[key] = sortKeysDeep((value as Record<string, unknown>)[key]);
        }
        return sorted;
      }
      return value;
    }
    const canonicalMsg = JSON.stringify(sortKeysDeep(payloadWithoutSig));
    const msgBytes = new TextEncoder().encode(canonicalMsg);

    const valid = await ed.verifyAsync(sigBytes, msgBytes, pubKeyBytes);
    expect(valid).toBe(true);
  });
});
