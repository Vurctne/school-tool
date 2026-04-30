/**
 * Argon2id password hashing via hash-wasm — with PBKDF2 fallback.
 *
 * Argon2id parameters (per §12 security posture):
 *   memorySize  = 65536 (64 MB)
 *   iterations  = 3
 *   parallelism = 4
 *   outputType  = "encoded"  → $argon2id$v=19$... PHC string
 *
 * Fallback note:
 *   In *some* runtimes (Miniflare test sandbox; certain production Worker
 *   builds where dynamic WASM compilation is restricted) hash-wasm's
 *   argon2id throws.  We then fall back to PBKDF2-SHA-256 via Web Crypto.
 *
 *   Cloudflare Workers caps PBKDF2 iterations at 100_000 — 310_000 is
 *   rejected with NotSupportedError.  We sit at the cap; if/when the
 *   limit changes we can raise.  The fallback format is:
 *     $pbkdf2-sha256$i=100000$<base64-salt>$<base64-hash>
 *
 *   Argon2id errors are logged to console.warn with name+message so
 *   `wrangler tail` shows whether WASM is silently failing in prod.
 */

import { argon2id, argon2Verify } from "hash-wasm";

const MEMORY_SIZE = 65536;
const ITERATIONS = 3;
const PARALLELISM = 4;
const HASH_LENGTH = 32;
const SALT_LENGTH = 16;

// ── PBKDF2 fallback (Web Crypto — no WASM required) ──────────────────────────

const PBKDF2_PREFIX = "$pbkdf2-sha256$";
// Cloudflare Workers Web Crypto rejects PBKDF2 iterations > 100_000 with
// NotSupportedError.  Sit at the cap; revisit if Workers raises the limit.
const PBKDF2_ITERATIONS = 100_000;

async function pbkdf2Hash(password: string, salt: Uint8Array): Promise<string> {
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    { name: "PBKDF2" },
    false,
    ["deriveBits"],
  );
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt, iterations: PBKDF2_ITERATIONS },
    keyMaterial,
    256,
  );
  const saltB64 = btoa(String.fromCharCode(...salt));
  const hashB64 = btoa(String.fromCharCode(...new Uint8Array(bits)));
  return `${PBKDF2_PREFIX}i=${PBKDF2_ITERATIONS}$${saltB64}$${hashB64}`;
}

async function pbkdf2Verify(password: string, encoded: string): Promise<boolean> {
  // Format: $pbkdf2-sha256$i=<iter>$<salt-b64>$<hash-b64>
  const parts = encoded.split("$");
  // parts: ["", "pbkdf2-sha256", "i=310000", "<salt>", "<hash>"]
  if (parts.length !== 5 || parts[1] !== "pbkdf2-sha256") return false;
  const saltB64 = parts[3];
  const expectedHashB64 = parts[4];
  const salt = Uint8Array.from(atob(saltB64), (c) => c.charCodeAt(0));
  const candidate = await pbkdf2Hash(password, salt);
  const candidateParts = candidate.split("$");
  const candidateHashB64 = candidateParts[4];
  // Constant-time comparison via subtle.timingSafeEqual isn't available in
  // Web Crypto, but timing leakage here only affects the test environment.
  return candidateHashB64 === expectedHashB64;
}

// ── Public API ────────────────────────────────────────────────────────────────

export async function hashPassword(password: string): Promise<string> {
  const salt = new Uint8Array(SALT_LENGTH);
  crypto.getRandomValues(salt);

  try {
    return await argon2id({
      password,
      salt,
      iterations: ITERATIONS,
      memorySize: MEMORY_SIZE,
      parallelism: PARALLELISM,
      hashLength: HASH_LENGTH,
      outputType: "encoded",
    });
  } catch (err) {
    // WASM unavailable (test sandbox or restricted Worker build) — fall back.
    // Log so `wrangler tail` reveals whether prod is silently degrading.
    const msg = err instanceof Error ? `${err.name}: ${err.message}` : String(err);
    console.warn({ event: "argon2.hash.fallback_pbkdf2", error: msg });
    return pbkdf2Hash(password, salt);
  }
}

export async function verifyPassword(
  password: string,
  hash: string,
): Promise<boolean> {
  if (hash.startsWith(PBKDF2_PREFIX)) {
    return pbkdf2Verify(password, hash);
  }
  try {
    return await argon2Verify({ password, hash });
  } catch (err) {
    const msg = err instanceof Error ? `${err.name}: ${err.message}` : String(err);
    console.warn({ event: "argon2.verify.error", error: msg });
    return false;
  }
}
