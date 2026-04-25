import { sign, verify } from "hono/jwt";
import type { Context, MiddlewareHandler } from "hono";
import type { Bindings } from "./env";
import type { UserRow } from "./db";

export interface UserTokenPayload {
  sub: string;
  email: string;
  iat: number;
  exp: number;
}

/** Variables made available on c.var by requireUser(). */
export interface AuthVariables {
  user: UserRow;
}

const DEFAULT_TTL_DAYS = 90;

// Fallback used only when JWT_SECRET_USER is not set (e.g. test environment).
// Never reached in production because wrangler secret is always injected.
const TEST_FALLBACK_SECRET = "sft-test-secret-not-for-production";

function resolveSecret(secret: string): string {
  return secret || TEST_FALLBACK_SECRET;
}

export async function signUserToken(
  secret: string,
  sub: string,
  email: string,
  ttlDays: number = DEFAULT_TTL_DAYS,
): Promise<string> {
  const iat = Math.floor(Date.now() / 1000);
  const exp = iat + ttlDays * 86400;
  return sign({ sub, email, iat, exp }, resolveSecret(secret), "HS256");
}

export async function verifyUserToken(
  secret: string,
  token: string,
): Promise<UserTokenPayload> {
  const payload = await verify(token, resolveSecret(secret), "HS256");
  return payload as unknown as UserTokenPayload;
}

/**
 * Hono middleware: reads Authorization: Bearer <token>, verifies against
 * env.JWT_SECRET_USER, stores the raw payload on c.var.jwtPayload.
 * Note: caller routes must fetch the full user row using sub from the payload.
 */
export function requireAuth(): MiddlewareHandler<{
  Bindings: Bindings;
  Variables: { jwtPayload: UserTokenPayload };
}> {
  return async (c, next) => {
    const authHeader = c.req.header("Authorization");
    if (!authHeader || !authHeader.startsWith("Bearer ")) {
      return c.json({ error: "Unauthorized" }, 401);
    }
    const token = authHeader.slice(7);
    try {
      const payload = await verifyUserToken(c.env.JWT_SECRET_USER, token);
      c.set("jwtPayload", payload);
      await next();
    } catch {
      return c.json({ error: "Unauthorized" }, 401);
    }
  };
}

/**
 * Hono middleware: requireAuth + fetches UserRow from D1 and stores on c.var.user.
 */
export function requireUser(): MiddlewareHandler<{
  Bindings: Bindings;
  Variables: { user: UserRow; jwtPayload: UserTokenPayload };
}> {
  return async (c: Context<{ Bindings: Bindings; Variables: { user: UserRow; jwtPayload: UserTokenPayload } }>, next) => {
    const authHeader = c.req.header("Authorization");
    if (!authHeader || !authHeader.startsWith("Bearer ")) {
      return c.json({ error: "Unauthorized" }, 401);
    }
    const token = authHeader.slice(7);
    try {
      const payload = await verifyUserToken(c.env.JWT_SECRET_USER, token);
      c.set("jwtPayload", payload);

      const { findUserById } = await import("./db");
      const user = await findUserById(c.env.DB, payload.sub);
      if (!user) {
        return c.json({ error: "Unauthorized" }, 401);
      }
      c.set("user", user);
      await next();
    } catch {
      return c.json({ error: "Unauthorized" }, 401);
    }
  };
}
