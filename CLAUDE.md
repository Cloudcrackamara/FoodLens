# FoodLens — Claude Code instructions

## Build target

Build a responsive, role-based FoodLens prototype where consumers can look up simulated product/batch/credential records, companies can manage reviewed catalogue data and submit change notices, and wholesalers can discover demo-reviewed suppliers and place traceable order requests—without making official certification or product-safety claims.

Product brief: `docs/HANDOFF.md`. Schema: `docs/SCHEMA.md` (tables and rules) and `docs/ERD.mmd` (diagram). Phase plan: `docs/PLAN.md`. Decisions (answered 2026-10-07): `docs/DECISIONS.md` — read it before implementing lookup, change notices, or announcements.
`docs/archive/ERD_v1_consumer_only.mmd` is superseded history; do not build from it.

## Non-negotiable rules

1. **No "safe" wording.** Never return or display "safe", "unsafe", "fake", "verified safe", or any safety/adulteration score. Lookups return one primary record state — `DEMO_RECORD_FOUND`, `BATCH_NOT_FOUND`, `BATCH_EXPIRED`, `DETAILS_MISMATCH`, `CREDENTIAL_EXPIRED_OR_INACTIVE`, or `INSUFFICIENT_OR_AMBIGUOUS` — plus a `warnings` list, using the precedence in `docs/DECISIONS.md` Q4.
2. **DEMO data_mode on every lookup.** Every lookup response includes `"data_mode": "DEMO"` and a disclaimer message from the backend. The frontend shows the banner **DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE** on every lookup result. Both layers enforce this; neither relies on the other.
3. **Product-level credentials.** Credentials (`CREDENTIAL_RECORD`) link to a product and a regulatory agency, separate from `PRODUCT_BATCH`. Never present a product credential as a batch-specific certificate or a batch test.
4. **No self-approval.** Company users can never approve or activate their own company profile, products (publishing), batches, supplier locations, credentials, or change notices. Only platform admins review. Approval means "reviewed for the FoodLens demonstration database" only — never NAFDAC or SON approval.
5. **Change notices need admin approval.** Changes to published product details, batches, credentials, or reviewed locations go through a change notice with structured current/proposed values. While `PENDING_REVIEW` or `CLARIFICATION_REQUESTED`, published data is unchanged. Only approval applies it, recording old value, new value, approver, and time. New batches and company-entered credentials stay pending and are invisible to consumer lookup until approved.
   - **Exception — product announcements ("POPs"):** approved companies may post pop-up announcements that go live without review. They are labelled "Message from the company — not reviewed by FoodLens", never change product data, and admins can hide them.
   - Company contact details and private account settings are edited directly but logged with actor and time.
6. **No payments.** Orders are requests only. No payment fields, providers, or checkout.
7. **Server-side authorization.** Every protected route checks the user's role and company ownership on the server. The frontend hiding a button is never the control.
8. **Fictional seed data.** All companies, products, credentials, and contacts are obviously fictional, reference numbers are prefixed `DEMO-`, agencies are labelled "(simulated)", and no real regulator logos are used.

## Stack

- **Backend:** Python 3.12, FastAPI, SQLModel (sync sessions), Alembic, PostgreSQL, pytest, managed with `uv`. Ruff for lint/format.
- **Frontend:** Next.js (App Router) + TypeScript + Tailwind + TanStack Query + Zod. Vitest + Testing Library for tests.
- **Infra:** Docker Compose for Postgres (later the API too).
- **Auth:** FastAPI-issued httpOnly cookie session; password hashing with bcrypt. Next.js `rewrites` proxy `/api/*` to FastAPI so cookies are same-origin.
- Tests run against a Postgres test database, not SQLite.

## Folder layout

```text
/backend
  app/
    main.py          FastAPI app factory
    core/            settings, db session, security, auth dependencies
    models/          SQLModel table models
    schemas/         request/response models (no status/ownership fields on inputs)
    services/        business rules: lookup, approval, ownership, order status
    routers/         thin HTTP layer; calls services
    seed.py          fictional demo data
  alembic/           migrations
  tests/
/frontend
  app/               Next.js App Router pages
  components/
  lib/               typed API client, Zod schemas, query hooks
/docs                handoff, PLAN.md, DECISIONS.md, schema docs
docker-compose.yml
```

## Commands

These exist after Phase 0.

```bash
# Database
docker compose up -d db

# Backend (run from /backend)
uv sync
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "describe change"
uv run python -m app.seed
uv run fastapi dev app/main.py
uv run pytest
uv run ruff check . && uv run ruff format --check .

# Frontend (run from /frontend)
npm install
npm run dev
npm run lint
npm run typecheck
npm test
```

## Working rules

- Work one phase at a time; never start the next phase unprompted.
- Never add payments, regulator scraping, AI safety scores, OCR, ratings or maps.
- Business rules live in backend service modules, not routers or React components.
- Every protected route checks role and company ownership server-side.
- Client input must never set is_admin, approval/review status, credential status, or ownership fields.
- Write tests for each rule you implement, and run them before saying a phase is done.
- Ask me before changing business rules, privacy behaviour, or any user-facing wording about regulators or safety.
- Keep `README.md` install/run/test/seed/migrate instructions current.
- Schema changes go through an Alembic migration; read the generated file before applying, and keep `docs/SCHEMA.md` and `docs/ERD.mmd` in step. `uv run alembic check` must pass.
- Never commit secrets; use environment variables and keep `.env.example` up to date.
