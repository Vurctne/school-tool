import { describe, it, expect, beforeAll, beforeEach } from "vitest";
import { env, SELF } from "cloudflare:test";
import {
  findUserByEmail,
  findUserById,
  insertUser,
  touchUserLastSeen,
  insertSchool,
  linkUserSchool,
  listSchoolsForUser,
  listInvoicesForUser,
  getActiveLicenceForSchool,
  insertEmailToken,
  consumeEmailToken,
  logAdminEvent,
  type NewUserRow,
  type NewSchoolRow,
  type NewEmailTokenRow,
} from "../src/lib/db";
import { now, addDays } from "../src/lib/time";
import { ulid } from "../src/lib/ids";

// Helper: pull the D1 binding from the test env
function db(): D1Database {
  return (env as { DB: D1Database }).DB;
}

// ---------------------------------------------------------------------------
// Apply the migration SQL once before all tests.
// (vitest-pool-workers doesn't auto-run wrangler migrations in miniflare.)
// ---------------------------------------------------------------------------
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

beforeAll(async () => {
  // D1 exec() doesn't handle multi-statement DDL well — run each statement individually.
  const statements = MIGRATION_SQL
    .split(";")
    .map((s) => s.trim())
    .filter((s) => s.length > 0 && !s.startsWith("--"));

  for (const sql of statements) {
    await db().prepare(sql).run();
  }
});

// Shared fixture IDs — regenerated fresh each test via beforeEach seeding
let userId: string;
let schoolId: string;

async function seedUser(overrides: Partial<NewUserRow> = {}): Promise<NewUserRow> {
  const row: NewUserRow = {
    id: ulid("usr"),
    email: `test.${Date.now()}.${Math.random()}@example.edu.au`,
    password_hash: "$argon2id$v=19$...",
    first_name: "Ada",
    last_name: "Lovelace",
    created_at: now(),
    ...overrides,
  };
  await insertUser(db(), row);
  return row;
}

async function seedSchool(createdBy: string): Promise<NewSchoolRow> {
  const row: NewSchoolRow = {
    id: ulid("sch"),
    name: "Sunrise Secondary College",
    abn: "12345678901",
    address: "1 School St",
    suburb: "Melbourne",
    postcode: "3000",
    state: "VIC",
    created_by: createdBy,
    created_at: now(),
  };
  await insertSchool(db(), row);
  return row;
}

describe("db helpers", () => {
  beforeEach(async () => {
    const u = await seedUser();
    userId = u.id;
    const s = await seedSchool(userId);
    schoolId = s.id;
  });

  // ── 1. Insert user and find by email ─────────────────────────────────────
  it("insertUser / findUserByEmail returns the inserted row", async () => {
    const email = `find.email.${Date.now()}@school.vic.edu.au`;
    const row: NewUserRow = {
      id: ulid("usr"),
      email,
      password_hash: "hash",
      first_name: "Bob",
      last_name: "Smith",
      created_at: now(),
    };
    await insertUser(db(), row);

    const found = await findUserByEmail(db(), email);
    expect(found).not.toBeNull();
    expect(found!.id).toBe(row.id);
    expect(found!.first_name).toBe("Bob");
  });

  // ── 2. findUserByEmail is case-insensitive (COLLATE NOCASE) ──────────────
  it("findUserByEmail is case-insensitive", async () => {
    const base = `ci.${Date.now()}@example.edu.au`;
    const row: NewUserRow = {
      id: ulid("usr"),
      email: base.toLowerCase(),
      password_hash: "hash",
      first_name: null,
      last_name: null,
      created_at: now(),
    };
    await insertUser(db(), row);

    const found = await findUserByEmail(db(), base.toUpperCase());
    expect(found).not.toBeNull();
    expect(found!.id).toBe(row.id);
  });

  // ── 3. findUserById ───────────────────────────────────────────────────────
  it("findUserById returns the row and null for unknown id", async () => {
    const found = await findUserById(db(), userId);
    expect(found).not.toBeNull();
    expect(found!.id).toBe(userId);

    const missing = await findUserById(db(), "usr_DOESNOTEXIST");
    expect(missing).toBeNull();
  });

  // ── 4. touchUserLastSeen updates last_seen_at ─────────────────────────────
  it("touchUserLastSeen sets last_seen_at", async () => {
    const before = await findUserById(db(), userId);
    expect(before!.last_seen_at).toBeNull();

    await touchUserLastSeen(db(), userId);

    const after = await findUserById(db(), userId);
    expect(after!.last_seen_at).toBeGreaterThan(0);
  });

  // ── 5. linkUserSchool / listSchoolsForUser ────────────────────────────────
  it("linkUserSchool then listSchoolsForUser returns that school", async () => {
    await linkUserSchool(db(), userId, schoolId, "owner");

    const schools = await listSchoolsForUser(db(), userId);
    expect(schools).toHaveLength(1);
    expect(schools[0].id).toBe(schoolId);
    expect(schools[0].name).toBe("Sunrise Secondary College");
  });

  // ── 6. listSchoolsForUser returns empty for unlinked user ─────────────────
  it("listSchoolsForUser returns empty array when user has no schools", async () => {
    // userId was seeded but NOT linked — separate fresh user with no links
    const fresh = await seedUser();
    const schools = await listSchoolsForUser(db(), fresh.id);
    expect(schools).toHaveLength(0);
  });

  // ── 7. Insert invoice and list for user ───────────────────────────────────
  it("listInvoicesForUser returns invoices belonging to the user", async () => {
    const invId = ulid("inv");
    const seq = Date.now() % 10000;
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
        `SFT-2026-${seq}`,
        schoolId,
        userId,
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
        now(),
      )
      .run();

    const invoices = await listInvoicesForUser(db(), userId);
    expect(invoices.length).toBeGreaterThanOrEqual(1);
    const inv = invoices.find((i) => i.id === invId);
    expect(inv).toBeDefined();
    expect(inv!.total_cents).toBe(60500);
  });

  // ── 8. getActiveLicenceForSchool returns null when none exists ────────────
  it("getActiveLicenceForSchool returns null when no licence exists", async () => {
    // fresh user+school with no licence
    const freshUser = await seedUser();
    const freshSchool = await seedSchool(freshUser.id);
    const result = await getActiveLicenceForSchool(db(), freshSchool.id);
    expect(result).toBeNull();
  });

  // ── 9. getActiveLicenceForSchool returns active licence ───────────────────
  it("getActiveLicenceForSchool returns a non-revoked, non-expired licence", async () => {
    const licId = ulid("lic");
    const issuedAt = now();
    const expiresAt = addDays(issuedAt, 365);

    await db()
      .prepare(
        `INSERT INTO licences
          (id, school_id, invoice_id, po_id, source, issued_at, expires_at, features)
         VALUES (?,?,?,?,?,?,?,?)`,
      )
      .bind(
        licId,
        schoolId,
        null,
        null,
        "admin_grant",
        issuedAt,
        expiresAt,
        JSON.stringify(["sub_program"]),
      )
      .run();

    const lic = await getActiveLicenceForSchool(db(), schoolId);
    expect(lic).not.toBeNull();
    expect(lic!.id).toBe(licId);
    expect(lic!.source).toBe("admin_grant");
  });

  // ── 10. consumeEmailToken is one-shot ─────────────────────────────────────
  it("consumeEmailToken consumes a token exactly once", async () => {
    const tokenRow: NewEmailTokenRow = {
      token: `tok_${crypto.randomUUID().replace(/-/g, "")}`,
      user_id: userId,
      purpose: "verify",
      expires_at: addDays(now(), 1),
    };
    await insertEmailToken(db(), tokenRow);

    // First consume: should succeed
    const first = await consumeEmailToken(db(), tokenRow.token, "verify");
    expect(first).not.toBeNull();
    expect(first!.user_id).toBe(userId);

    // Second consume: must return null (already consumed)
    const second = await consumeEmailToken(db(), tokenRow.token, "verify");
    expect(second).toBeNull();
  });

  // ── 11. logAdminEvent inserts a row ───────────────────────────────────────
  it("logAdminEvent inserts an audit row that is queryable", async () => {
    const entityId = `lic_${Date.now()}`;
    await logAdminEvent(
      db(),
      "admin",
      "licence.extend",
      "licence",
      entityId,
      { days: 14, reason: "Test extension" },
    );

    const row = await db()
      .prepare(
        "SELECT * FROM admin_events WHERE entity_id = ? ORDER BY id DESC LIMIT 1",
      )
      .bind(entityId)
      .first<{ actor: string; action: string; payload: string }>();

    expect(row).not.toBeNull();
    expect(row!.actor).toBe("admin");
    expect(row!.action).toBe("licence.extend");
    const payload = JSON.parse(row!.payload) as { days: number; reason: string };
    expect(payload.days).toBe(14);
  });

  // ── 12. SELF healthz sanity ───────────────────────────────────────────────
  it("GET /healthz returns ok", async () => {
    const res = await SELF.fetch("http://example.com/healthz");
    expect(res.status).toBe(200);
    const body = await res.json<{ ok: boolean }>();
    expect(body.ok).toBe(true);
  });
});
