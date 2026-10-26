# FoodLens

FoodLens is a startup product at the demonstration-prototype stage; the founder's capstone is its first milestone. It is being rebuilt as a unit-level product integrity platform: every pack gets its own QR identity, shops record what happens to it, and consumers check it for free (`docs/PLAN.md`, final design in `docs/DECISIONS.md` D137–D147).

**Status: Phases 1 to 3 are done.** The unit-identity schema exists (units, cartons, lifecycle events, scans, alerts, allocations, POS partners), and the old registration lookup, simulated register and OCR are removed. Manufacturers generate a QR code for every pack and carton, download the one-time label file, release, void and allocate stock (see [Pack codes and labels](#pack-codes-and-labels)). Anyone can check a pack for free at `/check` (Scan QR or Type code) or by opening the QR link `/p/{code}` (see [Consumer checks](#consumer-checks)). Companies register with type flags (manufacturer, distributor, retailer), manage demo-reviewed catalogue data and appear in the public partner directory. Each phase updates this README for what it changes.

> **DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE.** All companies, products and codes are fictional. A check is not a laboratory test and not a NAFDAC or SON decision, and no QR system catches every copied code.

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
| Demo distributor (Demo Market Traders) | `buyer@demo.foodlens.invalid` | `SEED_DEMO_PASSWORD` in `backend/.env` |
| Demo manufacturer (Demo Harvest Foods) | `seller@demo.foodlens.invalid` | `SEED_DEMO_PASSWORD` in `backend/.env` |

The seed creates fictional companies, products, batches and reviewed locations. Demo QR codes arrive with the full scenario in Phase 8 (D145).

## Run (separate terminals)

```bash
# Terminal 1 — API on http://localhost:8000 (docs at /docs)
cd backend && uv run fastapi dev app/main.py

# Terminal 2 — web app on http://localhost:3000 (proxies /api/* to the API)
cd frontend && npm run dev
```

Check: `http://localhost:3000/api/health` returns `{"status":"ok"}`.

`npm run dev` and `npm run start` run `frontend/server.mjs`, a small custom Next.js server that replaces any client-supplied `X-Forwarded-For` with the real connection address so rate limits cannot be dodged (D45). It listens on all interfaces, so other devices on the same network can open `http://<this-computer's-IP>:3000` during usability tests.

## Test on a phone

Phone cameras only work on HTTPS pages (or `localhost`), so a phone cannot use the camera at `http://<computer-IP>:3000`. Use the tunnel below to try Scan QR at `/check` from a phone.

### Test on your phone (iPhone or Android) with a Cloudflare quick tunnel

1. Install cloudflared once: `winget install --id Cloudflare.cloudflared` (no Cloudflare account needed).
2. In `frontend/.env.local` add `TRUST_CLOUDFLARE_TUNNEL=true`, so rate limits see each visitor's own IP instead of the tunnel's (D90).
3. Start the API as usual, then the web app. A production build is faster on the phone:
   ```bash
   cd frontend && npm run build && npm run start
   ```
   (`npm run dev` also works through the tunnel; `*.trycloudflare.com` is allowed in `next.config.ts`.)
4. In a third terminal: `cloudflared tunnel --url http://localhost:3000`
5. Open the printed `https://<random-words>.trycloudflare.com/` on the phone.

**Warning:** while the tunnel runs, anyone who has that URL can reach your local FoodLens. Use demo data only and stop the tunnel (Ctrl+C) when you finish. The URL changes every time.

Backup (no internet tunnel; not tested on an iPhone): create a local certificate with [mkcert](https://github.com/FiloSottile/mkcert) (`mkcert -install`, then `mkcert <computer-IP>`), put an HTTPS proxy in front of port 3000 (for example `npx local-ssl-proxy --source 3443 --target 3000 --cert <cert>.pem --key <key>.pem`), and install and fully trust mkcert's root certificate on the phone (iPhone: Settings > General > About > Certificate Trust Settings). Then open `https://<computer-IP>:3443/check`. Through this proxy all phones share one rate-limit bucket, so add the computer's IP to `RATE_LIMIT_EXEMPT_IPS` for the session.

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

## Pack codes and labels

On `/company`, each batch has a **Codes, labels and allocations** link (`/company/batches/<batch>`). The company must be an approved manufacturer.

| Action | Who | What happens |
|---|---|---|
| Generate and download labels | Owner | Up to 2,000 packs per request, optionally in cartons of N. Each pack and carton gets a random 26-character code (128 bits, Crockford Base32). FoodLens stores only the SHA-256 hash of each code and records an `ISSUED` event. The browser downloads a zip once: `labels.pdf`, `units.csv`, `cartons.csv` (columns `batch, carton_ref, token, verification_url`) and `READ-ME-FIRST.txt`. |
| Release | Owner or staff | The whole batch or one carton moves from "Not released" to "Released" (`RELEASED` events). |
| Void | Owner | Only before release, with a reason: the whole batch's unreleased packs, listed cartons, or single codes pasted from the CSV. Voided codes stop working; generate new ones to replace them. Released packs need a recall instead. |
| Allocate | Owner or staff | Plan where stock goes: an area, optionally an approved distributor or retailer, by quantity, cartons or single codes. |

Each QR encodes `{PUBLIC_BASE_URL}/p/{code}` with error correction level M and a 4-module quiet zone. The code is printed under it in groups of 4, with "Type the code at <host>/check". QR sizes below 15 mm are allowed with a warning. The page footer names the base URL used. **Set `PUBLIC_BASE_URL` in `backend/.env` before printing real labels: printed codes cannot change.**

**The label file holds every raw code and cannot be downloaded again.** Keep it secure, send it only to the printer, and delete every copy after printing. A full 2,000-pack file takes about 15 seconds to build.

## Companies, admin review, and the partner directory

| Page | Who | What |
|---|---|---|
| `/suppliers` | Anyone | Partner directory: approved companies with demo-reviewed locations, badge "FoodLens demo-reviewed profile" |
| `/company/register` | Signed-in user without a company | Registers a company as manufacturer, distributor and/or retailer (at least one; starts pending; you become owner) |
| `/company` | Company members | Review status, locations, products (manufacturers only, with the NAFDAC number as printed), batches, change notices with attachments, announcements (once approved) |
| `/admin` | Admins (seed admin) | Approve, reject, or suspend companies; mark locations demo-reviewed; approve, reject, or request clarification on change notices; hide announcements |

Try the full flow: create an account at `/register`, register a company, sign in as the seed admin in another browser (or a private window) and approve it at `/admin`, add a location at `/company`, mark it demo-reviewed at `/admin`, then see it at `/suppliers`. The NAFDAC number on a product is shown as printed, as information only; FoodLens never checks it against any register. A FoodLens demo review is never a NAFDAC or SON approval.

## Consumer checks

No account and no cookies. Every result carries `data_mode: "DEMO"` and the disclaimer from the API, and the page shows the **DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE** banner (D115, D141).

- `/check`: **Scan QR** reads the code with the phone camera, or from a photo when there is no camera. The reader runs in the browser (the built-in `BarcodeDetector`, otherwise the bundled jsQR); no image is uploaded. **Type code** accepts the 26 characters printed under the QR, with spaces or dashes; O, I and L are read as 0, 1 and 1.
- `/p/{code}`: what any phone camera opens. The page records nothing on load; the browser checks the code with a `POST` after the page mounts, so link previews create no scan (D117).
- Results, first match wins: `INVALID_IDENTITY`, `SUSPICIOUS_ACTIVITY` (from existing alerts; risk rules arrive in Phase 6), `BATCH_OR_PRODUCT_WARNING` (recall), a carton QR gives `CARTON_CODE` ("check the individual pack"), then `RECOGNISED_JUST_SOLD` (sold within `JUST_SOLD_WINDOW_HOURS`, default 6), `RECOGNISED_PREVIOUSLY_SOLD` or `RECOGNISED_NOT_SOLD`. Only the last 4 characters of the code are shown, and responses contain no internal IDs.
- **I've bought this** (no sale recorded) shows a note and sends nothing. **Report a concern** sends an anonymous report to the manufacturer and admins (`POST /api/check/report`, 5 per hour per network).
- A check stores only the coarse area (city). With `SIMULATE_LOCATION_ENABLED=true` (demo only) a city chosen in the picker comes first (D148); otherwise the area comes from Cloudflare's location headers through a trusted tunnel, else the DB-IP Lite file at `GEOIP_DB_PATH`. The IP is discarded (D118). A check never changes a pack's status.

Demo codes to type arrive with the seed scenario in Phase 8 (D145). Until then, generate codes for a batch at `/company` and type one from the label file.

## Company contact details

On `/company` the company owner can edit the public contact email and phone. Changes apply at once (no review) and are recorded in the audit log with who made them and when (D103). Product and batch details can only be changed through a change notice.

## Wholesale order requests (hidden, future work)

Order requests are hidden future work (D127). They stay in the code, but the API registers the order routes only with `ORDERS_ENABLED=true` in `backend/.env`, and the web app shows them only with `NEXT_PUBLIC_ORDERS_ENABLED=true` in `frontend/.env.local`. Both default to `false`. They are requests only: no prices or payments (D95-D101).

- `/suppliers`: search approved partners by name, area, or product, then open a partner page. It shows reviewed locations, contacts, and each published product with its size and NAFDAC number as printed.
- With orders switched on, members of approved distributor companies see **Request an order** on a partner page. They choose quantities, units, and pickup or delivery, then track requests at `/orders` and cancel while a request is still "Requested".
- Suppliers see **Incoming orders** at `/company`: Accept, Decline (optional reason), Reply, and Mark fulfilled, optionally linking their own batches to each line.

Demo accounts: set `SEED_DEMO_PASSWORD` in `backend/.env` (at least 10 characters) and run `uv run python -m app.seed`. Then sign in as `buyer@demo.foodlens.invalid` (Demo Market Traders) or `seller@demo.foodlens.invalid` (Demo Harvest Foods) with that password. The seed adds one order in each status. Without `SEED_DEMO_PASSWORD` these accounts cannot sign in.

## Rate limits

Requests are limited per network (IP address); no cookies or identifiers are used. Defaults, all changeable in `backend/.env`:

| What | Default |
|---|---|
| Consumer checks | burst of 20, then 1 per second (`RATE_LIMIT_CHECK_BURST`, `RATE_LIMIT_CHECK_REFILL_PER_SECOND`) |
| Login | 5 per minute per IP + email (`RATE_LIMIT_LOGIN_PER_MINUTE`) |
| Registration | 5 per hour per IP (`RATE_LIMIT_REGISTER_PER_HOUR`) |
| Consumer concern reports | 5 per hour per IP (`RATE_LIMIT_REPORT_PER_HOUR`) |

For usability-test sessions, list the test machines' IPs or a range in `RATE_LIMIT_EXEMPT_IPS`, e.g. `192.168.1.20,192.168.1.0/24`, and restart the API. Over the limit the API returns 429 with `Retry-After`. Blocked checks and reports are also counted per city and day in `rate_limit_daily`, with no IP (D144). See `docs/DECISIONS.md` D39–D45.

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

Migration `0006_unit_identity` keeps existing data: `company_type` becomes the three type flags (MANUFACTURER becomes manufacturer, WHOLESALER becomes distributor, BOTH becomes both), `REPRESENTATIVE` members become `STAFF`, `package_size` is renamed `size`, and supplier locations get an `area_id` where their area names a seeded city. It also seeds the reference `area` table. Migration `0007_drop_register` drops the simulated register, the old lookup log and `product_batch.qr_token`; that data is not kept. Both migrations can be rolled back to `0005_order_requests`.

## Reset the local database

This deletes all local data:

```bash
docker compose down -v && docker compose up -d db
```
