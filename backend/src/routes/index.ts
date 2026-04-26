import { Hono } from "hono";
import type { Bindings } from "../lib/env";
import { authRoutes } from "./auth";
import { invoicesRoutes } from "./invoices";
import { licencesRoutes } from "./licences";
import { meRoutes } from "./me";
import { posRoutes } from "./pos";
import { schoolsRoutes } from "./schools";

export function registerRoutes(app: Hono<{ Bindings: Bindings }>): void {
  app.route("/v1/auth", authRoutes);
  app.route("/v1/invoices", invoicesRoutes);
  app.route("/v1/licences", licencesRoutes);
  app.route("/v1/me", meRoutes);
  app.route("/v1/purchase-orders", posRoutes);
  app.route("/v1/schools", schoolsRoutes);
}
