import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { sendLicenceExtendedEmail } from "../src/lib/mailer";
import type { Bindings } from "../src/lib/env";

// Minimal fake env — only the fields mailer.ts needs.
const fakeEnv = {
  RESEND_API_KEY: "re_test_key_abc123",
  SUPPORT_EMAIL: "Vurctne@gmail.com",
} as unknown as Bindings;

// ── Fetch mock ────────────────────────────────────────────────────────────────

let mockFetch: ReturnType<typeof vi.fn>;
let originalFetch: typeof globalThis.fetch;

beforeEach(() => {
  originalFetch = globalThis.fetch;
  mockFetch = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
    const url =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.toString()
          : (input as Request).url;
    if (url === "https://api.resend.com/emails") {
      return new Response(JSON.stringify({ id: "mock_email_id" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return originalFetch(input, _init);
  });
  globalThis.fetch = mockFetch as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Extract the parsed JSON body from the first fetch call. */
function capturedBody(): Record<string, unknown> {
  const call = mockFetch.mock.calls[0] as [RequestInfo | URL, RequestInit?];
  const init = call[1];
  return JSON.parse(init?.body as string) as Record<string, unknown>;
}

/** Format a unix-second timestamp with the same en-AU options mailer uses. */
function enAUDate(unixSeconds: number): string {
  return new Date(unixSeconds * 1000).toLocaleDateString("en-AU", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("sendLicenceExtendedEmail", () => {
  // 1. Calls Resend with the correct URL and method.
  it("sends a POST request to https://api.resend.com/emails", async () => {
    await sendLicenceExtendedEmail(fakeEnv, "user@school.vic.edu.au", 1800000000, 14, "Outage compensation");

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const call = mockFetch.mock.calls[0] as [RequestInfo | URL, RequestInit?];
    const url =
      typeof call[0] === "string"
        ? call[0]
        : call[0] instanceof URL
          ? call[0].toString()
          : (call[0] as Request).url;
    expect(url).toBe("https://api.resend.com/emails");
    expect(call[1]?.method).toBe("POST");
  });

  // 2. Authorization header has the form Bearer <key>.
  it("sets the Authorization header to Bearer <RESEND_API_KEY>", async () => {
    await sendLicenceExtendedEmail(fakeEnv, "user@school.vic.edu.au", 1800000000, 14, "Outage compensation");

    const call = mockFetch.mock.calls[0] as [RequestInfo | URL, RequestInit?];
    const headers = call[1]?.headers as Record<string, string>;
    expect(headers["Authorization"]).toBe(`Bearer ${fakeEnv.RESEND_API_KEY}`);
  });

  // 3. Request body has the correct from, to, and subject.
  it("sends correct from, to, and subject fields", async () => {
    const to = "user@school.vic.edu.au";
    await sendLicenceExtendedEmail(fakeEnv, to, 1800000000, 14, "Outage compensation");

    const body = capturedBody();
    expect(body["from"]).toBe(`School Tool <${fakeEnv.SUPPORT_EMAIL}>`);
    expect(body["to"]).toEqual([to]);
    expect(body["subject"]).toBe("Your School Tool licence has been extended");
  });

  // 4. HTML body contains daysAdded, the formatted date, and the reason.
  it("includes daysAdded, formatted expiry date, and reason in the HTML body", async () => {
    const newExpiresAt = 1800000000;
    const daysAdded = 30;
    const reason = "Pilot programme extension";
    await sendLicenceExtendedEmail(fakeEnv, "user@school.vic.edu.au", newExpiresAt, daysAdded, reason);

    const body = capturedBody();
    const html = body["html"] as string;

    expect(html).toContain(String(daysAdded));
    expect(html).toContain(enAUDate(newExpiresAt));
    expect(html).toContain(reason);
  });

  // 5. HTML injection in reason is escaped.
  it("escapes HTML special characters in the reason string", async () => {
    const maliciousReason = "<script>alert('xss')</script>";
    await sendLicenceExtendedEmail(fakeEnv, "user@school.vic.edu.au", 1800000000, 14, maliciousReason);

    const body = capturedBody();
    const html = body["html"] as string;

    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
  });

  // 6. en-AU date format is consistent with sendApprovalEmail (same Date API call).
  it("formats newExpiresAt using the same en-AU long date format as sendApprovalEmail", async () => {
    // unix timestamp 1700000000 = 14 November 2023 in en-AU long format
    const testTs = 1700000000;
    const expected = enAUDate(testTs); // "14 November 2023"

    await sendLicenceExtendedEmail(fakeEnv, "user@school.vic.edu.au", testTs, 14, "Test reason");

    const body = capturedBody();
    const html = body["html"] as string;
    expect(html).toContain(expected);
  });
});
