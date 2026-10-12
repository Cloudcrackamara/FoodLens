# FoodLens build plan

Follows Section 12 of the handoff. Section 12 step 1 ("confirm scope") is a gate before Phase 0, not a build phase. Section 12 step 8 is split into Phase 6 (supplier discovery) and Phase 7 (order requests). Re-ordered 2026-10-12 (D102): after Phase 7 come 8 Deployment and 9 Polish and evaluation; concern reports are deferred.

Every phase is done only when all tests listed under "Done when" exist and pass, existing tests still pass, docs are updated, and the student signs off. Do not start the next phase without being asked.

---

## Gate — Confirm scope

**Goal:** Supervisor approval of the simulated-data approach, roles, privacy defaults, and no-payment order requests.

**Deliverables:** Answers to the open questions in `docs/DECISIONS.md` recorded there.

**Done when**
- [x] Supervisor approved simulation, user roles, and no-payment scope
- [x] Pre-Phase-0 questions in `docs/DECISIONS.md` answered (2026-10-07)
- [ ] Remaining "Proposed" defaults in `docs/DECISIONS.md` accepted or amended

---

## Phase 0 — Foundation

**Goal:** A runnable empty monorepo with database, migrations, tests, and lint wired up.

**Deliverables**
- `/backend` uv project: FastAPI app factory, `GET /api/health`, env-based settings, sync SQLModel session, Alembic baseline migration, empty seed script, pytest config using a Postgres test DB, Ruff
- `/frontend` Next.js App Router + TS + Tailwind + TanStack Query + Zod; layout with the persistent demo-data banner; `/api` rewrite to FastAPI; ESLint, typecheck, Vitest
- `docker-compose.yml` with Postgres (dev + test databases)
- `.gitignore`, `.env.example`, `README.md` with install/run/test/seed/migrate steps

**Done when**
- [x] `docker compose up -d db` starts Postgres (host port 5433)
- [x] `uv run alembic upgrade head` succeeds on a fresh DB
- [x] `uv run pytest` passes (health route test)
- [x] `npm run lint`, `npm run typecheck`, `npm test` pass (banner renders test)
- [ ] No secrets committed; README steps work from a clean clone (verify after first commit)

Note: the pytest DB fixture was added in Phase 1 with the first models.

---

## Phase 1 — Data model

**Goal:** The full MVP schema exists in PostgreSQL, matches `docs/ERD.mmd`, and its database-level rules are tested.

**Deliverables**
- SQLModel tables for every MVP entity in `docs/ERD.mmd` (Phase 8 tables excluded): UUID keys, enum status fields, timestamps, shared review columns, `claimed_` company fields
- Migration `0002_initial_schema`, applied and reversible
- pytest fixtures that rebuild `foodlens_test` from migrations and roll back each test
- `docs/SCHEMA.md` describing each table

**Done when**
- [x] `uv run alembic upgrade head` and `downgrade` work; `alembic check` reports no drift
- [x] Test: `(product_id, batch_number)` unique; same batch number allowed on another product
- [x] Test: enum columns reject unknown values (e.g. `'SAFE'`)
- [x] Test: new records default to unreviewed states; `is_admin` defaults false; `data_mode` defaults `DEMO`
- [x] Test: change notice has exactly one existing target
- [x] Test: date-order, quantity, attachment-size, and buyer≠seller checks
- [x] Test: no payment/price columns exist
- [x] `docs/SCHEMA.md` written

---

## Phase 2 — Identity, roles, catalogue, and lookup

**Goal:** Users can sign in with roles enforced server-side, and consumers can look up a product code + batch number against seeded demo data and get a precise record state.

**Deliverables — identity and roles**
- Password hashing (bcrypt), `USER_SESSION` cookie sessions, `register` / `login` / `logout` / `me`
- Reusable dependencies: `current_user`, `require_admin`, `require_company_member(*roles)`
- Admin accounts created only by seed/CLI
- Frontend login/register pages and auth-aware nav

**Done when — identity and roles**
- [x] Test: register payload with `is_admin` / status fields is rejected or ignored
- [x] Test: unauthenticated request gets 401; wrong role gets 403
- [x] Test: member of company A cannot access company B routes
- [x] Test: passwords stored hashed, never returned
- [x] Test: inactive user cannot log in; revoked or expired session rejected
- [x] Test: wrong password rejected with a generic message; seed admin created from env, idempotent
- [x] Frontend: `/login` and `/register` pages, signed-in header; Vitest tests for validation, server errors, and payload

**Deliverables — catalogue and lookup**
- Seed: fictional products/batches incl. mismatch and not-found cases
- `services/lookup.py`: normalize input, find product, find approved batch, apply the precedence in `docs/DECISIONS.md` Q4, return primary state + `warnings`
- `POST /api/lookups/batch` with `data_mode: "DEMO"` and disclaimer on every response
- Attach the lookup rate limit (`Depends(limit_lookups)`, D40) and show the per-network 429 message on the result screen
- Frontend check form with value confirmation/correction and result screen with banner

**Done when — catalogue and lookup**
- [x] Test: known product + batch returns `DEMO_RECORD_FOUND` (credential checks included; see Phase 3)
- [x] Test: unknown batch returns `BATCH_NOT_FOUND` (no "fake"/"unsafe")
- [x] Test: product that is not `PUBLISHED` returns `BATCH_NOT_FOUND`
- [x] Test: batch belonging to a different product returns `DETAILS_MISMATCH` with differing field `product_code`
- [x] Test: batch past expiry date returns `BATCH_EXPIRED`
- [x] Test: pending or rejected batch returns `BATCH_NOT_FOUND`
- [x] Test: unidentifiable input returns `INSUFFICIENT_OR_AMBIGUOUS`
- [x] Test: every lookup response has `data_mode == "DEMO"`
- [x] Test: banned-words guard (no "safe"/"unsafe"/"fake") over all lookup messages, backend and frontend
- [x] Frontend test: banner shown on every result state
- [x] Seed covers every lookup state; each seed case tested through the API (`app/demo_data.py` `SEED_CASES`)
- [x] Anonymised `BATCH_SCAN` logged per lookup, no identifying columns (D46)

---

## Phase 3 — Credential record display (replaced 2026-10-09 by the simulated regulator register, D80-D87)

**Goal:** Lookup results show product-level credential provenance honestly.

**Deliverables**
- Seeded simulated agencies (NAFDAC simulated, SON/MANCAP simulated) and `DEMO-` references
- Status/expiry computation in a service; `CREDENTIAL_EXPIRED_OR_INACTIVE` state
- Result UI: agency, scheme, reference, status, dates, provenance, scope label

**Done when**
- [x] Test: expired/inactive credential returns `CREDENTIAL_EXPIRED_OR_INACTIVE`, worded as demo record status
- [x] Test: product with no approved credential returns `DETAILS_MISMATCH` with differing field `credential`
- [x] Test: pending company-entered credential is not shown in lookup
- [x] Test: expired batch + expired credential returns `BATCH_EXPIRED` with a credential warning
- [x] Test: expiry computed the same way in every response
- [x] Test: product-level credential is never labelled batch-level
- [x] Test: every credential carries `data_mode == "DEMO"`

Note: delivered together with the Phase 2 lookup (2026-10-08); expiry is computed by one function, `credential_status` in `backend/app/services/lookup.py`.

---

## Phase 4 — Company workflow

**Goal:** Companies register, get admin-reviewed, and manage their own catalogue and locations.

**Deliverables**
- Company registration → `PENDING_REVIEW`; admin approve/reject/suspend with reviewer + time
- Representative management within a company
- `SUPPLIER_LOCATION` with FoodLens review status and reviewer/time
- Company product drafts, new batches, and credential entry. Submitting a draft for publication sets `PENDING_REVIEW`; admin publishes or rejects. New batches and credentials `PENDING_REVIEW` until admin approves
- Direct edit of company contact details, logged in `AUDIT_LOG`
- Company dashboard and admin review queue screens

**Done when**
- [x] Test: credential claim invisible to lookup until admin approves (new batches now go live directly, D61)
- [x] Test: contact detail edit writes an audit entry with actor and time (`test_company_contact.py`, D103)
- [x] Test: published product fields cannot be edited directly (only via change notice, Phase 5): no PUT/PATCH/DELETE route on products or batches (`test_company_contact.py`)
- [x] Test: company user cannot approve own company, location, or credential (`test_company_cannot_approve_itself`, `test_company_cannot_mark_own_location_reviewed`; credentials removed, D80)
- [x] Test: client cannot set status, reviewer, or ownership fields on any create/update (company, location, product, contact, change notice, and order tests)
- [x] Test: member cannot edit another company's products, batches, or locations (`test_catalogue.py`, `test_member_cannot_add_location_to_another_company`, contact test)
- [x] Test: unapproved company cannot publish products to lookups or the directory (`test_pending_company_cannot_add_products`, `test_unapproved_companies_are_hidden_from_directory`)
- [x] ~~Test: company cannot publish its own product~~ (superseded by D61: approved companies publish directly; pending companies cannot)
- [x] Test: admin decisions record reviewer and timestamp (`test_admin_decision_records_reviewer_time_note_and_audit`)

**Progress (2026-10-08)**
- Done: company registration (`PENDING_REVIEW` + owner), admin approve/reject/suspend with reviewer, time, note, and audit; supplier locations (pending until admin review, only for approved companies); company dashboard and admin review screens.
- Tested so far: company cannot approve itself or its locations; admin cannot review a company they belong to; client cannot set review/ownership fields on company or location create; member cannot add locations to another company; decisions record reviewer and time.
- Done (2026-10-09): products and batches published directly by approved companies (D61); credential claims reviewed by admins before they reach lookups (D63); owner shown as directory contact (D65).
- Dropped as over-engineering (D64): extra representatives, product-approval flow, supplier detail page.
- Done (2026-10-12): owner edits company contact email and phone directly on `/company`, logged with actor, time, and old/new values (D103). Phase 4 complete.

---

## Phase 5 — Change notices

**Goal:** Companies propose catalogue changes that only take effect after admin approval, with full history, and can post pop-up product announcements.

**Deliverables**
- States: `PENDING_REVIEW`, `CLARIFICATION_REQUESTED`, `APPROVED`, `REJECTED`
- Upload validation (type, extension, size), private storage, safe filenames
- Admin field-by-field diff view and decision endpoint; approval validates and applies values, recording old/new value, approver, time
- Announcements: approved companies post instantly; shown as pop-up on lookup labelled "Message from the company — not reviewed by FoodLens"; admin can hide
- Company notice form and history; admin review screen

**Done when**
- [x] Test: pending or clarification-requested notice leaves published data unchanged
- [x] Test: approved notice updates the catalogue and records old value, new value, approver, time
- [x] Test: rejected notice changes nothing
- [x] Test: company response to clarification returns notice to `PENDING_REVIEW`
- [x] Test: submitter cannot approve own notice
- [x] Test: notice targeting another company's record is rejected
- [x] Test: disallowed file type/size rejected; attachments not publicly accessible
- [x] Test: announcement never changes product fields; hidden announcement not shown; only approved companies can post
- [x] Frontend test: announcement pop-up shows the "not reviewed by FoodLens" label

---

## Phase 6 — Supplier discovery

**Goal:** Wholesalers find approved suppliers and reviewed locations.

**Deliverables**
- `GET /api/suppliers` (public, with `q` search) showing only approved companies with reviewed locations; a separate detail endpoint was not needed, the list carries all public fields
- Supplier detail with reps/contact and what FoodLens reviewed
- Badge: "FoodLens demo-reviewed profile"
- Wholesaler search and detail screens

**Done when**
- [x] Test: pending/rejected/suspended companies and unreviewed locations never listed
- [x] Test: badge wording exact and never implies official certification
- [x] Test: only wholesaler-capable users reach buyer screens (directory itself is public, D58; order form and My orders only for approved wholesaler/both members, D95)

---

## Addition — Camera scanning (2026-10-12, D88-D94)

**Goal:** Consumers can fill the lookup by pointing the phone camera at the pack instead of typing.

**Done when**
- [x] "Scan pack" on `/check`: registration number, then optional batch number, then an editable confirm screen, then the normal lookup
- [x] OCR in the browser only, files self-hosted under `/ocr/`; no image uploaded, logged, or stored
- [x] Photo-picker fallback when the camera is unavailable; typing still works
- [x] Tests: extraction, image clean-up, engine paths, scan flow with OCR mocked, no image in any request
- [x] `server.mjs` trusts `CF-Connecting-IP` only from cloudflared when enabled (D90)
- [ ] Accuracy measured on about 20 real packs (`docs/OCR_ACCURACY.md`)

---

## Phase 7 — Wholesale order requests (2026-10-12, D95-D101)

**Goal:** Wholesalers find approved suppliers and send order requests; suppliers respond. Secondary, business side: kept minimal.

**Deliverables**
- Supplier search (name, area, or product) and a public supplier page: reviewed locations, owner contact, published products with their result in the simulated register (demo data)
- Order request from one supplier at a time: published products, positive quantity, unit; pickup from a reviewed location or delivery with details; no payment fields
- Seller on `/company`: accept, decline (optional reason), reply, mark fulfilled with optional batch links
- Status flow `REQUESTED -> ACCEPTED | DECLINED | CANCELLED`, `ACCEPTED -> FULFILLED`; buyer cancels only while requested
- Buyer "My orders" at `/orders`
- Seed: demo wholesaler, demo owner accounts (`SEED_DEMO_PASSWORD`), one order per status
- Migration `0005_order_requests`

**Done when**
- [x] Test: only the addressed seller can respond; buyer and outsiders cannot
- [x] Test: invalid transitions rejected (409); cancel only by the buyer and only while requested
- [x] Test: allocated batch must be the seller's own approved batch of the line's product
- [x] Test: unpublished products, non-positive quantities, mixed suppliers, self-orders rejected
- [x] Test: only approved wholesaler/both companies order; pending/suspended companies cannot place or receive orders
- [x] Test: only buyer and seller see an order (403 for non-members of the path company, 404 for other companies)
- [x] Test: client cannot set status, company IDs, user IDs, or seller notes
- [x] Test: no payment fields in tables or the order/supplier API
- [x] Test: supplier page shows each registration result with `data_mode` DEMO, never "safe"
- [x] Frontend tests: supplier page badges and banner, order form payload, buyer cancel, seller actions and batch allocation

---

## Phase 8 — Deployment (planned, not built)

**Goal:** A public demo reachable on the student's own domain without opening ports on the server.

**Deliverables**
- Cloud VM (small Linux instance) running Docker Compose: Postgres, the FastAPI API, and the Next.js web server (`npm run build && npm run start`)
- A named Cloudflare Tunnel (`cloudflared` container or service) routing the student's own domain to the web container; the VM has no inbound ports open except SSH
- `TRUST_CLOUDFLARE_TUNNEL=true` with `CLOUDFLARED_IPS` set to the cloudflared container's address (D90); the API trusts only the web container as proxy (`TRUSTED_PROXY_IPS`)
- Secrets from environment files on the VM, never in git; production settings (secure cookies, `BCRYPT_ROUNDS` default, seed admin and demo password from env)
- Database backups and a short runbook (deploy, migrate, seed, roll back)

**Done when**
- [ ] The demo opens over HTTPS on the domain and `/api/health` returns ok
- [ ] Rate limits see each visitor's own IP through the tunnel
- [ ] Camera scanning works on an iPhone and an Android phone over the domain
- [ ] A fresh VM can be set up from the runbook

---

## Phase 9 — Polish and evaluation

**Goal:** Evidence the prototype works and is understood; capstone-ready docs.

**Deliverables**
- Close the open Phase 0 and Phase 4 checklist items (clean-clone check, audit and ownership tests)
- Camera scanning accuracy on about 20 real packs (`docs/OCR_ACCURACY.md`)
- End-to-end smoke tests for the main workflows (lookup, scan, supplier search, order request)
- Usability study script, consent form, and task list (check a number, interpret the result, find a supplier, send an order request)
- Measures: completion, errors, time, comprehension of the demo-data limitation
- Demo script and final README

**Done when**
- [ ] All backend and frontend tests pass
- [ ] Study materials approved by supervisor before any participant session
- [ ] Docs let a reader install, seed, run, and test from a clean clone

---

## Deferred (not planned)

Concern reports (private consumer reports with an admin queue) and scan analytics were optional Phase 8 items. They are deferred by the 2026-10-12 re-ordering (D102) and will only be built if the student asks. The anonymised `batch_scan` log from Phase 2 stays.
