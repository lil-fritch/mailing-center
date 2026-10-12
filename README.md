# Mailing Center

AI-powered B2B outreach platform, built as a freelance contract project
(2024–2025): collect leads, generate personalized emails with OpenAI
Assistants, send them, and process replies automatically.

> This is a sanitized snapshot for portfolio purposes: no client data,
> no real credentials. See `backend/app/config/*.example.json` for the
> shape of the sender-account config, with fake values.

## Architecture

Two independently deployable services, split so that email *delivery*
(provider-specific, stateful, flaky) never blocks email *orchestration*
(campaign logic, AI generation, scheduling):

```
┌─────────────────┐  POST /email/send   ┌──────────────────┐
│  backend/        │ ───────────────────▶│  sender/          │
│  (mailing_center)│                      │  (mailing_sender) │
│                  │◀─────────────────────│                  │
│  - campaigns     │   success/error      │  - SMTP (Gmail)  │
│  - OpenAI email  │                      │  - Selenium      │
│    generation    │                      │    (op.pl, no    │
│  - IMAP reply    │                      │    SMTP access)  │
│    polling       │                      │  - send history  │
│  - B2B database  │                      │                  │
└─────────────────┘                      └──────────────────┘
```

- **`backend/`** — FastAPI service owning campaigns, the B2B leads
  database (PostgreSQL + SQLAlchemy + Alembic), OpenAI-driven email and
  reply generation, and an IMAP poller that watches for and auto-drafts
  responses to incoming replies. JWT-protected (see its README).
- **`sender/`** — a deliberately dumb delivery service: given a
  `from_email`/`to_email`/subject/body, it sends it right away, through
  SMTP where the provider supports it and through a Selenium-driven
  browser session where it doesn't (op.pl has no usable SMTP). Knows
  nothing about campaigns, AI, or scheduling — see its README for why
  that split exists.

## Stack

Python 3.11+/3.13, FastAPI, PostgreSQL + SQLAlchemy + Alembic, OpenAI
Assistants API, IMAP/SMTP, Selenium, JWT auth (PyJWT), Pydantic.

## Services

- [`backend/README.md`](backend/README.md) — campaigns, B2B objects, auth, full API reference
- [`sender/README.md`](sender/README.md) — delivery service, SMTP/Selenium providers
