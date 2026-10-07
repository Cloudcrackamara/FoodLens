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
uv run python -m app.seed                  # fictional demo data (empty until Phase 1)

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
