# FAYDA ID BOT

A public, bilingual Telegram service platform with a mobile-first Mini App. This repository is separate from any previous bot project.

## Architecture

This repository contains three deployable parts:

- **Telegram bot** — `backend/app/bot.py`; handles `/start` and `/help` using Telegram long polling.
- **API backend** — `backend/app/main.py`; FastAPI service for health, status, authentication, orders, and payment submissions.
- **Mini App** — `frontend/`; React + TypeScript interface opened from the Telegram bot.

The bot and API must run as **two separate services**. Do not start long polling inside the FastAPI web process.

## Product direction

- Public user access with private, role-protected administration
- English and Amharic interface
- Telegram bot + Mini App
- FastAPI backend, PostgreSQL data layer, Redis-ready configuration
- Paid services with payment verification and manual-review fallback
- Dark navy interface with cyan and violet accents

## Current bot commands

- `/start` — sends the welcome message and, when configured, the Mini App button.
- `/help` — lists the available commands.

The bot registers these commands in Telegram when it starts. It uses long polling, so only one running bot service should use this token at a time.

## Integration and safety boundary

This application does not issue, alter, or certify official Fayda identity credentials. The eSignet client has been ported from the project archive supplied by the owner, but it is not yet connected to a customer-facing workflow. Enable it only with the owner's valid authorization and approved credentials. The resident API authorization value must be stored in the hosting provider's secrets, never in GitHub.

Never ask users to send OTPs to the bot. Never claim a payment or identity result is verified unless an authorized verification source confirms it.

## Payments

The backend has a provider-specific Cheki verification service for CBE Bank (`cbe`) and Telebirr (`telebirr`). CBE Birr (`cbebirr`) is accepted for manual review only. A payment is not approved from a screenshot, HTTP success alone, or transaction-reference format.

Customer order endpoints require valid Telegram Mini App initData. Prices come from the server-side `SERVICE_CATALOG_JSON`, not the browser. Customers can only view and submit payments for their own orders. Automatic verification remains in manual-review mode until trusted merchant receiver details are configured.

Cheki documentation: https://cheki.et/docs

## Security

- Never commit tokens, API credentials, signing keys, OTPs, or customer identity data.
- Keep all secrets in the hosting provider's environment variables.
- Validate Telegram Mini App initData on the server before accepting customer actions.
- Never log or store OTP values in plaintext.
- Use least-privilege admin roles, audit logs, rate limits, and data-retention rules.
- Configure trusted receiver details only after confirming the merchant accounts.

## Environment variables

See `.env.example`. Important variables:

- `TELEGRAM_BOT_TOKEN` — required by the Telegram bot and Mini App authentication.
- `TELEGRAM_MINI_APP_URL` — public HTTPS URL of the deployed Mini App.
- `DATABASE_URL` — production PostgreSQL connection string.
- `SERVICE_CATALOG_JSON` — server-controlled service codes and ETB prices, e.g. a JSON object such as `{"sample_service": "50"}`.
- `FAYDA_RESIDENT_AUTHORIZATION` — authorization header value for the approved resident API integration; configure only in Railway secrets, not in GitHub or chat.
- `CBE_RECEIVER_NAME`, `CBE_RECEIVER_ACCOUNT_SUFFIX`, `TELEBIRR_RECEIVER_NAME`, `TELEBIRR_RECEIVER_ACCOUNT_SUFFIX` — trusted receiver details used to gate automatic verification.

Do not put real values in GitHub or send them in chat.

## Local development

Backend API:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Telegram bot (in a second terminal):

```bash
cd backend
python -m app.bot
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Deployment outline

Deploy the frontend as a static site and set `TELEGRAM_MINI_APP_URL` to its public HTTPS URL.

Deploy the backend directory as a Docker service using `backend/Dockerfile` (or set the service root directory to `backend`):

1. **API service start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
2. **Bot service start command:** `python -m app.bot`

Both backend services need the same `TELEGRAM_BOT_TOKEN`. The bot service also needs `TELEGRAM_MINI_APP_URL`. The API service needs `DATABASE_URL`, `FRONTEND_ORIGIN`, and the appropriate server-side service/merchant configuration.

Use a persistent managed PostgreSQL database. Production startup intentionally does not create database tables automatically; run database migrations before enabling order/payment features. Do not run two bot instances with the same token because they will compete for Telegram updates.

## Release readiness

This repository is a working foundation, not yet a public production launch. Before launch:

- Configure secrets in the hosting provider.
- Deploy the frontend, API, and bot as separate services.
- Add and run production database migrations.
- Implement protected admin review endpoints and audit logs.
- Run the automated test suite and a Telegram end-to-end test.
- Confirm official Fayda authorization before enabling identity operations.
- Verify merchant payment details and test every provider, including manual-review paths.
