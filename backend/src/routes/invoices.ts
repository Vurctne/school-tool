import { Hono } from "hono";
import { z } from "zod";
import type { Bindings } from "../lib/env";
import type { UserRow } from "../lib/db";
import {
  findSchoolById,
  insertInvoice,
  findInvoiceById,
  countInvoicesIssuedInYear,
} from "../lib/db";
import { ulid } from "../lib/ids";
import { now, addDays, toIsoDate } from "../lib/time";
import { requireUser } from "../lib/jwt";
import type { UserTokenPayload } from "../lib/jwt";

type InvoicesVariables = {
  user: UserRow;
  jwtPayload: UserTokenPayload;
};

const createInvoiceSchema = z.object({
  school_id: z.string().min(1),
});

export const invoicesRoutes = new Hono<{
  Bindings: Bindings;
  Variables: InvoicesVariables;
}>();

// POST /  (auth required) — create an annual invoice for the given school
invoicesRoutes.post("/", requireUser(), async (c) => {
  const user = c.var.user;
  const body = await c.req.json().catch(() => null);
  const parsed = createInvoiceSchema.safeParse(body);
  if (!parsed.success) {
    return c.json({ error: "Validation error", issues: parsed.error.issues }, 400);
  }

  const { school_id } = parsed.data;

  // Verify school exists and is linked to the requesting user
  const school = await findSchoolById(c.env.DB, school_id);
  if (!school) {
    return c.json({ error: "School not found or not linked to user" }, 403);
  }

  const membership = await c.env.DB.prepare(
    "SELECT 1 FROM user_schools WHERE user_id = ? AND school_id = ?",
  )
    .bind(user.id, school_id)
    .first<{ 1: number }>();

  if (!membership) {
    return c.json({ error: "School not found or not linked to user" }, 403);
  }

  // Compute amounts
  const subtotal_cents = Number(c.env.PRICING_CENTS_SUBTOTAL);
  const gst_cents = Math.round(subtotal_cents * Number(c.env.GST_RATE));
  const total_cents = Number(c.env.PRICING_CENTS_TOTAL);

  // Compute the invoice number (SFT-YYYY-NNNN)
  const nowTs = now();
  const year = new Date(nowTs * 1000).getUTCFullYear();
  const seq = (await countInvoicesIssuedInYear(c.env.DB, year)) + 1;
  const number = `SFT-${year}-${String(seq).padStart(4, "0")}`;

  // Compute dates
  const issue_date = toIsoDate(nowTs);
  const due_date = toIsoDate(addDays(nowTs, 30));
  const period_start = issue_date;
  const period_end = toIsoDate(addDays(nowTs, Number(c.env.LICENCE_DAYS)));

  // Generate IDs and keys
  const invoiceId = ulid("inv");
  const r2_key = `invoices/${invoiceId}.pdf`;

  await insertInvoice(c.env.DB, {
    id: invoiceId,
    number,
    school_id,
    user_id: user.id,
    issue_date,
    due_date,
    period_start,
    period_end,
    subtotal_cents,
    gst_cents,
    total_cents,
    currency: "AUD",
    status: "issued",
    r2_key,
    created_at: nowTs,
  });

  const invoice = await findInvoiceById(c.env.DB, invoiceId);
  return c.json({ invoice, pdf_url: null }, 201);
});

// GET /:id/pdf  (auth required) — PDF redirect stub (M4-deferred)
invoicesRoutes.get("/:id/pdf", requireUser(), async (c) => {
  const user = c.var.user;
  const invoiceId = c.req.param("id");

  const invoice = await findInvoiceById(c.env.DB, invoiceId);
  if (!invoice) {
    return c.json({ error: "Invoice not found" }, 404);
  }

  // Check the invoice belongs to a school linked to the requesting user
  const membership = await c.env.DB.prepare(
    "SELECT 1 FROM user_schools WHERE user_id = ? AND school_id = ?",
  )
    .bind(user.id, invoice.school_id)
    .first<{ 1: number }>();

  if (!membership) {
    return c.json({ error: "Forbidden" }, 403);
  }

  // PDF rendering is M4 work — deliberate stub
  return c.json({ error: "PDF rendering pending M4" }, 501);
});
