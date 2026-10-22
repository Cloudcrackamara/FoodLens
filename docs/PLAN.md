# FoodLens build plan: unit-level product integrity

Rewritten on 2026-10-21 for the scope change: D104–D136 in `docs/DECISIONS.md`, and the product concept in `docs/PRODUCT_INTEGRITY.md`.

The earlier plan (Gate and Phases 0–7: foundation, auth, registration lookup, companies, change notices, supplier discovery, camera scanning, and order requests) was completed before this rewrite and is kept in git history (`git show 28d4fb6:docs/PLAN.md`). Its auth, company review, change notices, announcements, rate limits, OCR stack and Docker/test setup carry forward.

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

**Goal:** The new schema exists in PostgreSQL, the obsolete register and lookup are gone, and the database-level rules are tested.

**Deliverables**
- Migration `0006_unit_identity`:
  - company type flags, with data mapping (D105);
  - the `OWNER`/`STAFF` role (D106);
  - product `size`, `attributes` and `gtin` (D107);
  - `area` (seeded reference data), `carton`, `product_unit`, `lifecycle_event`, `scan_event`, `risk_alert`;
  - `pos_partner`, `pos_partner_key`, `pos_partner_retailer`, `pos_till`;
  - `consumer_report`;
  - `batch_allocation` and `allocation_carton` (D131);
  - `lifecycle_event.return_disposition` and lifecycle status `WITHDRAWN` (D134);
  - announcement `kind`, `batch_id` and `recall_reason`.
- Migration `0007_drop_register`:
  - drop `regulator_register`, `regulatory_agency`, `batch_scan` and `product_batch.qr_token`;
  - add `product_batch.released_at`.
- Remove (D104):
  - backend `services/lookup.py`, `services/register.py`, `routers/lookups.py` and `SEED_CASES`;
  - the register part of `services/suppliers.py`;
  - the `LookupResult` and `RegisterStatus` enums;
  - frontend `components/lookup/*` and `lib/lookup.ts`;
  - the NAFDAC/batch parsing in `lib/ocr/extract.ts` (a Crockford extractor replaces it in Phase 3);
  - tests `test_lookup.py`, `LookupForm.test.tsx`, `LookupResultView.test.tsx` and `extract.test.ts`, plus the register parts of `test_catalogue.py`, `test_schema.py`, `test_announcements.py` and `test_orders.py`;
  - the empty root file `new`.
- Retarget `test_rate_limit.py` to a stub check route.
- Hide orders behind `ORDERS_ENABLED` and rename the directory "Partner directory" (D127).
- Rework the company registration form for the type flags.
- The minimal seed (admin plus one approved manufacturer) still runs.
- `docs/SCHEMA.md` and `docs/ERD.mmd` match the models.

**Done when**
- [ ] `alembic upgrade head`, `downgrade` to 0005 and `upgrade` again all work, and `alembic check` reports no drift.
- [ ] Test: `qr_token_hash` and `secret_code_hash` are unique on units, and `qr_token_hash` is unique on cartons.
- [ ] Test: the `scan_event` column list is exact (no IP, user agent, cookie, device or GPS column).
- [ ] Test: a lifecycle event has exactly one of unit or carton; enums reject unknown values (e.g. `'GENUINE'`).
- [ ] Test: a company with no type flag set is rejected.
- [ ] Test: the POS idempotency key is unique on (partner, transaction, unit, event type).
- [ ] Test: allocation `quantity` > 0; an allocation carton is unique per allocation; `return_disposition` is required on RETURNED and absent on other events.
- [ ] Test: no amount, price, card or customer columns exist anywhere.
- [ ] Test: with `ORDERS_ENABLED=false`, the order routes return 404. The order tests pass with the flag on.
- [ ] Removed tests are deleted and the remaining backend and frontend suites are green.

---

## Phase 2: Unit and code generation, label export

**Goal:** An approved manufacturer's owner generates units and cartons for a batch, downloads the label file once, releases units, and can void unreleased ones.

**Deliverables**
- `services/identity.py`:
  - QR tokens (D108);
  - hidden codes with Luhn mod-32 (D109);
  - hashing with `CODE_HASH_PEPPER`;
  - retry on collision.
- `POST /api/companies/{id}/batches/{batch_id}/units`:
  - one transaction, at most 2,000 units, optional cartons;
  - streams a zip with the label PDF (segno + fpdf2) and the printer CSV (D110).
- `ISSUED` events.
- Release per batch or per carton (`RELEASED` events).
- Void unreleased units with a reason (D110).
- Batch allocations (D131): owners and staff split a generated batch by destination company and/or area, by quantity or by carton list, with a planned date.
- Company page: generate, the warning about the one-time file, release, and void.

**Done when**
- [ ] Test: tokens and codes are unique, and a forced collision retries.
- [ ] Test: raw codes never appear in the database (whole-table scan after generation) or in the logs.
- [ ] Test: the check character accepts valid codes, rejects every single-character change, and handles the O/I/L/lowercase tolerance.
- [ ] Test: the token does not depend on `unit_id` (no shared prefix or sequence across a batch).
- [ ] Test: only the owner of an approved manufacturer can generate (staff and other companies get 403; a pending company gets 409).
- [ ] Test: the zip contains the PDF and the CSV, and the PDF footer shows the `PUBLIC_BASE_URL`.
- [ ] Test: void works only before release (409 after), needs a reason, and records the actor and time.
- [ ] Test: release writes the events and sets the status.
- [ ] Test: allocations accept only the company's own batch and cartons, a carton sits in at most one allocation, and the allocated total never exceeds the issued units; other companies get 403.

---

## Phase 3: Consumer check

**Goal:** Anyone can check a pack via `/check` (QR, OCR of the hidden code, or typing) or `/p/{token}`, and gets the before/after-purchase message.

**Deliverables**
- `POST /api/check/qr` and `POST /api/check/secret`:
  - rate-limited (D119);
  - `data_mode` DEMO and a disclaimer on every response;
  - the results and precedence in D115 and D116.
- Hidden-code CLAIMED (D114).
- Coarse area resolution, with the IP discarded straight after (D118).
- `POST /api/check/report` for consumer reports (D120).
- Frontend:
  - `/check`: Scan QR (a self-hosted reader), Scan secret code (OCR retargeted to Crockford), and Type code. The check character is validated in the browser.
  - `/p/[token]`: verifies by client POST only.
  - Result views for every result; "I've bought this"; Report a concern; the demo banner.
- Risk evaluation is left for Phase 6. Until then `SUSPICIOUS_ACTIVITY` comes only from existing alerts.

**Done when**
- [ ] Test: each result is reachable, and the precedence order holds.
- [ ] Test: the just-sold window boundary (exactly at the window is just-sold; one second older is previously-sold).
- [ ] Test: a consumer check never changes `lifecycle_status` or sale status; CLAIMED sets only the claim fields.
- [ ] Test: CLAIMED is recorded on the first hidden-code check only.
- [ ] Test: a voided code or one from an unapproved manufacturer gives `INVALID_IDENTITY`; a carton token gives the carton message.
- [ ] Test: a restocked unit gives `RECOGNISED_NOT_SOLD` ("In circulation, not yet sold"); a withdrawn unit gives `RECOGNISED_WITHDRAWN` ("Returned to the shop and withdrawn from sale") (D135).
- [ ] Test: banned words (D128) appear in no response or frontend copy; `data_mode` is DEMO and the disclaimer is always present.
- [ ] Test: no IP, cookie or device data is stored; `Set-Cookie` is absent on check responses.
- [ ] Test: the rate limit gives 429 with `Retry-After`.
- [ ] Frontend tests:
  - [ ] the banner shows on every result;
  - [ ] an invalid check character is stopped before the API;
  - [ ] no image is sent in any request;
  - [ ] `/p/[token]` makes no request until it mounts.

---

## Phase 4: Merchant page

**Goal:** Approved distributors and retailers record RECEIVED, TRANSFERRED, SOLD, RETURNED (with a disposition) and SALE_CORRECTED from a phone, for a unit or a carton.

**Deliverables**
- `services/lifecycle.py`:
  - custody rules (D113);
  - status derivation by replay (D112);
  - the area taken from the company's reviewed location;
  - returns with a disposition, accepted only from the seller (D134);
  - the "received outside its allocation" timeline label (D132).
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
- [ ] Test: RESTOCK sets IN_STOCK, clears `last_sold_*`, keeps the SOLD event in the timeline, and the next check shows "not yet sold".
- [ ] Test: NOT_FOR_RESALE sets WITHDRAWN; a withdrawn unit cannot be sold, received or transferred again.
- [ ] Test: a unit whose hidden code was CLAIMED can only be returned NOT_FOR_RESALE (RESTOCK gets 409).
- [ ] Test: a receipt outside the allocation (company or area) is labelled in the timeline.
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
- [ ] Test: a refund creates RETURNED with the required disposition, only for a sale recorded by a retailer linked to this partner; a void creates SALE_CORRECTED with a reason.
- [ ] Test: lookup never changes any row.
- [ ] Test: an unlinked or unapproved retailer, and an unregistered till, are rejected.
- [ ] Test: a sale returns a per-unit error list for sold, recalled, voided or unreleased units.
- [ ] Test: no payment data is stored beyond `payment_reference`; the signing secret is stored encrypted, never in plain text.
- [ ] Test: the per-partner rate limit.
- [ ] The signing examples in `POS_INTEGRATION.md` are run against the test API.

---

## Phase 6: Risk rules and alerts

**Goal:** The eleven deterministic rules (D124, D132, D133) raise explainable alerts, and consumer results reflect them (D116).

**Deliverables**
- `services/risk.py`, called from checks, merchant events and POS calls.
- Env thresholds.
- De-duplication.
- Evidence snapshot and explanation.
- The alert workflow (D125).

**Done when**
- [ ] Test: each of the eleven rules fires on its scenario, at its level, with evidence and a plain-words explanation; rules 10 and 11 include the allocation in the evidence.
- [ ] Test: rule 11 is LOW alone and MEDIUM when combined with another signal on the same unit.
- [ ] Test: a sale followed by a valid return is ignored by every rule; a restocked unit's later sale and checks raise no alert.
- [ ] Test: no alert for a buyer rescan (same area, within the window), a return, a void correction, or a carton move.
- [ ] Test: only MEDIUM and HIGH open alerts (and RESOLVED_SUSPECTED_COPY) switch the consumer result to SUSPICIOUS_ACTIVITY.
- [ ] Test: a second trigger appends to the open alert instead of duplicating it.
- [ ] Test: the evidence snapshot survives the scan purge.
- [ ] Test: alert status changes record the actor and time; another company cannot read or change them.

---

## Phase 7: Manufacturer and admin dashboards

**Goal:** Manufacturers see and act on their identity, lifecycle and alert data, and admins run the platform.

**Deliverables**
- **Manufacturer:**
  - products and batches; generating units and labels;
  - the unit timeline in plain words;
  - alerts with evidence, status and notes;
  - recalls and notices;
  - partners (derived from transfers and sales, plus POS links);
  - consumer reports;
  - batch allocations and the inventory view per destination and area: allocated, received, in stock, sold, returned (D131).
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
  - invalid-burst alerts;
  - consumer reports.
- **Recalls** (D126).

**Done when**
- [ ] Test: each stat is correct on a fixed dataset.
- [ ] Test: the inventory view counts are correct per destination and area, including a restocked unit counted again as in stock.
- [ ] Test: a manufacturer sees only its own units, alerts, reports and stats.
- [ ] Test: a recall writes RECALLED events for every affected unit; hiding a recall needs a reason.
- [ ] Frontend tests: the timeline wording, alert actions, and empty states.

---

## Phase 8: Seed scenario and full demo pass

**Goal:** One command produces the D111 scenario, and the whole story can be demonstrated on a phone.

**Done when**
- [ ] The seed is idempotent and built through the services; every batch is released except the labelled test carton.
- [ ] Allocations (D136): one batch split between Lagos and Kano; one unit sold in Abuja (a retailer's reviewed Abuja location) triggers rule 11.
- [ ] Test: each scenario case gives its expected result and alert (and no alert where none is expected), including the rule 11 alerts on the existing Kano and Abuja scenarios.
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
- Secrets on the VM only: `CODE_HASH_PEPPER`, `POS_SECRET_KEY`, the seed passwords and secure cookies. `PUBLIC_BASE_URL=https://foodlens.online`.
- Backups and a runbook (deploy, migrate, seed, roll back, rotate secrets).

**Done when**
- [ ] The demo opens over HTTPS on the domain, and `/api/health` returns ok and reports that `cf-ipcity` is present.
- [ ] The rate limits see each visitor's own IP.
- [ ] A QR code printed with the production base URL opens `/p/{token}` from an iPhone and an Android camera.
- [ ] A fresh VM can be set up from the runbook.

---

## Phase 10: Evaluation and docs

**Goal:** Evidence that the prototype works and is understood; docs ready for the capstone.

**Deliverables**
- OCR accuracy on printed hidden codes (`docs/OCR_ACCURACY.md`, reworked).
- End-to-end smoke tests: issue, release, receive, POS sale, buyer check, a cloned-code check in another city, and resolving the alert.
- Detection and false-positive rates on the simulated clones, legitimate rescans and returns (concept doc §13).
- A usability study: script, consent and tasks (check before and after purchase, interpret a suspicious result, report a concern). Measures: completion, errors, time, and understanding of what a check does and does not prove.
- The final README and the demo script.

**Done when**
- [ ] All backend and frontend tests pass.
- [ ] The supervisor approves the study materials before any participant session.
- [ ] The docs let a reader install, seed, run and test from a clean clone.

---

## Phase 11: Stretch

Only after Phases 1–10:
- Opt-in simulated rewards when a hidden code is claimed. A phone number is collected only if the consumer opts in.
- Results in local languages.
