// ── JSON helpers ──────────────────────────────────────────────────────────────

export function jsonColumn<T>(raw: string | null): T | null {
  if (raw === null) return null;
  return JSON.parse(raw) as T;
}

export function stringifyJson(v: unknown): string {
  return JSON.stringify(v);
}

// ── Row interfaces ─────────────────────────────────────────────────────────────

export interface UserRow {
  id: string;
  email: string;
  password_hash: string;
  first_name: string | null;
  last_name: string | null;
  email_verified_at: number | null;
  created_at: number;
  last_seen_at: number | null;
}

export interface NewUserRow {
  id: string;
  email: string;
  password_hash: string;
  first_name: string | null;
  last_name: string | null;
  created_at: number;
}

export interface EmailTokenRow {
  token: string;
  user_id: string;
  purpose: "verify" | "reset";
  expires_at: number;
  consumed_at: number | null;
}

export interface NewEmailTokenRow {
  token: string;
  user_id: string;
  purpose: "verify" | "reset";
  expires_at: number;
}

export interface SchoolRow {
  id: string;
  name: string;
  abn: string | null;
  address: string | null;
  suburb: string | null;
  postcode: string | null;
  state: string | null;
  created_by: string;
  created_at: number;
}

export interface NewSchoolRow {
  id: string;
  name: string;
  abn: string | null;
  address: string | null;
  suburb: string | null;
  postcode: string | null;
  state: string | null;
  created_by: string;
  created_at: number;
}

export interface UserSchoolRow {
  user_id: string;
  school_id: string;
  role: "owner" | "member";
}

export interface InvoiceRow {
  id: string;
  number: string;
  school_id: string;
  user_id: string;
  issue_date: string;
  due_date: string;
  period_start: string;
  period_end: string;
  subtotal_cents: number;
  gst_cents: number;
  total_cents: number;
  currency: string;
  status: string;
  r2_key: string;
  created_at: number;
}

export interface PurchaseOrderRow {
  id: string;
  invoice_id: string | null;
  uploaded_by: string;
  original_filename: string;
  r2_key: string;
  ocr_raw: string | null;
  extracted: string | null;
  form_template: string | null;
  match_score: number | null;
  status: string;
  rejection_reason: string | null;
  reviewed_by: string | null;
  reviewed_at: number | null;
  created_at: number;
}

export interface LicenceRow {
  id: string;
  school_id: string;
  invoice_id: string | null;
  po_id: string | null;
  source: string;
  issued_at: number;
  expires_at: number;
  features: string;
  revoked_at: number | null;
  revoked_reason: string | null;
}

export interface LicenceDeviceRow {
  licence_id: string;
  device_id: string;
  first_seen: number;
  last_seen: number;
  os_info: string | null;
  app_version: string | null;
}

export interface AdminEventRow {
  id: number;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string;
  payload: string | null;
  at: number;
}

// ── User queries ──────────────────────────────────────────────────────────────

export async function findUserByEmail(
  db: D1Database,
  email: string,
): Promise<UserRow | null> {
  return db
    .prepare("SELECT * FROM users WHERE email = ?")
    .bind(email)
    .first<UserRow>();
}

export async function findUserById(
  db: D1Database,
  id: string,
): Promise<UserRow | null> {
  return db
    .prepare("SELECT * FROM users WHERE id = ?")
    .bind(id)
    .first<UserRow>();
}

export async function insertUser(
  db: D1Database,
  row: NewUserRow,
): Promise<void> {
  await db
    .prepare(
      `INSERT INTO users (id, email, password_hash, first_name, last_name, created_at)
       VALUES (?, ?, ?, ?, ?, ?)`,
    )
    .bind(
      row.id,
      row.email,
      row.password_hash,
      row.first_name,
      row.last_name,
      row.created_at,
    )
    .run();
}

export async function touchUserLastSeen(
  db: D1Database,
  id: string,
): Promise<void> {
  const ts = Math.floor(Date.now() / 1000);
  await db
    .prepare("UPDATE users SET last_seen_at = ? WHERE id = ?")
    .bind(ts, id)
    .run();
}

// ── School queries ─────────────────────────────────────────────────────────────

export async function findSchoolById(
  db: D1Database,
  id: string,
): Promise<SchoolRow | null> {
  return db
    .prepare("SELECT * FROM schools WHERE id = ?")
    .bind(id)
    .first<SchoolRow>();
}

export async function insertSchool(
  db: D1Database,
  row: NewSchoolRow,
): Promise<void> {
  await db
    .prepare(
      `INSERT INTO schools (id, name, abn, address, suburb, postcode, state, created_by, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    )
    .bind(
      row.id,
      row.name,
      row.abn,
      row.address,
      row.suburb,
      row.postcode,
      row.state ?? "VIC",
      row.created_by,
      row.created_at,
    )
    .run();
}

export async function linkUserSchool(
  db: D1Database,
  userId: string,
  schoolId: string,
  role: "owner" | "member",
): Promise<void> {
  await db
    .prepare(
      `INSERT INTO user_schools (user_id, school_id, role)
       VALUES (?, ?, ?)
       ON CONFLICT (user_id, school_id) DO UPDATE SET role = excluded.role`,
    )
    .bind(userId, schoolId, role)
    .run();
}

export async function listSchoolsForUser(
  db: D1Database,
  userId: string,
): Promise<SchoolRow[]> {
  const result = await db
    .prepare(
      `SELECT s.* FROM schools s
       INNER JOIN user_schools us ON us.school_id = s.id
       WHERE us.user_id = ?
       ORDER BY s.created_at ASC`,
    )
    .bind(userId)
    .all<SchoolRow>();
  return result.results;
}

// ── Invoice queries ───────────────────────────────────────────────────────────

export async function listInvoicesForUser(
  db: D1Database,
  userId: string,
): Promise<InvoiceRow[]> {
  const result = await db
    .prepare(
      `SELECT * FROM invoices WHERE user_id = ? ORDER BY created_at DESC`,
    )
    .bind(userId)
    .all<InvoiceRow>();
  return result.results;
}

// ── Licence queries ───────────────────────────────────────────────────────────

export async function getActiveLicenceForSchool(
  db: D1Database,
  schoolId: string,
): Promise<LicenceRow | null> {
  const nowSeconds = Math.floor(Date.now() / 1000);
  return db
    .prepare(
      `SELECT * FROM licences
       WHERE school_id = ?
         AND revoked_at IS NULL
         AND expires_at > ?
       ORDER BY expires_at DESC
       LIMIT 1`,
    )
    .bind(schoolId, nowSeconds)
    .first<LicenceRow>();
}

// ── Email token queries ───────────────────────────────────────────────────────

export async function insertEmailToken(
  db: D1Database,
  row: NewEmailTokenRow,
): Promise<void> {
  await db
    .prepare(
      `INSERT INTO email_tokens (token, user_id, purpose, expires_at)
       VALUES (?, ?, ?, ?)`,
    )
    .bind(row.token, row.user_id, row.purpose, row.expires_at)
    .run();
}

/**
 * Atomically consume an email token (one-shot).
 * Returns the token row if it was valid and unconsumed; null otherwise.
 */
export async function consumeEmailToken(
  db: D1Database,
  token: string,
  purpose: "verify" | "reset",
): Promise<EmailTokenRow | null> {
  const nowSeconds = Math.floor(Date.now() / 1000);
  const row = await db
    .prepare(
      `SELECT * FROM email_tokens
       WHERE token = ?
         AND purpose = ?
         AND consumed_at IS NULL
         AND expires_at > ?`,
    )
    .bind(token, purpose, nowSeconds)
    .first<EmailTokenRow>();

  if (!row) return null;

  await db
    .prepare("UPDATE email_tokens SET consumed_at = ? WHERE token = ?")
    .bind(nowSeconds, token)
    .run();

  return row;
}

// ── Admin event queries ───────────────────────────────────────────────────────

export async function logAdminEvent(
  db: D1Database,
  actor: string,
  action: string,
  entityType: string,
  entityId: string,
  payload: unknown,
): Promise<void> {
  const nowSeconds = Math.floor(Date.now() / 1000);
  await db
    .prepare(
      `INSERT INTO admin_events (actor, action, entity_type, entity_id, payload, at)
       VALUES (?, ?, ?, ?, ?, ?)`,
    )
    .bind(actor, action, entityType, entityId, stringifyJson(payload), nowSeconds)
    .run();
}
