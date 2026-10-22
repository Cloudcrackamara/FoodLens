# FoodLens: Claude Code instructions

## Build target

FoodLens is a startup product at the demonstration-prototype stage. Its first milestone is the founder's capstone. Build a responsive FoodLens prototype: a unit-level product integrity platform.

- **Manufacturers** get a unique, unpredictable QR identity for every product unit and every carton. They print the QR, with the code underneath as a typing fallback, on packs.
- **Distributors and retailers** record what happens to units. They use either:
  - a mobile merchant page;
  - a signed POS integration, which records a sale only after payment is confirmed.
- **Consumers** check any pack for free, with no login, at `/check` or `/p/{token}`.
- **Intelligence:** FoodLens combines identities, lifecycle events, consumer scan patterns and the manufacturer's batch allocations (geo-batching) into explainable risk alerts. Manufacturers see these on their dashboard.

Consumer checks are the core asset. They must be fast, useful and possible only through FoodLens. FoodLens never claims that a physical item is the real product, and never makes regulator or product-safety claims.

Wholesale order requests remain in the code but are hidden and treated as future work (`ORDERS_ENABLED=false`).

Where to find things:
- **Product concept** (source of truth for scope): `docs/PRODUCT_INTEGRITY.md`.
- **Phase plan** (phases 1-10, one session and one commit each, then future work): `docs/PLAN.md`.
- **Schema:** the tables and rules are in `docs/SCHEMA.md`; the diagram is `docs/ERD.mmd`.
- **Decisions:** `docs/DECISIONS.md`. D104 onwards covers the unit-identity design, geo-batching and returns; D137 onwards is the final design and wins where earlier entries differ. Read the relevant entries before implementing identity, checks, lifecycle events, allocations, returns, POS, or risk rules.
- **Challenge log:** `docs/log.md`.
- **History only:** `docs/HANDOFF.md` and `docs/archive/` describe the earlier registration-lookup design.

## Non-negotiable rules

1. **Wording.**
   - **Words FoodLens never uses:** in its own wording, FoodLens never uses "original", "genuine", "authentic", "safe", "unsafe", "fake", "adulteration" or "verified by NAFDAC", and never gives a safety score.
   - **A recognised code:** it is described as issued by the manufacturer and recorded as in circulation, sold, and so on. Results state that no QR system catches every copied code.
   - **What a check proves:** help text says plainly that a copied QR carries the same code, and that FoodLens spots copies through sale status, places, scan volume and allocation, not by the QR alone.
   - **Recorded facts and possible patterns:** results label recorded facts as recorded facts and possible patterns as possible patterns.
   - **Company announcements and recalls:**
     - They may not contain the whole words "safe" or "unsafe".
     - They may not claim NAFDAC/SON approval, registration or certification.
     - They may warn about counterfeit products (D77, D86).
2. **The demo label is on every check.**
   - Every consumer check response includes `"data_mode": "DEMO"` and a disclaimer from the backend.
   - The frontend shows the banner **DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE** on every result.
   - Both layers enforce this. Neither relies on the other.
3. **Identities are random and stored only as hashes.**
   - QR tokens come from `secrets.token_bytes(16)`, encoded as 26 uppercase Crockford Base32 characters with no padding.
   - They are never derived from IDs, sequences or timestamps.
   - Typed codes are normalised before hashing: uppercase, spaces and hyphens removed, `O` read as `0`, `I` and `L` read as `1`.
   - Only the SHA-256 hash of the normalised token is stored.
   - Raw codes exist only in the one-time label download.
   - Public pages and responses never show internal identifiers (`unit_id` or other UUIDs). A result page shows only the last 4 characters of the code.
   - `product.registration_number` is product information only. It is never checked against a register.
4. **Only authorised commercial workflows change lifecycle status.** These are the manufacturer, the merchant page, and signed POS calls.
   - A consumer check never changes `lifecycle_status` or sale status.
   - `SALE_CORRECTED` keeps the original sale.
   - **RETURNED:**
     - Accepted only from the company that recorded the sale, or from that retailer's linked POS partner.
     - Puts the unit back `IN_STOCK` and clears the sold state, so the next check shows "In circulation, not yet sold".
     - The original SOLD event always stays, and risk rules ignore a sale that a valid return followed (D140).
   - `VOIDED` is allowed only before release.
5. **No self-approval.**
   - Company users never approve their own company profile, supplier locations, or change notices. (Exception, D61: approved manufacturers publish their own new products and batches directly.)
   - Only platform admins review.
   - Approval means "reviewed for the FoodLens demonstration database" only. It is never NAFDAC or SON approval.
6. **Change notices need admin approval.**
   - Changes to published product details (including size, attributes, GTIN and registration number), to batches, or to reviewed locations go through a change notice with structured current and proposed values.
   - While a notice is `PENDING_REVIEW` or `CLARIFICATION_REQUESTED`, published data stays unchanged.
   - Only approval applies the change. It records the old value, new value, approver and time.
   - **Exception: announcements and recalls.** Approved companies post them live without review.
     - They are labelled "Message from the company — not reviewed by FoodLens".
     - They never edit product data.
     - Admins can hide them; hiding a recall needs a reason.
   - Company contact details and private account settings are edited directly, and each edit is logged with actor and time.
7. **No payment data.**
   - POS calls carry an opaque `payment_reference` and a transaction ID only.
   - FoodLens stores no amounts, card details, customer data or checkout.
   - Orders, while hidden, remain requests only.
8. **Server-side authorization.**
   - Every protected route checks role and company ownership on the server.
   - Every POS route checks the API key, the HMAC signature, the timestamp, and the partner-retailer link.
   - Hiding a button in the frontend is never the control.
9. **Consumer privacy.**
   - Consumers stay anonymous.
   - A scan stores a coarse city/state derived from the IP, then the IP is discarded.
   - No GPS, cookies, device IDs or accounts.
   - Scan logs are deleted after 12 months.
   - QR decoding runs only in the browser. Images never leave the phone.
10. **Fictional seed data.**
    - All companies, products, POS partners and contacts are obviously fictional.
    - Reference numbers are prefixed `DEMO-`.
    - No real regulator logos are used.

## Stack

- **Backend:** Python 3.12, FastAPI, SQLModel (sync sessions), Alembic, PostgreSQL, and pytest, managed with `uv`. Ruff for lint and format.
- **Frontend:** Next.js (App Router), TypeScript, Tailwind, TanStack Query and Zod. Vitest and Testing Library for tests.
- **Infra:** Docker Compose for Postgres (later the API and web too). A named Cloudflare Tunnel serves the domain set in `PUBLIC_BASE_URL` (planned: `foodlens.online`).
- **Auth:**
  - FastAPI-issued httpOnly cookie session, with bcrypt password hashing.
  - Next.js `rewrites` proxy `/api/*` to FastAPI so cookies are same-origin.
  - POS partners use an API key plus an HMAC-SHA256 signature instead.
- Tests run against a Postgres test database, not SQLite.

## Folder layout

```text
/backend
  app/
    main.py          FastAPI app factory
    core/            settings, db session, security, auth dependencies, rate limits
    models/          SQLModel table models
    schemas/         request/response models (no status/ownership fields on inputs)
    services/        business rules: identity, check, lifecycle, risk, POS, approval, ownership
    routers/         thin HTTP layer; calls services
    jobs/            scheduled commands (scan-log purge)
    seed.py          fictional demo scenario
  alembic/           migrations
  tests/
/frontend
  app/               Next.js App Router pages (/check, /p/[token], /merchant, /company, /admin, /demo/pos)
  components/
  lib/               typed API client, Zod schemas, query hooks, QR reader
  server.mjs         custom server: replaces X-Forwarded-For with the real client IP (D45, D90)
/docs                product concept, PLAN, DECISIONS, SCHEMA, ERD, POS_INTEGRATION, log
/scripts             dev.mjs: start DB, migrate, seed, API and web app in one command
docker-compose.yml
```

## Commands

```bash
# Everything at once (from the repo root): DB, migrations, seed, API, web app
node scripts/dev.mjs

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

- Work one phase at a time. Start the next phase only when I ask.
- These are out of scope: payments, regulator scraping, AI safety scores, ratings and maps. Risk rules stay deterministic and explainable.
- Business rules live in backend service modules, not in routers or React components.
- Client input never sets any of the following:
  - `is_admin`, approval or review status, or lifecycle status;
  - alert status, except through the alert workflow;
  - hashes or ownership fields.
- Write tests for each rule you implement, and run them before saying a phase is done.
- Ask me before changing any of these:
  - business rules;
  - privacy behaviour;
  - risk thresholds' defaults;
  - user-facing wording about regulators, safety, or what a check proves.
- Keep the `README.md` install/run/test/seed/migrate instructions and the demo codes and logins current.
- Schema changes go through an Alembic migration:
  - Read the generated file before applying it.
  - Keep `docs/SCHEMA.md` and `docs/ERD.mmd` in step.
  - `uv run alembic check` must pass.
- Never commit secrets. Use environment variables and keep each `.env.example` up to date. The secrets include `POS_SECRET_KEY`.
- Log every real challenge in `docs/log.md` as it happens: an error, a blocker, a conflicting requirement, or surprising tool behaviour.
  - Each entry has a date section, area, challenge, cause, resolution and status.
  - Add it in the same task, not later.
