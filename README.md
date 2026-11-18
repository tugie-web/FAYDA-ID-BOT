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

## Layout
- backend/: FastAPI service
- frontend/: React + TypeScript Mini App
- .env.example: placeholders only; copy locally to .env

## Local development
Backend: cd backend, install requirements.txt, then run uvicorn app.main:app --reload.
Frontend: cd frontend, run npm install, then npm run dev.

The first release is a safe foundation with a health endpoint and a bilingual landing screen. Real identity and payment integrations are not enabled until authorization and provider details are confirmed.
