const CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

/**
 * Generate a prefixed ULID string.
 * Format: `{prefix}_{26-char-crockford-base32}`
 * - 10 chars: millisecond timestamp component
 * - 16 chars: cryptographically random component
 */
export function ulid(prefix: string): string {
  const now = Date.now();
  const timeChars: string[] = [];
  let t = now;
  for (let i = 9; i >= 0; i--) {
    timeChars[i] = CROCKFORD[t % 32];
    t = Math.floor(t / 32);
  }

  const randomBytes = new Uint8Array(10);
  crypto.getRandomValues(randomBytes);

  const randChars: string[] = [];
  // Pack 10 random bytes into 16 Crockford chars (10 bytes = 80 bits; 16 * 5 = 80 bits)
  let bits = 0;
  let bitCount = 0;
  let randIdx = 0;
  for (let i = 0; i < 16; i++) {
    while (bitCount < 5) {
      bits = (bits << 8) | randomBytes[randIdx++];
      bitCount += 8;
    }
    bitCount -= 5;
    randChars.push(CROCKFORD[(bits >> bitCount) & 31]);
  }

  return `${prefix}_${timeChars.join("")}${randChars.join("")}`;
}
