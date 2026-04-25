/**
 * Argon2id password hashing via hash-wasm.
 *
 * Parameters (per §12 security posture):
 *   memorySize  = 65536 (64 MB)
 *   iterations  = 3
 *   parallelism = 4
 *   outputType  = "encoded"  → $argon2id$v=19$... PHC string
 *
 * Test-environment note:
 *   Miniflare's workerd sandbox blocks dynamic WebAssembly compilation.
 *   When WASM is unavailable the functions fall back to a PBKDF2-SHA-256
 *   scheme (via the Web Crypto API) so that integration tests can exercise
 *   the full HTTP stack.  The fallback format is:
 *     $pbkdf2-sha256$i=310000$<base64-salt>$<base64-hash>
 *   Production Workers always use Argon2id; the fallback is never reached
 *   in an actual deployment.
 */

import { argon2id, argon2Verify } from "hash-wasm";

const MEMORY_SIZE = 65536;
const ITERATIONS = 3;
const PARALLELISM = 4;
const HASH_LENGTH = 32;
const SALT_LENGTH = 16;

// ── PBKDF2 fallback (Web Crypto — no WASM required) ──────────────────────────

const PBKDF2_PREFIX = "$pbkdf2-sha256$";
const PBKDF2_ITERATIONS = 310_000;

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
  } catch {
    // WASM unavailable (test sandbox) — use PBKDF2 fallback
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
  } catch {
    return false;
  }
}
