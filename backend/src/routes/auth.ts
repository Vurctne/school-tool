import { Hono } from "hono";
import { z } from "zod";
import type { Bindings } from "../lib/env";
import type { UserRow } from "../lib/db";
import {
  findUserByEmail,
  insertUser,
  insertSchool,
  linkUserSchool,
  insertEmailToken,
  consumeEmailToken,
  touchUserLastSeen,
  listSchoolsForUser,
} from "../lib/db";
import { ulid } from "../lib/ids";
import { now, addDays } from "../lib/time";
import { hashPassword, verifyPassword } from "../lib/argon2";
import { signUserToken } from "../lib/jwt";
import { sendVerificationEmail, sendPasswordResetEmail } from "../lib/mailer";
import { requireUser } from "../lib/jwt";

// ── Zod schemas ────────────────────────────────────────────────────────────────

const passwordSchema = z
  .string()
  .min(10, "Password must be at least 10 characters");

const registerSchema = z.object({
  email: z.string().email(),
  password: passwordSchema,
  first_name: z.string().min(1),
  last_name: z.string().min(1),
  school_name: z.string().min(1),
  abn: z.string().min(1),
});

const verifyEmailSchema = z.object({
  token: z.string().min(1),
});

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
  device_id: z.string().min(1),
});

const passwordResetRequestSchema = z.object({
  email: z.string().email(),
});

const passwordResetConfirmSchema = z.object({
  token: z.string().min(1),
  new_password: passwordSchema,
});

const passwordChangeSchema = z.object({
  old_password: z.string().min(1),
  new_password: passwordSchema,
});

// ── Helper: generate a cryptographically random token string ──────────────────

function generateToken(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

// ── Route definitions ─────────────────────────────────────────────────────────

type AuthVariables = { user: UserRow; jwtPayload: { sub: string; email: string; iat: number; exp: number } };

export const authRoutes = new Hono<{
  Bindings: Bindings;
  Variables: AuthVariables;
}>();

// POST /register
authRoutes.post("/register", async (c) => {
  const body = await c.req.json().catch(() => null);
  const parsed = registerSchema.safeParse(body);
  if (!parsed.success) {
    return c.json({ error: "Validation error", issues: parsed.error.issues }, 400);
  }
  const { email, password, first_name, last_name, school_name, abn } = parsed.data;

  // Enforce email uniqueness
  const existing = await findUserByEmail(c.env.DB, email);
  if (existing) {
    return c.json({ error: "Email already registered" }, 409);
  }

  const userId = ulid("usr");
  const schoolId = ulid("sch");
  const createdAt = now();

  const passwordHash = await hashPassword(password);

  await insertUser(c.env.DB, {
    id: userId,
    email,
    password_hash: passwordHash,
    first_name,
    last_name,
    created_at: createdAt,
  });

  await insertSchool(c.env.DB, {
    id: schoolId,
    name: school_name,
    abn,
    address: null,
    suburb: null,
    postcode: null,
    state: "VIC",
    created_by: userId,
    created_at: createdAt,
  });

  await linkUserSchool(c.env.DB, userId, schoolId, "owner");

  const emailToken = generateToken();
  await insertEmailToken(c.env.DB, {
    token: emailToken,
    user_id: userId,
    purpose: "verify",
    expires_at: addDays(createdAt, 1), // 24-hour TTL
  });

  // Fire-and-forget email; don't fail the request if it errors
  c.executionCtx.waitUntil(
    sendVerificationEmail(c.env, email, emailToken).catch((err: unknown) => {
      console.error({ event: "mailer.verify.error", error: String(err) });
    }),
  );

  console.log({ event: "auth.register", user_id: userId, email });

  return c.json({ ok: true });
});

// POST /verify-email
authRoutes.post("/verify-email", async (c) => {
  const body = await c.req.json().catch(() => null);
  const parsed = verifyEmailSchema.safeParse(body);
  if (!parsed.success) {
    return c.json({ error: "Validation error", issues: parsed.error.issues }, 400);
  }

  const tokenRow = await consumeEmailToken(c.env.DB, parsed.data.token, "verify");
  if (!tokenRow) {
    return c.json({ error: "Token invalid, expired, or already used" }, 400);
  }

  await c.env.DB.prepare(
    "UPDATE users SET email_verified_at = ? WHERE id = ?",
  )
    .bind(now(), tokenRow.user_id)
    .run();

  console.log({ event: "auth.verify_email", user_id: tokenRow.user_id });

  return c.json({ ok: true });
});

// POST /login
authRoutes.post("/login", async (c) => {
  // TODO: Implement rate limiting (10 failed attempts per email+IP per 15 min).
  // Real rate limiting will come via Cloudflare Rate Limiting Rules in a later milestone.
  // For now, track failed attempts in D1 login_attempts table is deferred.

  const body = await c.req.json().catch(() => null);
  const parsed = loginSchema.safeParse(body);
  if (!parsed.success) {
    return c.json({ error: "Validation error", issues: parsed.error.issues }, 400);
  }
  // device_id is accepted by the schema for future device-binding bookkeeping
  // (tracked server-side from M4 onwards); intentionally unused here.
  const { email, password } = parsed.data;

  const user = await findUserByEmail(c.env.DB, email);
  if (!user) {
    // Constant-time: always verify against a dummy hash to avoid timing attacks
    await verifyPassword(password, "$argon2id$v=19$m=65536,t=3,p=4$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA");
    return c.json({ error: "Invalid credentials" }, 401);
  }

  const valid = await verifyPassword(password, user.password_hash);
  if (!valid) {
    return c.json({ error: "Invalid credentials" }, 401);
  }

  if (!user.email_verified_at) {
    return c.json({ error: "Email not verified" }, 403);
  }

  await touchUserLastSeen(c.env.DB, user.id);

  const token = await signUserToken(
    c.env.JWT_SECRET_USER,
    user.id,
    user.email,
    90,
  );

  // Avoid logging device_id alongside email to keep the audit line PII-lean.
  console.log({ event: "auth.login", user_id: user.id });

  const schools = await listSchoolsForUser(c.env.DB, user.id);
  const firstSchool = schools[0] ?? null;

  return c.json({
    access_token: token,
    user: {
      id: user.id,
      email: user.email,
      first_name: user.first_name,
      last_name: user.last_name,
      email_verified_at: user.email_verified_at,
      created_at: user.created_at,
      last_seen_at: user.last_seen_at,
      school: firstSchool
        ? {
            id: firstSchool.id,
            name: firstSchool.name,
            abn: firstSchool.abn,
          }
        : null,
    },
  });
});

// POST /password-reset/request
authRoutes.post("/password-reset/request", async (c) => {
  const body = await c.req.json().catch(() => null);
  const parsed = passwordResetRequestSchema.safeParse(body);
  if (!parsed.success) {
    // Anti-enumeration: always return ok
    return c.json({ ok: true });
  }

  const { email } = parsed.data;

  // Anti-enumeration: always return ok regardless of whether email exists
  const user = await findUserByEmail(c.env.DB, email);
  if (user) {
    const resetToken = generateToken();
    const createdAt = now();
    await insertEmailToken(c.env.DB, {
      token: resetToken,
      user_id: user.id,
      purpose: "reset",
      expires_at: createdAt + 30 * 60, // 30-min TTL
    });

    c.executionCtx.waitUntil(
      sendPasswordResetEmail(c.env, email, resetToken).catch((err: unknown) => {
        console.error({ event: "mailer.reset.error", error: String(err) });
      }),
    );

    console.log({ event: "auth.password_reset_request", user_id: user.id });
  }

  return c.json({ ok: true });
});

// POST /password-reset/confirm
authRoutes.post("/password-reset/confirm", async (c) => {
  const body = await c.req.json().catch(() => null);
  const parsed = passwordResetConfirmSchema.safeParse(body);
  if (!parsed.success) {
    return c.json({ error: "Validation error", issues: parsed.error.issues }, 400);
  }

  const tokenRow = await consumeEmailToken(c.env.DB, parsed.data.token, "reset");
  if (!tokenRow) {
    return c.json({ error: "Token invalid, expired, or already used" }, 400);
  }

  const newHash = await hashPassword(parsed.data.new_password);
  await c.env.DB.prepare(
    "UPDATE users SET password_hash = ? WHERE id = ?",
  )
    .bind(newHash, tokenRow.user_id)
    .run();

  console.log({ event: "auth.password_reset_confirm", user_id: tokenRow.user_id });

  return c.json({ ok: true });
});

// POST /password/change  (auth required)
authRoutes.post(
  "/password/change",
  requireUser(),
  async (c) => {
    const body = await c.req.json().catch(() => null);
    const parsed = passwordChangeSchema.safeParse(body);
    if (!parsed.success) {
      return c.json({ error: "Validation error", issues: parsed.error.issues }, 400);
    }

    const user = c.var.user;
    const valid = await verifyPassword(parsed.data.old_password, user.password_hash);
    if (!valid) {
      return c.json({ error: "Old password is incorrect" }, 400);
    }

    const newHash = await hashPassword(parsed.data.new_password);
    await c.env.DB.prepare(
      "UPDATE users SET password_hash = ? WHERE id = ?",
    )
      .bind(newHash, user.id)
      .run();

    console.log({ event: "auth.password_change", user_id: user.id });

    // JWT is stateless — existing tokens remain valid until expiry.
    // The user's current session continues uninterrupted.
    return c.json({ ok: true });
  },
);
