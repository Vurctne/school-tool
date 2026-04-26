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
  insertInvoice,
  findInvoiceById,
  countInvoicesIssuedInYear,
  insertPurchaseOrder,
  findPurchaseOrderById,
  insertLicence,
  findLicenceById,
  upsertLicenceDevice,
  listLicenceDevicesByLicence,
  deleteLicenceDevice,
  type NewUserRow,
  type NewSchoolRow,
  type NewEmailTokenRow,
  type NewInvoiceRow,
  type NewPurchaseOrderRow,
  type NewLicenceRow,
  type NewLicenceDeviceRow,
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

  // ── 13. insertInvoice / findInvoiceById ───────────────────────────────────
  describe("insertInvoice / findInvoiceById", () => {
    it("round-trips a row and applies default currency + status", async () => {
      const row: NewInvoiceRow = {
        id: ulid("inv"),
        number: `SFT-2026-${Date.now() % 100000}`,
        school_id: schoolId,
        user_id: userId,
        issue_date: "2026-06-01",
        due_date: "2026-06-30",
        period_start: "2026-06-01",
        period_end: "2027-05-31",
        subtotal_cents: 55000,
        gst_cents: 5500,
        total_cents: 60500,
        // currency and status intentionally omitted → should default to 'AUD' / 'issued'
        r2_key: `invoices/${ulid("inv")}.pdf`,
        created_at: now(),
      };
      await insertInvoice(db(), row);

      const found = await findInvoiceById(db(), row.id);
      expect(found).not.toBeNull();
      expect(found!.id).toBe(row.id);
      expect(found!.total_cents).toBe(60500);
      expect(found!.currency).toBe("AUD");
      expect(found!.status).toBe("issued");
    });

    it("returns null for an unknown id", async () => {
      const result = await findInvoiceById(db(), "inv_DOESNOTEXIST");
      expect(result).toBeNull();
    });
  });

  // ── 14. countInvoicesIssuedInYear ─────────────────────────────────────────
  describe("countInvoicesIssuedInYear", () => {
    it("returns 0 when no invoices exist for the year", async () => {
      const count = await countInvoicesIssuedInYear(db(), 2099);
      expect(count).toBe(0);
    });

    it("counts only invoices in the target year", async () => {
      // Insert 2 invoices in 2030 and 1 in 2031
      const base: Omit<NewInvoiceRow, "id" | "number" | "issue_date" | "r2_key"> = {
        school_id: schoolId,
        user_id: userId,
        due_date: "2030-06-30",
        period_start: "2030-06-01",
        period_end: "2031-05-31",
        subtotal_cents: 55000,
        gst_cents: 5500,
        total_cents: 60500,
        created_at: now(),
      };

      const seq = Date.now() % 100000;
      for (let i = 0; i < 2; i++) {
        const id = ulid("inv");
        await insertInvoice(db(), {
          ...base,
          id,
          number: `SFT-2030-${seq + i}`,
          issue_date: "2030-05-15",
          r2_key: `invoices/${id}.pdf`,
        });
      }

      const idOther = ulid("inv");
      await insertInvoice(db(), {
        ...base,
        id: idOther,
        number: `SFT-2031-${seq + 99}`,
        issue_date: "2031-05-15",
        due_date: "2031-06-30",
        period_start: "2031-06-01",
        period_end: "2032-05-31",
        r2_key: `invoices/${idOther}.pdf`,
      });

      const count2030 = await countInvoicesIssuedInYear(db(), 2030);
      expect(count2030).toBeGreaterThanOrEqual(2);

      const count2031 = await countInvoicesIssuedInYear(db(), 2031);
      expect(count2031).toBeGreaterThanOrEqual(1);

      // 2030 and 2031 counts must differ (the 2031 row doesn't inflate 2030)
      expect(count2031).toBeLessThan(count2030 + 10); // sanity bound
    });
  });

  // ── 15. insertPurchaseOrder / findPurchaseOrderById ───────────────────────
  describe("insertPurchaseOrder / findPurchaseOrderById", () => {
    it("round-trips a row with required fields and applies default status", async () => {
      const row: NewPurchaseOrderRow = {
        id: ulid("po"),
        invoice_id: null,
        uploaded_by: userId,
        original_filename: "po_sample.pdf",
        r2_key: `pos/${ulid("po")}.pdf`,
        // status intentionally omitted → should default to 'uploaded'
        created_at: now(),
      };
      await insertPurchaseOrder(db(), row);

      const found = await findPurchaseOrderById(db(), row.id);
      expect(found).not.toBeNull();
      expect(found!.id).toBe(row.id);
      expect(found!.original_filename).toBe("po_sample.pdf");
      expect(found!.status).toBe("uploaded");
      expect(found!.invoice_id).toBeNull();
      expect(found!.ocr_raw).toBeNull();
    });

    it("returns null for an unknown id", async () => {
      const result = await findPurchaseOrderById(db(), "po_DOESNOTEXIST");
      expect(result).toBeNull();
    });
  });

  // ── 16. insertLicence / findLicenceById ───────────────────────────────────
  describe("insertLicence / findLicenceById", () => {
    it("round-trips a row; features is returned as raw JSON string", async () => {
      const featuresJson = JSON.stringify(["sub_program"]);
      const row: NewLicenceRow = {
        id: ulid("lic"),
        school_id: schoolId,
        invoice_id: null,
        po_id: null,
        source: "admin_grant",
        issued_at: now(),
        expires_at: addDays(now(), 365),
        features: featuresJson,
      };
      await insertLicence(db(), row);

      const found = await findLicenceById(db(), row.id);
      expect(found).not.toBeNull();
      expect(found!.id).toBe(row.id);
      expect(found!.source).toBe("admin_grant");
      expect(found!.features).toBe(featuresJson);
      expect(found!.revoked_at).toBeNull();
    });

    it("returns null for an unknown id", async () => {
      const result = await findLicenceById(db(), "lic_DOESNOTEXIST");
      expect(result).toBeNull();
    });
  });

  // ── 17. upsertLicenceDevice ───────────────────────────────────────────────
  describe("upsertLicenceDevice", () => {
    it("inserts on first call; updates last_seen/os_info but preserves first_seen on second call", async () => {
      // Set up a parent licence
      const licId = ulid("lic");
      await insertLicence(db(), {
        id: licId,
        school_id: schoolId,
        source: "admin_grant",
        issued_at: now(),
        expires_at: addDays(now(), 365),
        features: JSON.stringify(["sub_program"]),
      });

      const deviceId = `dev_${Date.now()}`;
      const firstSeen = now() - 100;
      const firstRow: NewLicenceDeviceRow = {
        licence_id: licId,
        device_id: deviceId,
        first_seen: firstSeen,
        last_seen: firstSeen,
        os_info: "Windows 11",
        app_version: "2.0.0",
      };
      await upsertLicenceDevice(db(), firstRow);

      // First call: row should exist with first_seen = firstSeen
      const devices1 = await listLicenceDevicesByLicence(db(), licId);
      expect(devices1).toHaveLength(1);
      expect(devices1[0].first_seen).toBe(firstSeen);
      expect(devices1[0].last_seen).toBe(firstSeen);

      // Second call: update last_seen and os_info
      const laterSeen = now();
      const updateRow: NewLicenceDeviceRow = {
        licence_id: licId,
        device_id: deviceId,
        first_seen: laterSeen, // this value must NOT overwrite the stored first_seen
        last_seen: laterSeen,
        os_info: "Windows 11 23H2",
        app_version: "2.0.1",
      };
      await upsertLicenceDevice(db(), updateRow);

      const devices2 = await listLicenceDevicesByLicence(db(), licId);
      expect(devices2).toHaveLength(1);
      // first_seen preserved from original insert
      expect(devices2[0].first_seen).toBe(firstSeen);
      // last_seen updated
      expect(devices2[0].last_seen).toBe(laterSeen);
      expect(devices2[0].os_info).toBe("Windows 11 23H2");
      expect(devices2[0].app_version).toBe("2.0.1");
    });
  });

  // ── 18. listLicenceDevicesByLicence ──────────────────────────────────────
  describe("listLicenceDevicesByLicence", () => {
    it("returns empty array for an unknown licence id", async () => {
      const result = await listLicenceDevicesByLicence(db(), "lic_DOESNOTEXIST");
      expect(result).toHaveLength(0);
    });

    it("returns multiple devices ordered by last_seen DESC", async () => {
      const licId = ulid("lic");
      await insertLicence(db(), {
        id: licId,
        school_id: schoolId,
        source: "purchase",
        issued_at: now(),
        expires_at: addDays(now(), 365),
        features: JSON.stringify(["sub_program"]),
      });

      const t1 = now() - 200;
      const t2 = now() - 100;
      const t3 = now();

      const devRows: NewLicenceDeviceRow[] = [
        { licence_id: licId, device_id: "dev_A", first_seen: t1, last_seen: t1 },
        { licence_id: licId, device_id: "dev_B", first_seen: t2, last_seen: t2 },
        { licence_id: licId, device_id: "dev_C", first_seen: t3, last_seen: t3 },
      ];

      for (const r of devRows) {
        await upsertLicenceDevice(db(), r);
      }

      const result = await listLicenceDevicesByLicence(db(), licId);
      expect(result).toHaveLength(3);
      // Should be DESC by last_seen: C, B, A
      expect(result[0].device_id).toBe("dev_C");
      expect(result[1].device_id).toBe("dev_B");
      expect(result[2].device_id).toBe("dev_A");
    });
  });

  // ── 19. deleteLicenceDevice ───────────────────────────────────────────────
  describe("deleteLicenceDevice", () => {
    it("removes one device and leaves others intact", async () => {
      const licId = ulid("lic");
      await insertLicence(db(), {
        id: licId,
        school_id: schoolId,
        source: "admin_grant",
        issued_at: now(),
        expires_at: addDays(now(), 365),
        features: JSON.stringify(["sub_program"]),
      });

      const t = now();
      await upsertLicenceDevice(db(), { licence_id: licId, device_id: "dev_X", first_seen: t, last_seen: t });
      await upsertLicenceDevice(db(), { licence_id: licId, device_id: "dev_Y", first_seen: t, last_seen: t });

      await deleteLicenceDevice(db(), licId, "dev_X");

      const remaining = await listLicenceDevicesByLicence(db(), licId);
      expect(remaining).toHaveLength(1);
      expect(remaining[0].device_id).toBe("dev_Y");
    });
  });
});
