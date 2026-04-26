import { Hono } from "hono";
import type { Bindings } from "../lib/env";
import type { UserRow } from "../lib/db";
import {
  listSchoolsForUser,
  findInvoiceById,
  insertPurchaseOrder,
  findPurchaseOrderById,
} from "../lib/db";
import { ulid } from "../lib/ids";
import { now } from "../lib/time";
import { requireUser } from "../lib/jwt";
import type { UserTokenPayload } from "../lib/jwt";

type PosVariables = {
  user: UserRow;
  jwtPayload: UserTokenPayload;
};

export const posRoutes = new Hono<{
  Bindings: Bindings;
  Variables: PosVariables;
}>();

// POST /  (auth required) — upload a purchase order PDF
posRoutes.post("/", requireUser(), async (c) => {
  const user = c.var.user;

  const body = await c.req.parseBody();
  const invoiceId = body["invoice_id"];
  const file = body["file"];

  if (!invoiceId || typeof invoiceId !== "string") {
    return c.json({ error: "invoice_id is required" }, 400);
  }
  if (!file || !(file instanceof File)) {
    return c.json({ error: "file is required" }, 400);
  }

  const MAX_BYTES = 10 * 1024 * 1024;
  if (file.size > MAX_BYTES) {
    return c.json({ error: "File too large; max 10 MB" }, 413);
  }

  const invoice = await findInvoiceById(c.env.DB, invoiceId);
  if (!invoice) {
    return c.json({ error: "Invoice not found" }, 404);
  }

  const schools = await listSchoolsForUser(c.env.DB, user.id);
  const linked = schools.some((s) => s.id === invoice.school_id);
  if (!linked) {
    return c.json({ error: "Forbidden" }, 403);
  }

  const poId = ulid("po");
  const extname = file.name.includes(".")
    ? "." + file.name.split(".").pop()
    : "";
  const r2Key = "pos/" + poId + extname;

  await c.env.R2.put(r2Key, file.stream(), {
    httpMetadata: { contentType: file.type || "application/octet-stream" },
  });

  await insertPurchaseOrder(c.env.DB, {
    id: poId,
    invoice_id: invoiceId,
    uploaded_by: user.id,
    original_filename: file.name,
    r2_key: r2Key,
    status: "uploaded",
    created_at: now(),
  });

  const purchaseOrder = await findPurchaseOrderById(c.env.DB, poId);
  return c.json({ purchase_order: purchaseOrder }, 201);
});

// GET /:id  (auth required) — poll status of a purchase order
posRoutes.get("/:id", requireUser(), async (c) => {
  const user = c.var.user;
  const poId = c.req.param("id");

  const purchaseOrder = await findPurchaseOrderById(c.env.DB, poId);
  if (!purchaseOrder) {
    return c.json({ error: "Purchase order not found" }, 404);
  }

  if (!purchaseOrder.invoice_id) {
    return c.json({ error: "Forbidden" }, 403);
  }

  const invoice = await findInvoiceById(c.env.DB, purchaseOrder.invoice_id);
  if (!invoice) {
    return c.json({ error: "Forbidden" }, 403);
  }

  const schools = await listSchoolsForUser(c.env.DB, user.id);
  const linked = schools.some((s) => s.id === invoice.school_id);
  if (!linked) {
    return c.json({ error: "Forbidden" }, 403);
  }

  return c.json({ purchase_order: purchaseOrder });
});
