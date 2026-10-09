# FoodLens build plan

Follows Section 12 of the handoff. Section 12 step 1 ("confirm scope") is a gate before Phase 0, not a build phase. Section 12 step 8 is split into Phase 6 (supplier discovery) and Phase 7 (order requests), giving phases 0–9.

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

## Phase 3 — Credential record display

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
- [ ] Test: contact detail edit writes an audit entry with actor and time
- [ ] Test: published product fields cannot be edited directly (only via change notice, Phase 5)
- [ ] Test: company user cannot approve own company, location, or credential
- [ ] Test: client cannot set status, reviewer, or ownership fields on any create/update
- [ ] Test: member cannot edit another company's products, batches, or locations
- [ ] Test: unapproved company cannot publish products to lookups or the directory
- [x] ~~Test: company cannot publish its own product~~ (superseded by D61: approved companies publish directly; pending companies cannot)
- [ ] Test: admin decisions record reviewer and timestamp

**Progress (2026-10-08)**
- Done: company registration (`PENDING_REVIEW` + owner), admin approve/reject/suspend with reviewer, time, note, and audit; supplier locations (pending until admin review, only for approved companies); company dashboard and admin review screens.
- Tested so far: company cannot approve itself or its locations; admin cannot review a company they belong to; client cannot set review/ownership fields on company or location create; member cannot add locations to another company; decisions record reviewer and time.
- Done (2026-10-09): products and batches published directly by approved companies (D61); credential claims reviewed by admins before they reach lookups (D63); owner shown as directory contact (D65).
- Dropped as over-engineering (D64): extra representatives, product-approval flow, supplier detail page.
- Remaining: contact-detail edits with audit (optional).

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
- [ ] Test: only wholesaler-capable users reach buyer screens (directory itself is public, D58; applies to ordering in Phase 7)

---

## Phase 7 — Order requests

**Goal:** Wholesalers send order requests; sellers respond; fulfilment can record batches.

**Deliverables**
- Order status lifecycle service (see `docs/DECISIONS.md`)
- Seller accept/decline/reply; buyer cancel before acceptance
- Batch allocation at fulfilment
- Buyer and seller order screens

**Done when**
- [ ] Test: buyer can order only approved products from approved sellers (buyer companies need no approval)
- [ ] Test: only the seller company can accept/decline; only the buyer company can cancel
- [ ] Test: invalid status transitions rejected
- [ ] Test: allocated batch must belong to the order line's product
- [ ] Test: no payment fields exist in models or schemas

---

## Phase 8 — Optional: concern reports and scan analytics

**Goal:** If time allows, consumers can privately report a concern; anonymized scan stats if approved.

**Deliverables**
- `CONCERN_REPORT` with product/batch snapshots, optional contact, optional photo, private admin queue
- Optional anonymized `BATCH_SCAN` (no user/IP link)

**Done when**
- [ ] Test: reports never exposed via public endpoints
- [ ] Test: report wording never states it reached a regulator
- [ ] Test: scan log stores no personal identifiers
- [ ] Retention/deletion rule documented

---

## Phase 9 — Evaluation and documentation

**Goal:** Evidence the prototype works and is understood; capstone-ready docs.

**Deliverables**
- End-to-end smoke tests for the four main workflows
- Usability study script, consent form, and task list (lookup, interpret result, find supplier, place order request)
- Measures: completion, errors, time, comprehension of demo-data limitation
- Schema/migration docs, demo script, final README

**Done when**
- [ ] All backend and frontend tests pass
- [ ] Study materials approved by supervisor before any participant session
- [ ] Docs let a reader install, seed, run, and test from a clean clone
