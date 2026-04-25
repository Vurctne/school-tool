/** Current time as unix seconds (integer). */
export function now(): number {
  return Math.floor(Date.now() / 1000);
}

/** Add N days to a unix-seconds timestamp. */
export function addDays(ts: number, days: number): number {
  return ts + days * 86400;
}

/**
 * Convert a unix-seconds timestamp to an ISO date string `YYYY-MM-DD`.
 * Uses UTC to avoid timezone-induced date shifts.
 */
export function toIsoDate(ts: number): string {
  return new Date(ts * 1000).toISOString().slice(0, 10);
}

/**
 * Parse an ISO date string `YYYY-MM-DD` to a unix-seconds timestamp
 * representing midnight UTC on that date.
 */
export function fromIsoDate(s: string): number {
  return Math.floor(new Date(`${s}T00:00:00Z`).getTime() / 1000);
}
