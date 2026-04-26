import { Hono } from "hono";
import { z } from "zod";
import type { Context } from "hono";
import type { Bindings } from "../lib/env";
import type { UserRow } from "../lib/db";
import {
  listSchoolsForUser,
  getActiveLicenceForSchool,
  findSchoolById,
  listLicenceDevicesByLicence,
  deleteLicenceDevice,
  upsertLicenceDevice,
} from "../lib/db";
import { now } from "../lib/time";
import { requireUser } from "../lib/jwt";
import type { UserTokenPayload } from "../lib/jwt";
import { signLicenceToken } from "../lib/ed25519";

type LicencesVariables = {
  user: UserRow;
  jwtPayload: UserTokenPayload;
};

type LicencesEnv = {
  Bindings: Bindings;
  Variables: LicencesVariables;
};

const activateSchema = z.object({
  device_id: z.string().min(1),
  os_info: z.string().nullable().optional(),
  app_version: z.string().nullable().optional(),
});

export const licencesRoutes = new Hono<LicencesEnv>();

// Shared handler for POST /activate and POST /refresh
async function activateHandler(c: Context<LicencesEnv>): Promise<Response> {
  const user = c.var.user;

  const rawBody = await c.req.json().catch(() => null);
  const parsed = activateSchema.safeParse(rawBody);
  if (!parsed.success) {
    return c.json({ error: "Validation error", issues: parsed.error.issues }, 400);
  }

  const { device_id, os_info, app_version } = parsed.data;

  // 1. Find an active licence for one of the user's schools
  const schools = await listSchoolsForUser(c.env.DB, user.id);
  let licence = null;
  for (const school of schools) {
    const found = await getActiveLicenceForSchool(c.env.DB, school.id);
    if (found) {
      licence = found;
      break;
    }
  }

  if (!licence) {
    return c.json({ error: "No active licence" }, 404);
  }

  // 2. Manage the device cap (max 3; LRU eviction on 4th new device)
  const devices = await listLicenceDevicesByLicence(c.env.DB, licence.id);
  const existing = devices.find((d) => d.device_id === device_id);

  if (!existing && devices.length >= 3) {
    // Evict the least-recently-seen device (last in DESC-sorted list)
    const lru = devices[devices.length - 1];
    await deleteLicenceDevice(c.env.DB, licence.id, lru.device_id);
  }

  const nowTs = now();
  await upsertLicenceDevice(c.env.DB, {
    licence_id: licence.id,
    device_id,
    first_seen: existing ? existing.first_seen : nowTs,
    last_seen: nowTs,
    os_info: os_info ?? null,
    app_version: app_version ?? null,
  });

  // 3. Resolve school for the licence
  const school = await findSchoolById(c.env.DB, licence.school_id);
  if (!school) {
    return c.json({ error: "School not found" }, 500);
  }

  // 4. Build the payload and sign
  const payload = {
    licence_id: licence.id,
    school_id: licence.school_id,
    school_name: school.name,
    email: user.email,
    device_id,
    issued_at: new Date().toISOString(),
    expires_at: new Date(licence.expires_at * 1000).toISOString(),
    features: JSON.parse(licence.features) as unknown[],
  };

  let signature: string;
  try {
    signature = await signLicenceToken(
      c.env.LICENCE_SIGNING_PRIVATE_KEY_ED25519,
      payload,
    );
  } catch {
    return c.json({ error: "Signing failed" }, 500);
  }

  // 5. Return payload + signature
  return c.json({ ...payload, signature });
}

// Both paths share the same handler
licencesRoutes.post("/activate", requireUser(), activateHandler);
licencesRoutes.post("/refresh", requireUser(), activateHandler);
