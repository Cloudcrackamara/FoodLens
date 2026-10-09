# FoodLens

Software engineering capstone prototype. Consumers look up **simulated** product and batch records; companies manage demo-reviewed catalogue data; wholesalers find demo-reviewed suppliers and send order requests.

> **DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE.** All companies, products, and credentials are fictional. A lookup is not a laboratory test, not a safety guarantee, and not a NAFDAC or SON decision.

Project docs: [`docs/HANDOFF.md`](docs/HANDOFF.md) (brief), [`docs/PLAN.md`](docs/PLAN.md) (phases), [`docs/DECISIONS.md`](docs/DECISIONS.md), [`docs/ERD.mmd`](docs/ERD.mmd) (draft data model).

## Layout

```text
backend/    FastAPI + SQLModel + Alembic (Python 3.12, uv)
frontend/   Next.js App Router + TypeScript + Tailwind
docs/       brief, plan, decisions, ERD
docker/     Postgres init scripts
docker-compose.yml
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (installs Python 3.12 automatically)
- Node.js 24 and npm
- Docker Desktop (running)

## First-time setup

```bash
cp .env.example .env                       # optional: override DB defaults
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local

docker compose up -d db                    # Postgres 16 on localhost:5433 (dev + foodlens_test DBs)
                                           # 5433, not 5432, avoids clashing with a locally installed PostgreSQL

cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.seed                  # seed admin (if SEED_ADMIN_* set) and demo data

cd ../frontend
npm install
```

## Run

```bash
# Terminal 1 — API on http://localhost:8000 (docs at /docs)
cd backend && uv run fastapi dev app/main.py

# Terminal 2 — web app on http://localhost:3000 (proxies /api/* to the API)
cd frontend && npm run dev
```

Check: `http://localhost:3000/api/health` returns `{"status":"ok"}`.

`npm run dev` and `npm run start` run `frontend/server.mjs`, a small custom Next.js server that replaces any client-supplied `X-Forwarded-For` with the real connection address so rate limits cannot be dodged (D45). It listens on all interfaces, so other devices on the same network can open `http://<this-computer's-IP>:3000` during usability tests.

## Demo lookups

Open `http://localhost:3000/check` (no account needed) after running the seed. Each row is tested automatically (`backend/app/demo_data.py` `SEED_CASES`):

| Case | Product code | Batch number | Result |
|---|---|---|---|
| Active NAFDAC and SON credentials | `DEMO-PC-0001` | `DEMO-LOT-101` | `DEMO_RECORD_FOUND` |
| Second product, active credential | `DEMO-PC-0002` | `DEMO-LOT-201` | `DEMO_RECORD_FOUND` |
| Batch number not in demo data | `DEMO-PC-0001` | `DEMO-LOT-999` | `BATCH_NOT_FOUND` |
| Batch awaiting review is hidden | `DEMO-PC-0001` | `DEMO-LOT-102` | `BATCH_NOT_FOUND` |
| Draft product is hidden | `DEMO-PC-0007` | `DEMO-LOT-701` | `BATCH_NOT_FOUND` |
| Company awaiting review is hidden | `DEMO-PC-0008` | `DEMO-LOT-801` | `BATCH_NOT_FOUND` |
| Batch expiry date has passed | `DEMO-PC-0005` | `DEMO-LOT-501` | `BATCH_EXPIRED` |
| Batch belongs to another product | `DEMO-PC-0001` | `DEMO-LOT-201` | `DETAILS_MISMATCH` |
| Product has no approved credential | `DEMO-PC-0006` | `DEMO-LOT-601` | `DETAILS_MISMATCH` |
| Credential expired | `DEMO-PC-0003` | `DEMO-LOT-301` | `CREDENTIAL_EXPIRED_OR_INACTIVE` |
| Credential inactive | `DEMO-PC-0004` | `DEMO-LOT-401` | `CREDENTIAL_EXPIRED_OR_INACTIVE` |
| Batch number on two products, no product code | `(blank)` | `DEMO-LOT-001` | `INSUFFICIENT_OR_AMBIGUOUS` |
| Nothing entered | `(blank)` | `(blank)` | `INSUFFICIENT_OR_AMBIGUOUS` |

All companies, products, and credentials are fictional; agencies are labelled "(simulated)". Every lookup is logged anonymously in `batch_scan` (no IP, user, or device details).

## Accounts and the seed admin

- Sign in at `http://localhost:3000/login`; create an account at `/register`. Consumers do not need an account.
- Sessions are httpOnly cookies issued by the API (`/api/auth/register`, `/login`, `/logout`, `/me`). Logout revokes the session server-side.
- Admins cannot be created through the API. To create one, set these in `backend/.env` and run the seed:

```bash
SEED_ADMIN_EMAIL=admin@foodlens-demo.example
SEED_ADMIN_PASSWORD=<10+ characters, not reused anywhere>
```

```bash
cd backend && uv run python -m app.seed
```

Running the seed again is safe. If an account with that email already exists it is promoted to admin and its password is left unchanged.

## Companies, admin review, and the supplier directory

| Page | Who | What |
|---|---|---|
| `/suppliers` | Anyone | Approved companies with demo-reviewed locations, badge "FoodLens demo-reviewed profile" |
| `/company/register` | Signed-in user without a company | Registers a company (starts pending; you become owner) |
| `/company` | Company members | Review status, locations, products, batches, credential claims (once approved) |
| `/admin` | Admins (seed admin) | Approve, reject, or suspend companies; mark locations demo-reviewed; approve or reject credential claims |

Try the full flow: create an account at `/register`, register a company, sign in as the seed admin in another browser (or a private window) and approve it at `/admin`, add a location at `/company`, mark it demo-reviewed at `/admin`, then see it at `/suppliers`. Products and batches a company adds are searchable at `/check` immediately, but show "Details do not match" (no credential) until an admin approves a credential claim. A FoodLens demo review is never a NAFDAC or SON approval.

## Rate limits

Requests are limited per network (IP address); no cookies or identifiers are used. Defaults, all changeable in `backend/.env`:

| What | Default |
|---|---|
| Product lookups | burst of 20, then 1 per second (`RATE_LIMIT_LOOKUP_BURST`, `RATE_LIMIT_LOOKUP_REFILL_PER_SECOND`) |
| Login | 5 per minute per IP + email (`RATE_LIMIT_LOGIN_PER_MINUTE`) |
| Registration | 5 per hour per IP (`RATE_LIMIT_REGISTER_PER_HOUR`) |

For usability-test sessions, list the test machines' IPs or a range in `RATE_LIMIT_EXEMPT_IPS`, e.g. `192.168.1.20,192.168.1.0/24`, and restart the API. Over the limit the API returns 429 with `Retry-After`. See `docs/DECISIONS.md` D39–D45.

## Test and lint

```bash
# Backend (needs `docker compose up -d db`; tests rebuild the foodlens_test database from migrations)
cd backend
uv run pytest
uv run ruff check . && uv run ruff format --check .

# Frontend
cd frontend
npm test
npm run lint
npm run typecheck
```

## Database migrations

```bash
cd backend
uv run alembic upgrade head                                  # apply
uv run alembic revision --autogenerate -m "describe change"  # create after model changes
uv run alembic downgrade -1                                  # roll back one
uv run alembic check                                         # fails if models and migrations differ
```

Models must be imported in `backend/app/models/__init__.py` for autogenerate to see them. Table-by-table rules: [`docs/SCHEMA.md`](docs/SCHEMA.md).

## Reset the local database

This deletes all local data:

```bash
docker compose down -v && docker compose up -d db
```
