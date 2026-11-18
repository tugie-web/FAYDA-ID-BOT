# FAYDA ID BOT

A new public, bilingual Telegram service platform with a mobile-first Mini App. This repository is separate from any existing bot.

## Product direction
- Public user access with private, role-protected administration
- English and Amharic interface
- Telegram bot + Mini App
- FastAPI backend, PostgreSQL data layer, Redis-ready configuration
- Paid services with verified payment-provider webhooks
- Dark navy interface with cyan and violet accents

## Integration boundary
This application does not issue, alter, or certify official Fayda identity credentials. Identity verification or eSignet workflows must use an officially authorized Fayda integration and approved credentials. Until access and permissions are confirmed, the application remains in safe demo mode.

## Security
- Never commit tokens, API credentials, signing keys, OTPs, or customer identity data.
- Validate Telegram Mini App initData on the server before accepting customer actions.
- Never log or store OTP values in plaintext.
- Verify payment references server-side; screenshots are not proof of payment.
- Use least-privilege admin roles, audit logs, rate limits, and data-retention rules.

## Payment verification and persistence

The backend includes a provider-specific Cheki verification service for CBE Bank (`cbe`) and Telebirr (`telebirr`). The persistence layer also recognizes CBE Birr (`cbebirr`) as a payment choice, but automatic Cheki verification for that provider is not enabled yet; keep it in manual review until its exact API support is confirmed.

The database layer stores orders and payment submissions, enforces a UNIQUE constraint on `(provider, transaction_reference)`, and records verification source and manual-review audit details. An order is marked paid only after Cheki returns `verified: true` with matching provider, amount, and currency, or after an authorized admin explicitly approves it through the internal review function.

These are backend building blocks, not public payment endpoints. Do not expose order/payment operations until Telegram Mini App identity validation, customer ownership checks, and admin authorization are implemented. Configure PostgreSQL through `DATABASE_URL`; SQLite is only a local development fallback. Apply schema migrations before production deployment.

Cheki API contract: https://cheki.et/docs. Its hosted API is rate-limited and may be unavailable for some providers from some server regions, so manual review remains a fallback. Never treat HTTP 200, a transaction-ID format, or a screenshot alone as proof.

## Layout
- backend/: FastAPI service and database layer
- frontend/: React + TypeScript Mini App
- .env.example: placeholders only; copy locally to .env

## Local development
Backend: `cd backend`, install `requirements.txt`, then run `uvicorn app.main:app --reload`.
Frontend: `cd frontend`, run `npm install`, then `npm run dev`.

The first release remains a safe foundation. Real identity and payment integrations are not enabled until authorization, provider details, and secure user/admin flows are confirmed.


## Authenticated customer API foundation

Customer order endpoints require a valid Telegram Mini App initData signature in the Authorization header. The backend validates the HMAC signature and rejects expired initData (five-minute default). It derives the customer Telegram ID from the signed Telegram user object; clients cannot choose another customer ID.

- POST /api/v1/orders: creates an order using a server-controlled service price from SERVICE_CATALOG_JSON.
- GET /api/v1/orders: lists only the signed-in customer's orders.
- POST /api/v1/orders/{order_id}/payments: accepts provider and transaction reference; the amount comes from the stored order, not the client.

Automatic Cheki approval is blocked until the trusted receiver name and account suffix are configured for that provider. CBE Birr remains manual-review only. The Mini App API helper sends Telegram initData and does not store the bot token.

Admin review routes are intentionally not public yet. Add administrator allowlisting, audit logging, and authorization before exposing any admin action. Local development auto-creates tables; production must use managed schema migrations before deployment.
