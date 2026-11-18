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
- Validate Telegram Mini App initData on the server.
- Never log or store OTP values in plaintext.
- Verify payment webhooks server-side; screenshots are not proof of payment.
- Use least-privilege admin roles, audit logs, rate limits, and data-retention rules.

## Payment verification foundation

The backend includes a provider-specific Cheki verification service for:
- CBE Bank (Cheki bank code: `cbe`)
- Telebirr (Cheki bank code: `telebirr`)

The service checks the provider returned by Cheki, `verified: true`, the exact ETB amount, and optional configured merchant receiver details. A mismatched provider or amount is rejected. API outages, rate limits, and unconfirmed receipts go to manual review; they never authorize service activation.

This is currently a verification module, not a complete checkout or payment activation workflow. Before launch, connect it to payment/order records and an admin review screen. Enforce a database UNIQUE constraint on provider + transaction reference, atomically claim each reference, and activate a paid order only after verification succeeds. Configure the expected merchant receiver details from trusted deployment settings, not user input. Never store payment credentials or customer secrets in this public repository.

Cheki API contract: https://cheki.et/docs. Cheki states that only `verified: true` means the bank's own record confirmed the receipt; HTTP 200 or `success: true` alone is not enough. The hosted API is rate-limited and may be unavailable for some providers from some server regions, so retain manual review as a fallback.

## Layout
- backend/: FastAPI service
- frontend/: React + TypeScript Mini App
- .env.example: placeholders only; copy locally to .env

## Local development
Backend: cd backend, install requirements.txt, then run uvicorn app.main:app --reload.
Frontend: cd frontend, run npm install, then npm run dev.

The first release is a safe foundation with a health endpoint and a bilingual landing screen. Real identity and payment integrations are not enabled until authorization and provider details are confirmed.
