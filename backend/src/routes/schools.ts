import { Hono } from "hono";
import { z } from "zod";
import type { Bindings } from "../lib/env";
import type { UserRow } from "../lib/db";
import {
  findSchoolById,
  insertSchool,
  linkUserSchool,
} from "../lib/db";
import { ulid } from "../lib/ids";
import { now } from "../lib/time";
import { requireUser } from "../lib/jwt";
import type { UserTokenPayload } from "../lib/jwt";

type SchoolsVariables = {
  user: UserRow;
  jwtPayload: UserTokenPayload;
};

const createSchoolSchema = z.object({
  name: z.string().min(1),
  abn: z.string().optional(),
  address: z.string().optional(),
  suburb: z.string().optional(),
  postcode: z.string().optional(),
  state: z.string().optional(),
});

export const schoolsRoutes = new Hono<{
  Bindings: Bindings;
  Variables: SchoolsVariables;
}>();

// POST /  (auth required) — create a second school and link as member
schoolsRoutes.post("/", requireUser(), async (c) => {
  const body = await c.req.json().catch(() => null);
  const parsed = createSchoolSchema.safeParse(body);
  if (!parsed.success) {
    return c.json({ error: "Validation error", issues: parsed.error.issues }, 400);
  }

  const user = c.var.user;
  const { name, abn, address, suburb, postcode, state } = parsed.data;
  const schoolId = ulid("sch");
  const createdAt = now();

  await insertSchool(c.env.DB, {
    id: schoolId,
    name,
    abn: abn ?? null,
    address: address ?? null,
    suburb: suburb ?? null,
    postcode: postcode ?? null,
    state: state ?? "VIC",
    created_by: user.id,
    created_at: createdAt,
  });

  // Link as member (not owner, since they already own their first school)
  await linkUserSchool(c.env.DB, user.id, schoolId, "member");

  console.log({ event: "schools.create", school_id: schoolId, user_id: user.id });

  const school = await findSchoolById(c.env.DB, schoolId);
  return c.json({ school }, 201);
});

// GET /:id  (auth required)
schoolsRoutes.get("/:id", requireUser(), async (c) => {
  const user = c.var.user;
  const schoolId = c.req.param("id");

  // Verify user is linked to this school
  const membership = await c.env.DB.prepare(
    "SELECT 1 FROM user_schools WHERE user_id = ? AND school_id = ?",
  )
    .bind(user.id, schoolId)
    .first<{ 1: number }>();

  if (!membership) {
    return c.json({ error: "School not found" }, 404);
  }

  const school = await findSchoolById(c.env.DB, schoolId);
  if (!school) {
    return c.json({ error: "School not found" }, 404);
  }

  return c.json({ school });
});
