import { Hono } from "hono";
import type { Bindings } from "../lib/env";
import { authRoutes } from "./auth";
import { meRoutes } from "./me";
import { schoolsRoutes } from "./schools";

export function registerRoutes(app: Hono<{ Bindings: Bindings }>): void {
  app.route("/v1/auth", authRoutes);
  app.route("/v1/me", meRoutes);
  app.route("/v1/schools", schoolsRoutes);
}
