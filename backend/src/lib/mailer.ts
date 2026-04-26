import type { Bindings } from "./env";

// TBD: Replace with actual app URL once custom domain is configured.
const APP_BASE_URL = "https://app.schooltool";

interface ResendEmailPayload {
  from: string;
  to: string[];
  subject: string;
  html: string;
}

async function sendEmail(
  env: Bindings,
  payload: ResendEmailPayload,
): Promise<void> {
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Resend API error ${res.status}: ${text}`);
  }
}

export async function sendVerificationEmail(
  env: Bindings,
  to: string,
  token: string,
): Promise<void> {
  const link = `${APP_BASE_URL}/verify-email?token=${encodeURIComponent(token)}`;
  await sendEmail(env, {
    from: `School Tool <${env.SUPPORT_EMAIL}>`,
    to: [to],
    subject: "Verify your School Tool email address",
    html: `
      <p>Welcome to School Tool!</p>
      <p>Please verify your email address by clicking the link below:</p>
      <p><a href="${link}">${link}</a></p>
      <p>This link expires in 24 hours.</p>
      <p>If you did not create an account, you can safely ignore this email.</p>
    `,
  });
}

export async function sendPasswordResetEmail(
  env: Bindings,
  to: string,
  token: string,
): Promise<void> {
  const link = `${APP_BASE_URL}/reset-password?token=${encodeURIComponent(token)}`;
  await sendEmail(env, {
    from: `School Tool <${env.SUPPORT_EMAIL}>`,
    to: [to],
    subject: "Reset your School Tool password",
    html: `
      <p>We received a request to reset your School Tool password.</p>
      <p>Click the link below to set a new password:</p>
      <p><a href="${link}">${link}</a></p>
      <p>This link expires in 30 minutes.</p>
      <p>If you did not request a password reset, you can safely ignore this email.</p>
    `,
  });
}

export async function sendApprovalEmail(
  env: Bindings,
  to: string,
  licenceExpiresAt: number,
): Promise<void> {
  const expiresDate = new Date(licenceExpiresAt * 1000).toLocaleDateString(
    "en-AU",
    { year: "numeric", month: "long", day: "numeric" },
  );
  await sendEmail(env, {
    from: `School Tool <${env.SUPPORT_EMAIL}>`,
    to: [to],
    subject: "Your School Tool licence has been approved",
    html: `
      <p>Great news! Your School Tool licence has been approved.</p>
      <p>Your licence is active until <strong>${expiresDate}</strong>.</p>
      <p>Open the School Tool desktop app, go to User → Service, and click <em>Refresh licence</em> to activate it.</p>
      <p>Thank you for your purchase.</p>
    `,
  });
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export async function sendLicenceExtendedEmail(
  env: Bindings,
  to: string,
  newExpiresAt: number,
  daysAdded: number,
  reason: string,
): Promise<void> {
  const newExpiresDate = new Date(newExpiresAt * 1000).toLocaleDateString(
    "en-AU",
    { year: "numeric", month: "long", day: "numeric" },
  );
  const safeReason = escapeHtml(reason);
  await sendEmail(env, {
    from: `School Tool <${env.SUPPORT_EMAIL}>`,
    to: [to],
    subject: "Your School Tool licence has been extended",
    html: `
      <p>Hello,</p>
      <p>Good news — your School Tool licence has been extended by <strong>${daysAdded}</strong> day(s).</p>
      <p>Your licence is now active until <strong>${newExpiresDate}</strong>.</p>
      <p>Reason: ${safeReason}</p>
      <p>If you have questions, reply to this email.</p>
      <p>— The School Tool team</p>
    `,
  });
}
