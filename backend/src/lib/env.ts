export interface Bindings {
  DB: D1Database;
  R2: R2Bucket;
  AI: Ai;
  OCR_QUEUE: Queue<{ poId: string }>;
  // vars (all arrive as strings from wrangler.toml [vars])
  PRICING_CENTS_SUBTOTAL: string;
  GST_RATE: string;
  PRICING_CENTS_TOTAL: string;
  PRODUCT_NAME: string;
  SELLER_NAME: string;
  SELLER_ABN_TBD: string;
  SUPPORT_EMAIL: string;
  LICENCE_DAYS: string;
  // secrets (injected via `wrangler secret put`)
  JWT_SECRET_USER: string;
  JWT_SECRET_ADMIN: string;
  ADMIN_PASSWORD_ARGON2_HASH: string;
  ADMIN_TOTP_SECRET: string;
  LICENCE_SIGNING_PRIVATE_KEY_ED25519: string;
  RESEND_API_KEY: string;
}
