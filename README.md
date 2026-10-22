# FoodLens

FoodLens is a startup product at the demonstration-prototype stage; the founder's capstone is its first milestone. It is being rebuilt as a unit-level product integrity platform: every pack gets its own QR identity, shops record what happens to it, and consumers check it for free (`docs/PLAN.md`, final design in `docs/DECISIONS.md` D137–D147).

**Until Phase 1 lands, the sections below describe the code as it runs today:** consumers look up **simulated** product and batch records; companies manage demo-reviewed catalogue data; wholesalers find demo-reviewed suppliers and send order requests. Each phase updates the README for what it changes.

> **DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE.** All companies, products, and register records are fictional. A lookup is not a laboratory test, not a safety guarantee, and not a NAFDAC or SON decision.

Project docs: [`docs/PRODUCT_INTEGRITY.md`](docs/PRODUCT_INTEGRITY.md) (product concept), [`docs/PLAN.md`](docs/PLAN.md) (phases), [`docs/DECISIONS.md`](docs/DECISIONS.md), [`docs/SCHEMA.md`](docs/SCHEMA.md) and [`docs/ERD.mmd`](docs/ERD.mmd) (target data model), [`docs/log.md`](docs/log.md) (challenge log). [`docs/HANDOFF.md`](docs/HANDOFF.md) is history only.

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

## Start everything with one command

After first-time setup (dependencies installed, `backend/.env` created), run from the repo root:

```bash
node scripts/dev.mjs
```

It starts Postgres with Docker Compose and waits until it is healthy. Then it applies migrations, runs the seed, and starts the API (`http://localhost:8000`) and the web app (`http://localhost:3000`) with `[api]` / `[web]` log prefixes. It waits for both health checks and prints the URLs. Docker Desktop must be running, and ports 3000 and 8000 must be free.

Stop: press **Ctrl+C** to stop the API and web app. The database keeps its data and keeps running until `docker compose stop db`.

Sign-ins after seeding:

| Account | Email | Password |
|---|---|---|
| Admin | `SEED_ADMIN_EMAIL` in `backend/.env` | `SEED_ADMIN_PASSWORD` in `backend/.env` |
| Demo wholesaler (buyer) | `buyer@demo.foodlens.invalid` | `SEED_DEMO_PASSWORD` in `backend/.env` |
| Demo supplier (Demo Harvest Foods) | `seller@demo.foodlens.invalid` | `SEED_DEMO_PASSWORD` in `backend/.env` |

## Run (separate terminals)

```bash
# Terminal 1 — API on http://localhost:8000 (docs at /docs)
cd backend && uv run fastapi dev app/main.py

# Terminal 2 — web app on http://localhost:3000 (proxies /api/* to the API)
cd frontend && npm run dev
```

Check: `http://localhost:3000/api/health` returns `{"status":"ok"}`.

`npm run dev` and `npm run start` run `frontend/server.mjs`, a small custom Next.js server that replaces any client-supplied `X-Forwarded-For` with the real connection address so rate limits cannot be dodged (D45). It listens on all interfaces, so other devices on the same network can open `http://<this-computer's-IP>:3000` during usability tests.

## Scan a pack with the phone camera

On `/check`, tap **Scan pack**, fit the NAFDAC/SON number inside the box, and tap **Capture**; then do the same for the batch number or skip it. A confirm screen always shows what was read so you can correct it before the register is checked. Reading happens in the browser (Tesseract.js); no photo is uploaded or saved (D88-D94).

The OCR files (about 7 MB) are copied from `node_modules` to `frontend/public/ocr/` automatically before `npm run dev` and `npm run build` (or run `npm run ocr:assets`). The folder is git-ignored.

Phone cameras only work on HTTPS pages (or `localhost`), so a phone cannot scan at `http://<computer-IP>:3000`. Use a tunnel:

### Test on your phone (iPhone or Android) with a Cloudflare quick tunnel

1. Install cloudflared once: `winget install --id Cloudflare.cloudflared` (no Cloudflare account needed).
2. In `frontend/.env.local` add `TRUST_CLOUDFLARE_TUNNEL=true`, so rate limits see each visitor's own IP instead of the tunnel's (D90).
3. Start the API as usual, then the web app. A production build is faster on the phone:
   ```bash
   cd frontend && npm run build && npm run start
   ```
   (`npm run dev` also works through the tunnel; `*.trycloudflare.com` is allowed in `next.config.ts`.)
4. In a third terminal: `cloudflared tunnel --url http://localhost:3000`
5. Open the printed `https://<random-words>.trycloudflare.com/check` on the phone and allow the camera.

**Warning:** while the tunnel runs, anyone who has that URL can reach your local FoodLens. Use demo data only and stop the tunnel (Ctrl+C) when you finish. The URL changes every time.

Backup (no internet tunnel; not tested on an iPhone): create a local certificate with [mkcert](https://github.com/FiloSottile/mkcert) (`mkcert -install`, then `mkcert <computer-IP>`), put an HTTPS proxy in front of port 3000 (for example `npx local-ssl-proxy --source 3443 --target 3000 --cert <cert>.pem --key <key>.pem`), and install and fully trust mkcert's root certificate on the phone (iPhone: Settings > General > About > Certificate Trust Settings). Then open `https://<computer-IP>:3443/check`. Through this proxy all phones share one rate-limit bucket, so add the computer's IP to `RATE_LIMIT_EXEMPT_IPS` for the session.

To measure accuracy on real packs, use `docs/OCR_ACCURACY.md`.

## Demo lookups

Open `http://localhost:3000/check` (no account needed) after running the seed, or a link such as `/check?reg=DEMO-NAFDAC-0001&batch=DEMO-LOT-101`, which fills in and checks immediately. Each row is tested automatically (`backend/app/demo_data.py` `SEED_CASES`):

| Case | Registration number | Batch number | Result |
|---|---|---|---|
| Active record, batch belongs to that product | `DEMO-NAFDAC-0001` | `DEMO-LOT-101` | `REGISTERED_ACTIVE` |
| Active record, number only | `DEMO-NAFDAC-0002` | `(blank)` | `REGISTERED_ACTIVE` |
| Scanned text with a label | `NAFDAC Reg No: demo-nafdac-0001` | `(blank)` | `REGISTERED_ACTIVE` |
| Lot number shared by two products, resolved by the number | `DEMO-NAFDAC-0002` | `DEMO-LOT-001` | `REGISTERED_ACTIVE` |
| Batch not in the FoodLens catalogue | `DEMO-NAFDAC-0001` | `DEMO-LOT-999` | `REGISTERED_ACTIVE` + BATCH_NOT_IN_CATALOGUE |
| Batch expiry date has passed | `DEMO-NAFDAC-0005` | `DEMO-LOT-501` | `REGISTERED_ACTIVE` + BATCH_EXPIRED |
| Number not in the simulated register | `DEMO-NAFDAC-9999` | `(blank)` | `REGISTRATION_NOT_FOUND` |
| Registration expired | `DEMO-NAFDAC-0003` | `DEMO-LOT-301` | `REGISTRATION_EXPIRED_OR_INACTIVE` |
| SON registration inactive | `DEMO-MANCAP-0004` | `DEMO-LOT-401` | `REGISTRATION_EXPIRED_OR_INACTIVE` |
| Batch belongs to a product with a different number | `DEMO-NAFDAC-0001` | `DEMO-LOT-201` | `REGISTRATION_MISMATCH` |
| Number registered to another product and company | `DEMO-NAFDAC-0009` | `DEMO-LOT-601` | `REGISTRATION_MISMATCH` |
| Nothing entered | `(blank)` | `(blank)` | `INSUFFICIENT_OR_AMBIGUOUS` |
| Batch number without a registration number | `(blank)` | `DEMO-LOT-101` | `INSUFFICIENT_OR_AMBIGUOUS` |

The register is a **simulated, fictional** NAFDAC/SON register held by FoodLens, not the regulators' own system; a match never proves a pack is the original. Every lookup is logged anonymously in `batch_scan` (no IP, user, or device details).

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
| `/company` | Company members | Review status, locations, products (with the registration number on the pack), batches, change notices with attachments, announcements (once approved) |
| `/admin` | Admins (seed admin) | Approve, reject, or suspend companies; mark locations demo-reviewed; approve, reject, or request clarification on change notices; hide announcements |

Try the full flow: create an account at `/register`, register a company, sign in as the seed admin in another browser (or a private window) and approve it at `/admin`, add a location at `/company`, mark it demo-reviewed at `/admin`, then see it at `/suppliers`. A company's products only show as registered at `/check` if their printed number matches an active record in the simulated register. A FoodLens demo review is never a NAFDAC or SON approval.

## Company contact details

On `/company` the company owner can edit the public contact email and phone. Changes apply at once (no review) and are recorded in the audit log with who made them and when (D103). Product and batch details can only be changed through a change notice.

## Wholesale order requests

Order requests are requests only: no prices or payments (D95-D101).

- `/suppliers`: search approved suppliers by name, area, or product, then open a supplier page. It shows the supplier's reviewed locations, contacts, and each published product's result in the simulated register (demo data).
- Members of approved wholesaler (or "manufacturer and wholesaler") companies see **Request an order** on a supplier page. They choose quantities, units, and pickup or delivery, then track requests at `/orders` and cancel while a request is still "Requested".
- Suppliers see **Incoming orders** at `/company`: Accept, Decline (optional reason), Reply, and Mark fulfilled, optionally linking their own batches to each line.

Demo accounts: set `SEED_DEMO_PASSWORD` in `backend/.env` (at least 10 characters) and run `uv run python -m app.seed`. Then sign in as `buyer@demo.foodlens.invalid` (Demo Market Traders) or `seller@demo.foodlens.invalid` (Demo Harvest Foods) with that password. The seed adds one order in each status. Without `SEED_DEMO_PASSWORD` these accounts cannot sign in.

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
