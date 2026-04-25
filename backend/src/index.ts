import { Hono } from 'hono';
import { logger } from 'hono/logger';
import { cors } from 'hono/cors';
import { registerRoutes } from './routes';
import type { Bindings } from './lib/env';

const app = new Hono<{ Bindings: Bindings }>();

app.use('*', logger());

// CORS: this API is consumed by (a) the desktop app (httpx — no Origin header,
// CORS doesn't apply), and (b) the admin dashboard at admin.<domain> (M4+).
// We reject any browser origin except the app:// custom protocol (for future
// Tauri/Electron embedding) and leave admin origins to be added in M4.
app.use(
  '*',
  cors({
    origin: (origin) => {
      if (!origin) return origin; // no Origin header → non-browser client (our desktop)
      if (origin.startsWith('app://')) return origin;
      return null; // reject all other browser origins
    },
    credentials: true,
  }),
);

app.get('/healthz', (c) => c.json({ ok: true }));

app.get('/readyz', async (c) => {
  try {
    await c.env.DB.prepare('SELECT 1').first();
    return c.json({ ok: true });
  } catch (err) {
    return c.json({ ok: false, error: String(err) }, 503);
  }
});

registerRoutes(app);

export default app;
