# FoodLens build plan: unit-level product integrity

Rewritten on 2026-10-21 for the scope change, and updated on 2026-10-22 for the final design: QR-only identity and advisory geo-batching (D137–D147 in `docs/DECISIONS.md`, which win over D104–D136 where they differ). The product concept is in `docs/PRODUCT_INTEGRITY.md`.

The earlier plan (Gate and Phases 0–7: foundation, auth, registration lookup, companies, change notices, supplier discovery, camera scanning, and order requests) was completed before this rewrite and is kept in git history (`git show 28d4fb6:docs/PLAN.md`). Its auth, company review, change notices, announcements, rate limits and Docker/test setup carry forward. The OCR stack does not (D147); it stays at tag `v1-registration-check`.

**Rules for every phase:**
- One session and one commit per phase.
- A phase is done only when all of these hold:
  - every test listed under "Done when" exists and passes;
  - the existing tests still pass;
  - lint and typecheck pass;
  - the docs are updated (SCHEMA, ERD, README, DECISIONS and log as relevant);
  - the founder signs off.
- Do not start the next phase unless asked.

---

## Phase 1: Data model and migrations

**Goal:** The new schema exists in PostgreSQL, the obsolete register, lookup and OCR are gone, and the database-level rules are tested.

**Deliverables**
- Migration `0006_unit_identity`:
  - company type flags, with data mapping (D105);
  - the `OWNER`/`STAFF` role (D106);
  - product `size`, `attributes` and `gtin` (D107);
  - `area` (seeded reference data), `carton` (with `carton_ref`, D139), `product_unit`, `lifecycle_event`, `scan_event`, `risk_alert` (with `batch_id`, D143);
  - `pos_partner`, `pos_partner_key`, `pos_partner_retailer`, `pos_till`;
  - `consumer_report`;
  - `batch_allocation`, `allocation_carton` and `allocation_unit` (D131, D142);
  - `rate_limit_daily` (D144);
  - announcement `kind`, `batch_id` and `recall_reason`.
- Migration `0007_drop_register`:
  - drop `regulator_register`, `regulatory_agency`, `batch_scan` and `product_batch.qr_token`;
  - add `product_batch.released_at`.
- Remove (D104):
  - backend `services/lookup.py`, `services/register.py`, `routers/lookups.py` and `SEED_CASES`;
  - the register part of `services/suppliers.py`;
  - the `LookupResult` and `RegisterStatus` enums;
  - frontend `components/lookup/*` and `lib/lookup.ts`;
  - tests `test_lookup.py`, `LookupForm.test.tsx` and `LookupResultView.test.tsx`, plus the register parts of `test_catalogue.py`, `test_schema.py`, `test_announcements.py` and `test_orders.py`;
  - the empty root file `new`.
- Remove the OCR stack (D147):
  - `lib/ocr/*` and its tests (including `extract.test.ts`);
  - the `tesseract.js` and `@tesseract.js-data/eng` dependencies;
  - the `ocr:assets`, `predev` and `prebuild` scripts and `scripts/copy-ocr-assets.mjs`;
  - the `/public/ocr/` line in `frontend/.gitignore`;
  - `docs/OCR_ACCURACY.md`, and the OCR section of the README.
- Retarget `test_rate_limit.py` to a stub check route.
- Hide orders behind `ORDERS_ENABLED` and rename the directory "Partner directory" (D127).
- Rework the company registration form for the type flags.
- The minimal seed (admin plus one approved manufacturer) still runs.
- `docs/SCHEMA.md` and `docs/ERD.mmd` match the models.

**Done when**
- [x] `alembic upgrade head`, `downgrade` to 0005 and `upgrade` again all work, and `alembic check` reports no drift.
- [x] Test: `qr_token_hash` is unique on units and on cartons; `carton_ref` is unique per batch.
- [x] Test: no `secret_code_hash`, `secret_claimed_*`, `return_disposition` or `WITHDRAWN` exists in the schema.
- [x] Test: the `scan_event` column list is exact (no IP, user agent, cookie, device or GPS column); `identifier_type` accepts only `QR` and `TYPED`.
- [x] Test: the `rate_limit_daily` column list is exact (area, day, bucket, count; no IP).
- [x] Test: a lifecycle event has exactly one of unit or carton; enums reject unknown values (e.g. `'GENUINE'`, `'CLAIMED'`).
- [x] Test: a company with no type flag set is rejected.
- [x] Test: the POS idempotency key is unique on (partner, transaction, unit, event type).
- [x] Test: allocation `quantity` > 0; a carton sits in at most one allocation; a unit sits in at most one allocation.
- [x] Test: no amount, price, card or customer columns exist anywhere.
- [x] Test: with `ORDERS_ENABLED=false`, the order routes return 404. The order tests pass with the flag on.
- [x] Test: no file under `frontend/` imports `tesseract.js`, and the dependency is absent from `package.json`.
- [x] Removed tests are deleted and the remaining backend and frontend suites are green.

---

## Phase 2: Unit and code generation, label export

**Goal:** An approved manufacturer's owner generates units and cartons for a batch, downloads the label file once, releases units, and can void unreleased ones.

**Deliverables**
- `services/identity.py` (D138):
  - QR tokens from `secrets.token_bytes(16)`, encoded as 26-character Crockford Base32;
  - normalisation (uppercase, no spaces or hyphens, `O`→`0`, `I`/`L`→`1`);
  - SHA-256 of the normalised token, with a retry on collision.
- `POST /api/companies/{id}/batches/{batch_id}/units`:
  - one transaction, at most 2,000 units, optional cartons with a `carton_ref`;
  - streams a zip with the label PDF (segno + fpdf2) and the printer CSV: batch, carton ref, token, verification URL (D139);
  - QR error correction level M; the token printed under the QR in groups of 4; a warning when the chosen QR size is below 15 mm.
- `ISSUED` events.
- Release per batch or per carton (`RELEASED` events).
- Void unreleased units with a reason, then regenerate (D110).
- Batch allocations (D131, D142): owners and staff split a generated batch by destination company and/or area, by carton list, by unit list or by quantity only, with a planned date.
- Company page: generate, the warning about the one-time file ("keep it secure and delete it after printing"), release, and void.

**Done when**
- [x] Test: tokens are 26 uppercase Crockford Base32 characters, unique, and a forced collision retries.
- [x] Test: normalisation maps lowercase, spaces, hyphens, `O`, `I` and `L` to the same hash as the clean token.
- [x] Test: raw tokens never appear in the database (whole-table scan after generation) or in the logs.
- [x] Test: the token does not depend on `unit_id` (no shared prefix or sequence across a batch).
- [x] Test: only the owner of an approved manufacturer can generate (staff and other companies get 403; a pending company gets 409).
- [x] Test: the zip contains the PDF and the CSV with the four columns; the PDF shows the token under each QR and the `PUBLIC_BASE_URL`; QR error correction is M.
- [x] Test: a QR size below 15 mm returns a warning.
- [x] Test: void works only before release (409 after), needs a reason, and records the actor and time.
- [x] Test: release writes the events and sets the status.
- [x] Test: allocations accept only the company's own batch, cartons and units; a carton or unit sits in at most one allocation; a unit whose carton is listed elsewhere is refused; the allocated total never exceeds the issued units; other companies get 403.

---

## Phase 3: Consumer check

**Goal:** Anyone can check a pack via `/check` (Scan QR or Type code) or `/p/{token}`, and gets the before/after-purchase message.

**Deliverables**
- `POST /api/check/qr` (scanned and typed codes, with `identifier_type`):
  - rate-limited (D119), with rate-limit hits counted by area and day (D144);
  - `data_mode` DEMO and a disclaimer on every response;
  - the results and precedence in D115, D116 and D141;
  - public fields only, no internal identifiers, and only the last 4 characters of the code (D138).
- Coarse area resolution, with the IP discarded straight after (D118).
- `POST /api/check/report` for consumer reports (D120).
- Frontend:
  - `/check`: Scan QR (a self-hosted reader) and Type code (normalised in the browser before sending).
  - `/p/[token]`: verifies by client POST only.
  - Result views for every result; "I've bought this"; Report a concern; the help text on copied codes (D141); the demo banner.
- Risk evaluation is left for Phase 6. Until then `SUSPICIOUS_ACTIVITY` comes only from existing alerts.

**Done when**
- [x] Test: each result is reachable, and the precedence order holds.
- [x] Test: the just-sold window boundary (exactly at the window is just-sold; one second older is previously-sold).
- [x] Test: a consumer check never changes `lifecycle_status` or sale status.
- [x] Test: a voided code or one from an unapproved manufacturer gives `INVALID_IDENTITY`; a carton token gives the carton message.
- [x] Test: an unknown typed code gives `INVALID_IDENTITY` with the neutral "We couldn't find that code…" copy.
- [x] Test: a returned unit gives `RECOGNISED_NOT_SOLD` ("In circulation, not yet sold").
- [x] Test: no response contains a `unit_id`, carton ID or other UUID, or more than the last 4 characters of the code.
- [x] Test: banned words (D128, D141) appear in no response or frontend copy; `data_mode` is DEMO and the disclaimer is always present.
- [x] Test: no IP, cookie or device data is stored; `Set-Cookie` is absent on check responses.
- [x] Test: the rate limit gives 429 with `Retry-After`, and increments `rate_limit_daily` for the area.
- [x] Frontend tests:
  - [x] the banner shows on every result;
  - [x] a typed code is normalised before the request;
  - [x] no image is sent in any request;
  - [x] `/p/[token]` makes no request until it mounts.

---

## Phase 4: Merchant page

**Goal:** Approved distributors and retailers record RECEIVED, TRANSFERRED, SOLD, RETURNED and SALE_CORRECTED from a phone, for a unit or a carton.

**Deliverables**
- `services/lifecycle.py`:
  - custody rules (D113);
  - status derivation by replay (D112);
  - the area taken from the company's reviewed location;
  - returns accepted only from the seller, always back to IN_STOCK (D140);
  - allocation matching (unit, then carton, then quantity) and the neutral "received outside its allocation" timeline note (D142).
- Merchant routes under `/api/companies/{id}/merchant/*`.
- `/merchant`:
  - mobile first;
  - QR scan (reusing the Phase 3 reader);
  - an event picker;
  - transfer target (approved companies);
  - correction reason.
- Staff management for the owner (D106).

**Done when**
- [ ] Test: a company can only record events for units it may hold (D113), and the label for a receipt without a transfer is set.
- [ ] Test: a carton event applies to all of its units and shares a `group_id`.
- [ ] Test: SALE_CORRECTED needs a reason, keeps the original SOLD event, and puts the unit back IN_STOCK.
- [ ] Test: RETURNED is accepted only from the company that recorded the SOLD event (others get 403).
- [ ] Test: RETURNED sets IN_STOCK, clears `last_sold_*`, keeps the SOLD event in the timeline, and the next check shows "In circulation, not yet sold"; the unit can be sold again.
- [ ] Test: allocation matching follows the order unit, carton, quantity; quantity allocations count down per matched receipt.
- [ ] Test: a receipt that matches no allocation is noted in the timeline and raises no alert; a batch with no allocations gets no note.
- [ ] Test: transfer only to approved companies; recalled and voided units are refused.
- [ ] Test: cross-company access is blocked; unapproved companies are blocked; the client cannot set the status or holder.
- [ ] Test: the owner adds and deactivates staff; staff cannot manage staff.
- [ ] Frontend tests: event form payloads, and the carton confirmation.

---

## Phase 5: POS integration and simulated POS

**Goal:** POS partners record sales after payment through a signed API, and a simulated till demonstrates it.

**Deliverables**
- `/api/pos/v1/units/lookup`, `sales`, `refunds` and `voids` (D121).
- Admin:
  - partners (key and secret shown once; revoke keys);
  - retailer links;
  - tills.
- Per-partner rate limit (D119).
- `/demo/pos` behind `DEMO_POS_ENABLED` (D123).
- `docs/POS_INTEGRATION.md` with Python and JavaScript signing examples.

**Done when**
- [ ] Test: unsigned, badly signed, wrong-key and revoked-key requests are rejected; a timestamp more than 300 s off either way is rejected.
- [ ] Test: replaying a sale is idempotent (the same response, no new events).
- [ ] Test: a late offline sale (an earlier `occurred_at`) is accepted and the status replays correctly; events older than the maximum age are rejected.
- [ ] Test: a refund creates RETURNED and puts the unit back IN_STOCK, only for a sale recorded by a retailer linked to this partner; a void creates SALE_CORRECTED with a reason.
- [ ] Test: lookup never changes any row, and returns no internal identifiers.
- [ ] Test: an unlinked or unapproved retailer, and an unregistered till, are rejected.
- [ ] Test: a sale returns a per-unit error list for sold, recalled, voided or unreleased units.
- [ ] Test: no payment data is stored beyond `payment_reference`; the signing secret is stored encrypted, never in plain text.
- [ ] Test: the per-partner rate limit.
- [ ] The signing examples in `POS_INTEGRATION.md` are run against the test API.

---

## Phase 6: Risk rules and alerts

**Goal:** The nine deterministic rules (D143) raise explainable alerts, and consumer results reflect them (D116).

**Deliverables**
- `services/risk.py`, called from checks, merchant events and POS calls.
- Env thresholds, including `ALLOCATION_OVERAGE_PCT` (default 10).
- De-duplication: per (rule, unit), and per (rule, batch, area) for rule 9.
- Evidence snapshot and explanation.
- The alert workflow (D125).

**Done when**
- [ ] Test: each of the nine rules fires on its scenario, at its level, with evidence and a plain-words explanation.
- [ ] Test: rule 1 is LOW alone and MEDIUM when the unit has another open alert or another rule fires on the same event.
- [ ] Test: rule 9 fires when distinct units observed in an area exceed the allocation by more than `ALLOCATION_OVERAGE_PCT`, counts units allocated elsewhere, treats an unallocated area of an allocated batch as 0, and skips a batch with no allocations.
- [ ] Test: rule 9 never changes the consumer result and is visible only to the manufacturer and admins.
- [ ] Test: a sale followed by a valid return is ignored by every rule; a returned unit's later sale and checks raise no alert.
- [ ] Test: no alert for a buyer rescan (same area, within the window), a return, a void correction, a carton move, or a receipt outside its allocation.
- [ ] Test: only MEDIUM and HIGH open alerts (excluding rule 9), and RESOLVED_SUSPECTED_COPY, switch the consumer result to SUSPICIOUS_ACTIVITY.
- [ ] Test: a second trigger appends to the open alert instead of duplicating it.
- [ ] Test: the evidence snapshot survives the scan purge.
- [ ] Test: alert status changes record the actor and time; another company cannot read or change them.

---

## Phase 7: Manufacturer and admin dashboards

**Goal:** Manufacturers see and act on their identity, lifecycle and alert data, and admins run the platform (D144).

**Deliverables**
- **Manufacturer:**
  - products and batches; generating units and labels;
  - batch allocations and the inventory view per destination: allocated, received, in stock, sold, returned (D142);
  - the unit timeline in plain words;
  - alerts with evidence, status and notes (including rule 9);
  - recalls and notices;
  - partners (derived from transfers and sales, plus POS links);
  - consumer reports.
- **Manufacturer stats:**
  - units issued and released;
  - sale coverage %;
  - POS versus merchant-page share;
  - checks by city and by week;
  - hot spots;
  - recall reach;
  - alerts raised and resolved;
  - time to resolve.
- **Admin:**
  - the approval queues (kept);
  - POS partners;
  - platform stats;
  - the automated-scanning panel: rate-limit hits and invalid-code bursts by area and day, no IPs;
  - consumer reports.
- **Recalls** (D126).

**Done when**
- [ ] Test: each stat is correct on a fixed dataset.
- [ ] Test: the inventory view counts are correct per destination, including a returned unit counted again as in stock.
- [ ] Test: the automated-scanning panel counts are correct per area and day, and the response holds no IP.
- [ ] Test: a manufacturer sees only its own units, alerts, reports and stats.
- [ ] Test: a recall writes RECALLED events for every affected unit; hiding a recall needs a reason.
- [ ] Frontend tests: the timeline wording, alert actions, and empty states.

---

## Phase 8: Seed scenario and full demo pass

**Goal:** One command produces the D145 scenario, and the whole story can be demonstrated on a phone.

**Done when**
- [ ] The seed is idempotent and built through the services; every batch is released except the labelled test carton.
- [ ] Demo codes are fixed 26-character tokens from `demo_data.py`, hashed like any other code (D111 exception).
- [ ] Cases (D145):
  - [ ] a batch allocated between Lagos and Kano;
  - [ ] loose units allocated individually to a Kano retailer;
  - [ ] one area exceeding its allocation (rule 9);
  - [ ] a POS sale then a buyer rescan (just sold, no alert);
  - [ ] sold in Lagos then scanned in Kano 3 hours later (alert);
  - [ ] a refund then a resale (no alert);
  - [ ] a recalled batch;
  - [ ] an invalid-code burst;
  - [ ] a voided code scan;
  - [ ] one deliberately unreleased carton;
  - [ ] never-sold units.
- [ ] Test: each scenario case gives its expected result and alert (and no alert where none is expected).
- [ ] Test: no scenario except the unreleased test carton gives `SUSPICIOUS_ACTIVITY` because of an unreleased unit.
- [ ] The README lists the demo codes, the logins (`SEED_DEMO_PASSWORD`) and a step-by-step demo script.
- [ ] A manual demo pass on a phone, recorded in `docs/log.md`.

---

## Phase 9: Deployment

**Goal:** A public demo on `foodlens.online`, with no inbound ports open on the server.

**Deliverables**
- A cloud VM running Docker Compose (Postgres, API and web), plus a daily purge job.
- A named Cloudflare Tunnel routing `foodlens.online` to the web container. The VM has no inbound ports except SSH.
- The D90 settings (`TRUST_CLOUDFLARE_TUNNEL`, `CLOUDFLARED_IPS`) and `TRUSTED_PROXY_IPS`.
- The Cloudflare "Add visitor location headers" managed transform switched on (D118).
- Secrets on the VM only: `POS_SECRET_KEY`, the seed passwords and secure cookies. `PUBLIC_BASE_URL=https://foodlens.online`.
- Backups and a runbook (deploy, migrate, seed, roll back, rotate secrets).

**Done when**
- [ ] The demo opens over HTTPS on the domain, and `/api/health` returns ok and reports that `cf-ipcity` is present.
- [ ] The rate limits see each visitor's own IP.
- [ ] A QR code printed with the production base URL opens `/p/{token}` from an iPhone and an Android camera.
- [ ] A fresh VM can be set up from the runbook.

---

## Phase 10: Evaluation and docs

**Goal:** Evidence that the prototype works and is understood; docs ready for the capstone, the first milestone.

**Deliverables**
- Label test (D146): QR read rate at 15, 20 and 25 mm on two phones, and typed-code entry errors (`docs/LABEL_TEST.md`).
- End-to-end smoke tests: issue, release, receive, POS sale, buyer check, a cloned-code check in another city, and resolving the alert.
- Detection and false-positive rates on the simulated clones, legitimate rescans and returns (concept doc §13).
- A usability study: script, consent and tasks (check before and after purchase, interpret a suspicious result, report a concern). Measures: completion, errors, time, and understanding of what a check does and does not prove.
- The final README and the demo script.

**Done when**
- [ ] All backend and frontend tests pass.
- [ ] The supervisor approves the study materials before any participant session.
- [ ] The docs let a reader install, seed, run and test from a clean clone.

---

## Future work

Not planned for the prototype (D146):
- Hidden scratch code and tamper-evident labels: the strongest anti-copy layer, deferred for simplicity.
- NFC tags.
- OCR of printed codes.
- Wholesale order requests (in the code, hidden by `ORDERS_ENABLED`).
- AI risk scoring.
- Consumer rewards (a phone number only if the consumer opts in).
- Results in local languages.
- Photo attachments on concern reports (the Report board has a photo step; the prototype sends text only, so nothing leaves the phone but the description).
