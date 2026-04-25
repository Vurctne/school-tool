import * as ed from "@noble/ed25519";

/**
 * Sign a licence payload with an Ed25519 private key.
 * Returns a string in the format "ed25519:<base64-signature>".
 * The payload is serialised as canonical JSON (keys sorted).
 */
export async function signLicenceToken(
  privateKeyBase64: string,
  payload: object,
): Promise<string> {
  const privateKeyBytes = base64ToBytes(privateKeyBase64);
  const message = new TextEncoder().encode(canonicalJson(payload));
  const signature = await ed.signAsync(message, privateKeyBytes);
  return `ed25519:${bytesToBase64(signature)}`;
}

/**
 * Derive the base64-encoded Ed25519 public key from a private key.
 */
export async function loadPublicKey(privateKeyBase64: string): Promise<string> {
  const privateKeyBytes = base64ToBytes(privateKeyBase64);
  const publicKeyBytes = await ed.getPublicKeyAsync(privateKeyBytes);
  return bytesToBase64(publicKeyBytes);
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function canonicalJson(obj: object): string {
  return JSON.stringify(sortKeys(obj));
}

function sortKeys(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(sortKeys);
  }
  if (value !== null && typeof value === "object") {
    const sorted: Record<string, unknown> = {};
    for (const key of Object.keys(value as Record<string, unknown>).sort()) {
      sorted[key] = sortKeys((value as Record<string, unknown>)[key]);
    }
    return sorted;
  }
  return value;
}

function base64ToBytes(b64: string): Uint8Array {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}
