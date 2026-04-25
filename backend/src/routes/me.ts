import { Hono } from "hono";
import type { Bindings } from "../lib/env";
import type { UserRow } from "../lib/db";
import {
  listSchoolsForUser,
  listInvoicesForUser,
  getActiveLicenceForSchool,
} from "../lib/db";
import { requireUser } from "../lib/jwt";
import type { UserTokenPayload } from "../lib/jwt";

type MeVariables = {
  user: UserRow;
  jwtPayload: UserTokenPayload;
};

export const meRoutes = new Hono<{
  Bindings: Bindings;
  Variables: MeVariables;
}>();

// GET /  (auth required)
meRoutes.get("/", requireUser(), async (c) => {
  const user = c.var.user;

  const [schools, invoices] = await Promise.all([
    listSchoolsForUser(c.env.DB, user.id),
    listInvoicesForUser(c.env.DB, user.id),
  ]);

  // Get active licence for the user's first school (if any)
  const activeLicence =
    schools.length > 0
      ? await getActiveLicenceForSchool(c.env.DB, schools[0].id)
      : null;

  return c.json({
    user: {
      id: user.id,
      email: user.email,
      first_name: user.first_name,
      last_name: user.last_name,
      email_verified_at: user.email_verified_at,
      created_at: user.created_at,
      last_seen_at: user.last_seen_at,
    },
    schools,
    active_licence: activeLicence,
    invoices: invoices.slice(0, 20),
  });
});
