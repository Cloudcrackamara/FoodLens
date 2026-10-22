# FoodLens decisions

Open choices from Section 13 of the handoff and answers to the pre-Phase-0 questions. Change any row by editing it and noting the date.

## Open choices (handoff §13)

| # | Choice | Decision | Status |
|---|---|---|---|
| D1 | Frontend framework | Next.js (App Router) + TypeScript + Tailwind + TanStack Query + Zod | Decided |
| D2 | PostgreSQL vs SQLite | PostgreSQL for dev, tests, and demo (via Docker Compose) | Proposed |
| D3 | Lookup input method | Manual product code + batch entry first. Optional QR holding an opaque FoodLens URL as stretch. No OCR. | Superseded by D88 (in-browser OCR) |
| D4 | Consumer concern reports | Stretch (Phase 8), not MVP | Proposed |
| D5 | **Superseded by D111 (2026-10-21).** Seed data volume | 3 categories, 4 companies (2 manufacturers, 1 wholesaler, 1 both), ~10 products, ~25 batches, 2 agencies (NAFDAC simulated, SON/MANCAP simulated), 5 locations. Includes expired, inactive, mismatch, no-credential, pending, and not-found cases. | Proposed |
| D6 | Multiple users per company | Yes, via `COMPANY_MEMBER`. One company per user in MVP. | Proposed |
| D7 | Change-notice attachments | PDF, PNG, JPEG only; max 5 MB; private local storage; admin and owning company can download | Proposed |
| D8 | Scan logs | Off by default. If enabled, no user, IP, or location link. | Proposed |
| D9 | Fulfilment batch allocation | In MVP (Phase 7), simple allocation without inventory tracking | Proposed |
| D10 | Order status lifecycle | `SUBMITTED` → `ACCEPTED` or `DECLINED`; `ACCEPTED` → `FULFILLED`; buyer may cancel (`CANCELLED`) while `SUBMITTED`. Seller replies are notes on the order. | Superseded by D96 (`SUBMITTED` renamed `REQUESTED`) |
| D11 | Supplier-location review checklist | Address and area present; linked to an approved company; named contact representative; reviewer and timestamp recorded | Proposed |

## Implementation defaults

| # | Choice | Decision | Status |
|---|---|---|---|
| D12 | Auth mechanism | FastAPI httpOnly cookie session; bcrypt hashing; Next.js rewrites `/api/*` to FastAPI | Decided (2026-10-07) |
| D13 | Admin model | `is_admin` flag on `APP_USER`, set only by seed/CLI (not the separate `ADMIN_USER` table in the old ERD) | Proposed |
| D14 | DB session style | Sync SQLModel sessions | Proposed |
| D15 | Frontend tests | Vitest + Testing Library; Playwright E2E in Phase 9 | Proposed |
| D16 | Phase numbering | Gate + phases 0–9; handoff §12 step 8 split into supplier discovery (6) and order requests (7) | Amended by D102 (8 Deployment, 9 Polish and evaluation) |

## Answers to pre-Phase-0 questions (2026-10-07)

### Q1 — Docs and ERD
Decided by Claude at the founder's request ("do what is best").
- Handoff renamed to `docs/HANDOFF.md`.
- Old consumer-only ERD moved to `docs/archive/ERD_v1_consumer_only.mmd` (kept for the capstone report's design history).
- New `docs/ERD.mmd` drafted from handoff §7 plus the decisions below. It is a draft; Alembic migrations are the source of truth once written.

### Q2 — Supervisor approval
Yes. Supervisor approved simulated data, user roles, and no-payment order requests.

### Q3 — What companies may change directly vs through review

**Direct (no review), change is logged with actor and time:**
- Private account settings.
- Unpublished product drafts.
- Company contact details.
- Product announcements (see Q7).

**Requires a change notice and admin review:**
- Published product details: name, brand, barcode, package size, manufacturer, label information.
- Batch numbers and expiry dates.
- Regulatory credential details.
- Reviewed supplier-location information.

**Change notice rules:**
- Each notice holds structured proposed values, not only free text. For each field it shows current value, proposed value, reason, and optional supporting document or image.
- The admin sees a field-by-field diff before deciding.
- While a notice is `PENDING_REVIEW` or `CLARIFICATION_REQUESTED`, published data is unchanged.
- On approval, the backend validates and applies the proposed values, then records old value, new value, approver, and approval time.
- On rejection, published data is unchanged.

**New records:** new batches and company-entered credentials stay `PENDING_REVIEW` until an admin reviews them.

**Wording:** any approval means "reviewed for the FoodLens demonstration database" only. It is never described as NAFDAC or SON approval. Simulated credentials and lookup results stay visibly labelled as demo data.

### Q4 — Lookup result precedence (superseded by D82, 2026-10-09)
Each lookup returns one primary `result` plus a `warnings` list so secondary conditions are still shown. Checked in this order:

1. Input empty, malformed, or matching more than one record: `INSUFFICIENT_OR_AMBIGUOUS`.
2. Product code not found, or batch not found under that product (including batches that are pending or rejected): `BATCH_NOT_FOUND`. If the batch number exists under a different product, return `DETAILS_MISMATCH` with the differing field (`product_code`).
3. Batch expiry date has passed: `BATCH_EXPIRED` (new state). Message: "The expiry date stored for this batch in the demo data has passed."
4. Product has approved credentials but all are expired or inactive: `CREDENTIAL_EXPIRED_OR_INACTIVE`.
5. Product has no approved credential record: `DETAILS_MISMATCH` with differing field `credential`. Message says no credential record matches this product in the demo data. (Founder's choice: mismatch rather than not-found, since the batch does exist.)
6. Otherwise: `DEMO_RECORD_FOUND`.

Every response carries `data_mode: "DEMO"` and the disclaimer regardless of result.

### Q5 — Company-entered credentials (superseded by D80-D81, 2026-10-09)
Hidden from consumer lookups until an admin approves them.

### Q6 — Buyer approval (superseded by D95, 2026-10-12)
Wholesaler/buyer companies do not need admin approval to order. Protection comes from the seller side: buyers can only see and order from approved seller companies, approved products, and reviewed locations.

### Q7 — "POPs"
POPs means pop-up messages. Implemented as **product announcements**:
- An approved company can post an announcement on its product (for example "New packaging from March 2027"), optionally with an image.
- Announcements go live immediately, without admin review.
- They are shown to consumers as a pop-up on lookup results for that product and labelled "Message from the company — not reviewed by FoodLens".
- An announcement never changes product data. Changing actual product fields still needs a change notice (Q3).
- Admins can hide an announcement afterwards; hiding is logged.

### Q8 — Clarification state
Yes. Change notice states: `PENDING_REVIEW`, `CLARIFICATION_REQUESTED`, `APPROVED`, `REJECTED`. The company can respond to a clarification request, which returns the notice to `PENDING_REVIEW`.

### Q9 — Timeline
As soon as possible, working phase by phase together. No fixed date.

### Pending batches in lookup
A batch that is `PENDING_REVIEW` or `REJECTED` is invisible to consumer lookup and returns `BATCH_NOT_FOUND`.

## Phase 1 data model decisions (approved 2026-10-07)

Changes to the draft ERD, all approved by the founder. Implemented in migration `0002_initial_schema`; described in `docs/SCHEMA.md`.

| # | Decision | Reason |
|---|---|---|
| D17 | Change notice targets are four optional FKs (`product_id`, `batch_id`, `credential_id`, `location_id`) with a check that exactly one is set. Replaces `target_type` + `target_id`. | The database rejects notices pointing at records that do not exist. |
| D18 | `PRODUCT_ANNOUNCEMENT` has no `company_id`; the company comes from the product. | Avoids two copies of ownership that could disagree. |
| D19 | **Superseded by D80-D85 (2026-10-09).** Credentials are product-level only; the `scope` / batch-specific option is removed for the MVP. | A batch-specific credential needs a batch link the model did not have; matches non-negotiable rule 3. |
| D20 | Database checks: quantities > 0, attachment size 1 byte–5 MB, `valid_until >= valid_from`, `expiry_date >= production_date`, buyer ≠ seller. | Enforce simple invariants even if a service has a bug. |
| D21 | Company-asserted identity fields are prefixed `claimed_` (`claimed_legal_name`, `claimed_business_identifier`, `claimed_address`). | Keeps claimed data visibly separate from reviewed fields. |
| D22 | All reviewable tables (company, product, batch, credential, location, change notice) share `review_status` / `status`, `reviewed_by_user_id`, `reviewed_at`, `review_note`. | One review pattern for services and tests. |
| D23 | **Superseded by D61 (2026-10-09).** Publishing a product needs admin review: `DRAFT → PENDING_REVIEW → PUBLISHED / REJECTED`, plus `WITHDRAWN`. | Without it a company could put any product in front of consumers unreviewed. Extends non-negotiable rule 4. |
| D24 | `USER_SESSION` table holds hashed session tokens with expiry and revocation. | Server-side sessions can be revoked on logout; JWT cookies cannot. |
| D25 | `COMPANY_MEMBER` gains `is_public_contact`, `public_title`, `public_phone`, `public_email`. | Supplier pages can name representatives without exposing login emails. |
| D26 | **Superseded by D106 (2026-10-21).** Member roles are `OWNER` and `REPRESENTATIVE` only. | `STAFF` had no distinct permissions. |
| D27 | `created_at` on every table; `updated_at` only on edited tables. Append-only tables (`audit_log`, `change_notice_field`, `notice_attachment`, `order_line`, `order_batch_allocation`, `user_session`) have none. | Makes immutability visible in the schema. |
| D28 | Enums stored as `VARCHAR` + `CHECK`, not native PostgreSQL enums. | Native enums need awkward migrations to add values. |
| D29 | `BATCH_SCAN` and `CONCERN_REPORT` are deferred to Phase 8's migration. They stay in `ERD.mmd`, marked Phase 8. | Optional features; no empty tables until needed. |
| D30 | `docs/PLAN.md` Phase 1 is now "Data model"; identity/roles moved to the start of Phase 2. | The whole schema was built in one phase at the founder's request. |

## Auth decisions (2026-10-08)

Implements D12 (httpOnly cookie session, bcrypt) and D24 (`USER_SESSION` table). Code: `backend/app/core/security.py`, `core/auth.py`, `services/auth.py`, `routers/auth.py`.

| # | Decision | Reason |
|---|---|---|
| D31 | Passwords: bcrypt (12 rounds; 4 in tests only), 10 characters minimum, 72 bytes maximum (bcrypt's limit; longer passwords are rejected, not truncated). | Matches D12; rejection avoids silently ignoring part of a password. |
| D32 | Session token: 32 random bytes in a cookie named `foodlens_session`; only its SHA-256 hash is stored. Cookie is `HttpOnly`, `SameSite=Lax`, `Path=/`, `Secure` when `SESSION_COOKIE_SECURE=true`. Sessions last 24 hours. | A leaked database row cannot be replayed as a cookie. Lax blocks the cookie on cross-site POSTs (basic CSRF protection). |
| D33 | Logout revokes the session in the database and clears the cookie; deactivating a user ends all their sessions. | Server-side revocation is the reason for D24. |
| D34 | Login failures (unknown email, wrong password, inactive account) all return 401 "Invalid email or password", and unknown emails still run a bcrypt check. | Does not reveal which accounts exist, by message or timing. Registration still returns 409 for a taken email, an accepted trade-off for a demo. |
| D35 | Registration reads only `email`, `password`, `display_name`; any other field (e.g. `is_admin`, `is_active`, `review_status`, `user_id`) is ignored, not rejected. Email is stored lowercased. Registration signs the user in. | Founder's instruction; the service takes explicit keyword arguments, so mass assignment is impossible. |
| D36 | Admins are created only by `uv run python -m app.seed` from `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD`. An existing account with that email is promoted; its password is not changed. | No API path can grant admin. |
| D37 | Dependencies: `current_user` (401), `require_admin` (403), `require_company_member(*roles)` (403; needs a `company_id` path parameter; admins do not pass as members). | One place for authorization checks; admins act through admin routes. |
| D38 | Not in scope yet: password reset, email verification. (Login rate limiting added in D41.) | Out of capstone MVP scope; listed so the report can name them as limitations. |

## Rate limiting (2026-10-08)

Approved by the founder. Code: `backend/app/core/rate_limit.py`. All values configurable in `backend/.env`.

| # | Decision | Reason |
|---|---|---|
| D39 | **Amended by D119 (2026-10-21).** Limits are per client IP address only (login adds the email). No cookies, fingerprinting, or per-consumer identifiers. Counters live in process memory, are never stored or logged, and are dropped once refilled. | Keeps consumer lookups anonymous. |
| D40 | **Amended by D119 (2026-10-21).** Product lookups use a token bucket: burst 20, refill 1 per second (about 60 per minute) per IP. | Several consumers on shared Wi-Fi are not blocked; sustained scraping is. |
| D41 | Login: 5 per minute per IP + email. Registration: 5 per hour per IP. Both are token buckets (burst = the number, refilling evenly over the period). Login is checked before the password. | Limits password guessing and bulk account creation. Closes the rate-limiting part of D38. |
| D42 | `RATE_LIMIT_EXEMPT_IPS` (IPs or CIDR ranges, empty by default) is never limited; `RATE_LIMIT_ENABLED=false` turns limits off. Invalid entries stop the API at startup. | Usability-test sessions from one room must not be blocked. |
| D43 | Over the limit: HTTP 429 with a `Retry-After` header (whole seconds). The frontend explains the limit is shared by everyone on the same network and says when to retry. | Users understand it is not their fault and how long to wait. |
| D44 | Client IP: the connecting address, or, when the connection comes from `TRUSTED_PROXY_IPS` (the Next.js server), the right-most `X-Forwarded-For` entry that is not a trusted proxy. Limits are per API process. | The browser reaches FastAPI through the Next.js `/api` proxy. Several API processes would need a shared store (e.g. Redis). |
| D45 | `next dev` / `next start` keep a client-supplied `X-Forwarded-For` (`??=` in Next.js 16.4 `base-server.js`; the rewrite proxy does not append), so a forged header could dodge the limits. **Fixed** with a custom server, `frontend/server.mjs`, which replaces `X-Forwarded-For` with the real connection address (and drops `Forwarded`) before Next.js runs. `npm run dev` / `npm run start` use it. IPv4-mapped addresses (`::ffff:a.b.c.d`) are normalised on both sides. If a CDN or reverse proxy is ever placed in front of the web server, `server.mjs` must trust it instead, or all visitors share its IP. | Verified end to end from the LAN address: before the fix forged headers were never limited; after it the 6th login attempt got 429 with `Retry-After` despite a new forged IP on every request. |

## Consumer lookup (2026-10-08)

Code: `backend/app/services/lookup.py`, `routers/lookups.py`, `demo_data.py`; `frontend/components/lookup/`.

| # | Decision | Reason |
|---|---|---|
| D46 | **Superseded by D118 (2026-10-21).** Every lookup writes an anonymised `BATCH_SCAN` row: normalised input, matched batch (if any), result, time. No user, session, IP, user agent, or location. **Supersedes D8** (scan logs off by default) and brings that part of D29 forward, at the founder's request. | Usage evidence for the evaluation without identifying anyone. |
| D47 | **Superseded by D80-D85 (2026-10-09).** Six lookup states, not five: `BATCH_EXPIRED` kept from Q4 / non-negotiable rule 1 although the build request listed five. No approved credential returns `DETAILS_MISMATCH` (field `credential`), per Q4. | Follows recorded decisions; reversible if the founder prefers five. |
| D48 | **Superseded by D80-D85 (2026-10-09).** Product code is required to show a record. Batch number alone returns `INSUFFICIENT_OR_AMBIGUOUS` with the matching products as candidates (name, brand, code only) so the user can choose; choosing resubmits with the code. | Handoff §5: "ask for correction or manual selection"; a batch number alone never reveals a record. |
| D49 | Only approved batches of published products of approved companies, and approved credentials, are visible. Anything else looks like `BATCH_NOT_FOUND` (or no credential). | Rules 4-5 and Q5: unreviewed data never reaches consumers. |
| D50 | Input is trimmed, inner whitespace collapsed, upper-cased; max 64 characters of letters, digits, space and `- . / _`; otherwise `INSUFFICIENT_OR_AMBIGUOUS`. A mismatch on product code does not reveal which product owns the batch. | Tolerant of how people type codes; no data leakage. |
| D51 | **Superseded by D80-D85 (2026-10-09).** Credential status shown is computed on the lookup date: `ACTIVE_IN_DEMO_DATA`, `EXPIRED_IN_DEMO_DATA` (past `valid_until`), `INACTIVE_IN_DEMO_DATA` (stored inactive), `NOT_YET_VALID_IN_DEMO_DATA` (before `valid_from`, counts as not active). One active credential is enough for `DEMO_RECORD_FOUND`; others not active add a warning. A batch expiring today is not expired. | One consistent rule for every response. |
| D52 | Result screen uses neutral colours (no green/red), repeats the demo banner inside every result, labels each credential "Product-level · Demo data", and shows the scope note "not to this batch … not a batch certificate or a test result". The banned-word check is whole-word (`safe`, `unsafe`, `fake`); the disclaimer's "food-safety test" is allowed. | Rules 1-3: a result describes a demo record, never fitness to eat. |
| D53 | **Superseded by D111 (2026-10-21).** Demo seed (`uv run python -m app.seed`): 4 fictional companies (1 pending), 8 products (1 draft), 11 batches (1 pending, 1 expired, 1 lot number shared by two products), NAFDAC (simulated) and SON MANCAP (simulated), 8 credentials (1 expired, 1 inactive, 1 pending). Dates are relative to the seeding day. `SEED_CASES` documents one lookup per state and is tested through the API. | Satisfies D5 at a smaller size; every state is demonstrable. |

## Companies, admin review, and supplier directory (2026-10-08)

Code: `backend/app/services/companies.py`, `services/suppliers.py`, `routers/companies.py`, `routers/admin.py`, `routers/suppliers.py`; `frontend/components/{company,admin,suppliers}/`.

| # | Decision | Reason |
|---|---|---|
| D54 | `POST /api/companies`: a signed-in user with no company creates a company in `PENDING_REVIEW` and becomes its `OWNER`. Only company fields are read; review status, reviewer, and IDs sent by the client are ignored. A user already in a company gets 409; admin accounts get 403. | Rule 4 and D21; one company per user (D6); admins stay neutral reviewers. |
| D55 | Company transitions: approve from `PENDING_REVIEW` or `SUSPENDED` (reinstate); reject from `PENDING_REVIEW`; suspend from `APPROVED`. Anything else is 409. Each decision sets reviewer, time, optional note, and writes `audit_log`. | Clear lifecycle; every decision attributable. |
| D56 | Admins can never review a company (or its locations) they are a member of: 403. | No self-approval, even for admins. |
| D57 | Supplier locations can be added only by members of an approved company and start `PENDING_REVIEW`. Admin can mark demo-reviewed (approve) or reject, only from pending, and only approve while the company is approved. A named contact is optional; if given it must be an active member of the same company. Editing reviewed locations is left to change notices (Phase 5). | Rule 5. D11's "named contact" is not enforced yet because D11 is still Proposed. |
| D58 | `GET /api/suppliers` is public, at the founder's request (the handoff had wholesalers signing in). It lists approved companies that have at least one demo-reviewed location, shows only those locations, the company's public contact details, and members who opted in as public contacts. It never shows claimed fields, review notes, or login emails. | Rules 4 and 7; privacy of claimed data and accounts. |
| D59 | Badge text is exactly "FoodLens demo-reviewed profile", always with the note "Reviewed for the FoodLens demonstration database only. This is not a NAFDAC or SON approval, and it does not verify the company's identity or products." | Rule 4 wording. |
| D60 | Seed adds five fictional locations: three reviewed (Demo Harvest ×2, Sample Springs) and two pending (Example Grain Mills, Pending Demo Snacks), so the directory shows two suppliers. | Demonstrates both listed and hidden cases. |

## Company catalogue (2026-10-09)

Founder decision: keep the catalogue simple. Code: `backend/app/services/catalogue.py`, `routers/catalogue.py`; `frontend/components/company/Catalogue.tsx`.

| # | Decision | Reason |
|---|---|---|
| D61 | **Amended by D107 (manufacturers only) (2026-10-21).** Approved companies publish new products and batches directly: products are `PUBLISHED` and batches `APPROVED` on creation, with no admin step. **Supersedes D23** and the "new batches stay pending" part of rule 5. Pending, rejected, or suspended companies cannot add products (409), and their products are hidden from lookups anyway. | Less friction for companies; the credential review (D63) still stops unreviewed data from looking trustworthy. |
| D62 | A batch with `review_status = APPROVED` and no reviewer means "published by the company". Product codes, batch numbers, and credential references are stored normalised (trimmed, upper-case) and must be unique case-insensitively: product code across the catalogue, batch number per product, reference per agency. | Lookups normalise input, so stored codes must match exactly. |
| D63 | **Superseded by D80-D85 (2026-10-09).** Company-entered credentials are claims: `PENDING_REVIEW`, status `ACTIVE`, `data_mode` `DEMO`, and fixed provenance "Entered by the company as a claim…", all set by the server (the client cannot set status). Hidden from lookups until an admin approves; rejected claims stay hidden. Admins review them at `/admin` with the same conflict-of-interest and audit rules as companies (D55-D56). | Rule 3 and Q5. Until a claim is approved, a company's new product returns `DETAILS_MISMATCH (credential)`, never "Demo record found". |
| D64 | Editing a published product is not built here; it goes through change notices (Phase 5). No separate product-approval flow. Extra representatives and a supplier detail page are skipped (one owner per company is enough). | Avoid over-engineering. |
| D65 | On company registration the owner becomes the directory contact: `is_public_contact`, title "Owner", and the company's contact email and phone. The owner's login email is never shown. | Directory must show the owner's contact (founder request) without breaking D58. |
| D66 | **Superseded by D105 (2026-10-21).** Registration offers three company types: Manufacturer, Wholesaler, or Manufacturer and wholesaler (`MANUFACTURER`, `WHOLESALER`, `BOTH`). Any approved company type may add products. | Confirmed by the founder; tested for all three. |
| D67 | **Superseded by D80-D85 (2026-10-09).** (2026-10-09) Credential claims are stored `INACTIVE` + `PENDING_REVIEW`; only admin approval sets them `ACTIVE`. Rejected claims stay `INACTIVE`. Replaces the "status `ACTIVE`" part of D63. | Founder instruction: a claim is never active until admin review. |

## Change notices (2026-10-09)

Code: `backend/app/services/change_notices.py`, `routers/change_notices.py`; `frontend/components/company/ChangeNotices.tsx`, admin queue in `components/admin/AdminReview.tsx`.

| # | Decision | Reason |
|---|---|---|
| D68 | A notice targets one of the company's products or batches. Allowed fields: product name, brand, category, package size, manufacturer, label information; batch production and expiry dates. Product codes and batch numbers cannot be changed (they are printed on packages and identify the record). Unknown fields, empty required fields, and "changes" equal to the current value are rejected (422). | Validated, structured `proposed_changes` (Q3); codes stay stable for consumers. |
| D69 | `proposed_changes` is accepted as JSON and stored as one `change_notice_field` row per field with a snapshot of the current value (dates as ISO text). Submitting changes no published data. | Field-by-field diff for the admin; rule 5. |
| D70 | Admin decisions: approve (from pending), request clarification (from pending; a note is required), reject (from pending or clarification). The company answers a clarification with a message, appended to the reason, and the notice returns to pending. To change proposed values, the company submits a new notice. | Q8 lifecycle without editable history. |
| D71 | Approval applies all fields in one transaction with a row lock, after checking every live value still equals its snapshot; if anything changed since submission it returns 409 and applies nothing. Each applied row stores `applied_old_value`; an audit entry records old and new values with the notice id. | Atomic change with history; no silent overwrite of a newer value. |
| D72 | Attachments: `.pdf`, `.png`, `.jpg`, `.jpeg` only, checked by extension and file signature (`%PDF-`, PNG header, JPEG `FF D8 FF`); 1 byte to 5 MB (413 when larger); at most 5 per notice; only while the notice is open. | Rejects renamed or disguised files. |
| D73 | Files are saved under a random 32-hex-character key in `UPLOAD_DIR` (default `backend/storage/notices`, git-ignored, never served statically). Original filenames are sanitised and only used for the download name. Downloads go through authorised routes (owning company members, admins) with `Content-Disposition: attachment`, `nosniff`, and `no-store`. | Private evidence; no path tricks or public URLs. |
| D74 | `effective_date` is recorded and shown but does not delay application: an approved change applies immediately. Product announcements were added afterwards (D75-D79). | Kept simple; announcements were not requested in this step. |

## Product announcements, "POPs" (2026-10-09)

Code: `backend/app/services/announcements.py`, `routers/announcements.py`; `frontend/components/company/Announcements.tsx`, pop-up in `components/lookup/LookupResultView.tsx`.

| # | Decision | Reason |
|---|---|---|
| D75 | Members of approved companies post announcements on their own products: title (max 80) and message (max 500). They go live at once (`LIVE`); the client cannot set status. No image for now. | Q7 and rule 5 exception; kept simple. |
| D76 | Lookup responses include up to 3 newest live announcements for the matched product, each with the fixed label "Message from the company — not reviewed by FoodLens". Only shown when the product is visible (approved company, published product). The frontend shows them in a closable box on the result. | Consumers see the message but know FoodLens did not review it. |
| D77 | Announcement text containing the whole words "safe" or "unsafe" is refused (422), so a company cannot claim its product is safe or unsafe. Whole-word matching means "safety", "safely", "fake", and "counterfeit" are allowed, so companies can warn about counterfeits ("beware of fake versions"). FoodLens's own wording still never uses "fake" (rule 1). Regulator claims such as "NAFDAC approved" are not blocked automatically; admins hide misleading ones. | Founder decision (2026-10-09): allow counterfeit warnings, block only safe/unsafe claims. |
| D78 | Announcements never change product data. The company can withdraw its own; admins can hide any (except for a company they belong to). Both set `HIDDEN`, `hidden_by_user_id`, `hidden_at`, and write an audit entry. Hidden announcements are not shown again. | Rule 5 exception; accountability. |
| D79 | Admins see live announcements at `/admin` with a Hide button and optional reason (stored in the audit log). | Post-moderation instead of pre-approval. |

## Core purpose: registration check against a simulated register (2026-10-09)

Founder correction: FoodLens exists so consumers can check that a product's printed NAFDAC/SON number is registered, according to the register. Company/wholesaler features are secondary. Credentials as company claims approved by FoodLens only proved FoodLens accepted a claim, so they were removed. Migration `0004_regulator_register`.

| # | Decision | Reason |
|---|---|---|
| D80 | **Superseded by D104 (2026-10-21).** New `regulator_register` table (agency, registration number, registered product name, registered company name, status `ACTIVE`/`INACTIVE`, expiry, `data_mode` `DEMO`, provenance, last checked) is the only source of registration status. Seeded fictional data with `DEMO-` numbers; no API can create or change it. `credential_record` is dropped, with its data, the credential claim/approval endpoints, `GET /api/agencies`, and `change_notice.credential_id`. | The register stands in for the regulator's records; FoodLens approval is not registration. |
| D81 | **Amended by D107 (information only, never checked) (2026-10-21).** Companies enter only the number printed on their pack: `product.registration_number` (optional, normalised, not unique, since a copied number on another product is exactly what lookups must catch). It can be changed through a change notice. Admins no longer approve credentials. | Rule 3 rewritten. |
| D82 | **Superseded by D104 (2026-10-21).** Lookup input: registration number (required) and batch number (optional). Consumers have no product code (packs carry only the printed number and batch). Results, checked in this order: `INSUFFICIENT_OR_AMBIGUOUS` (missing or malformed), `REGISTRATION_NOT_FOUND`, `REGISTRATION_EXPIRED_OR_INACTIVE` (inactive or past `expires_on`; a record expiring today is active), `REGISTRATION_MISMATCH`, `REGISTERED_ACTIVE`. Batch findings are warnings: `BATCH_NOT_IN_CATALOGUE`, `BATCH_EXPIRED`, and `REGISTRATION_MISMATCH` when the record is also expired/inactive. Endpoint renamed to `POST /api/lookups/registration`. | Founder answers 1 and 2; the old product-code-and-batch results no longer fit. |
| D83 | **Superseded by D104 (2026-10-21).** `REGISTRATION_MISMATCH` uses the batch: if the entered batch belongs to a visible FoodLens product whose registration number differs from the one entered, or whose product name / company claimed legal name differ from the register record (compared ignoring capitals and spaces), it is a mismatch. If the lot number exists on several products, the one carrying the entered number is used. | Founder answers 1 and 3. |
| D84 | **Superseded by D104 (2026-10-21).** Wording: a match is "matches an active record in the simulated NAFDAC/SON register (demo data)"; results never say "safe", "genuine", or "verified by NAFDAC", and state that a matching number cannot rule out a copied number. Every response keeps `data_mode` `DEMO`, the disclaimer (now "not NAFDAC's or SON's own system"), and shows the register record so consumers can compare names with the pack. | Founder-confirmed wording. |
| D85 | **Superseded by D104 and D117 (2026-10-21).** Scan-friendly input: registration numbers are upper-cased, all whitespace removed, and a leading label such as "NAFDAC Reg No:" stripped. `/check?reg=...&batch=...` opens the form filled in and runs the check (read server-side inside `Suspense`). `batch_scan.input_product_code` became `input_registration_number`; old scan rows were deleted because their results no longer exist. | Camera scanning comes next; a scanner only has to hand over two strings. |
| D86 | **Superseded by D104 (2026-10-21).** Announcements also refuse regulator claims, whole words, any case, either order: "NAFDAC approved/registered/certified", "SON approved/certified", "approved/registered/certified by NAFDAC", "approved/certified by SON" (space or hyphen). Known limitation: "my son approved..." is also refused because matching is case-insensitive. Mentions such as "the NAFDAC number on the cap" are allowed. | Founder answer 4; registration status only comes from the register. |
| D87 | **Superseded by D104 (2026-10-21).** Seed: 7 register records (5 active, 1 expired, 1 inactive SON), products carrying their pack numbers, and "Sample Honey" carrying a number registered to a company not in FoodLens. `SEED_CASES` covers all five results plus both warnings and scanned text. | Every result demonstrable. |

## Camera scanning (2026-10-12)

Code: `frontend/lib/ocr/` (`extract.ts`, `preprocess.ts`, `engine.ts`, `readImage.ts`), `frontend/components/scan/` (`ScanPack.tsx`, `ConfirmScan.tsx`), `frontend/scripts/copy-ocr-assets.mjs`, `frontend/server/forwarded-for.mjs`.

| # | Decision | Reason |
|---|---|---|
| D88 | **Amended by D117 (2026-10-21).** "Scan pack" on `/check` reads the printed registration number, then optionally the batch number, with the phone camera. OCR runs only in the browser (Tesseract.js 7). No image is uploaded, logged, or stored: frames are read from a canvas that is cleared straight after, and only the confirmed text is sent to the existing lookup. CLAUDE.md "never add OCR" changed to "OCR only in the browser". | Founder approval (2026-10-12); consumers stay anonymous. |
| D89 | All OCR files (worker, LSTM engine builds, English `best_int` model, about 7 MB on first scan) are served by FoodLens from `/ocr/`, copied from `node_modules` by `scripts/copy-ocr-assets.mjs` before `dev` and `build` (git-ignored). Tesseract.js's default CDN (jsDelivr) is never used. The engine loads only when "Scan pack" is opened and is freed when the scanner closes; the browser caches the model. | A CDN would see who uses the scanner; keeps the lookup page light. |
| D90 | Behind a Cloudflare Tunnel, `server.mjs` takes the visitor IP from `CF-Connecting-IP`, but only when `TRUST_CLOUDFLARE_TUNNEL=true` and the connection comes from an address in `CLOUDFLARED_IPS` (default `127.0.0.1,::1`). Otherwise the socket address is used, as before (D45). The header is removed before the request reaches Next.js or the API. Off by default. | Without it, every phone through the tunnel would share one rate-limit bucket; trusting the header from anyone else would let rate limits be dodged. |
| D91 | **Superseded by D117 (2026-10-21).** Number extraction does not assume one NAFDAC format. Labels ("NAFDAC Reg No", "Reg No", "SON/MANCAP No", "Batch", "BN", "B/N", "LOT") are the strongest clue, including labels glued to the number; otherwise tokens are ranked by shape (hyphen, digits, length). O/I/S/B-style confusions are fixed only in digit-heavy parts. Dates after EXP/MFD are ignored, and the other field's labelled value is not offered. Up to 4 readings are offered. Recognised characters: letters, digits, hyphen, and space (without the space, Tesseract glued words together). | Real pack formats vary (A1-1234, 01-2345, MC-...); a wrong guess is cheap because the person confirms. |
| D92 | Image clean-up: crop to the on-screen guide box (mapped through `object-fit: cover`), scale to about 1400 px wide, greyscale, 2-98% contrast stretch, Otsu threshold, invert light-on-dark print. Page mode: single block. | Small, low-contrast pack print; works offline on cheap phones. |
| D93 | No camera, or permission refused: the scanner offers a photo picker (`capture="environment"`) read the same way; typing always remains. The camera uses the back lens, no audio, and every track is stopped after each capture step. | Works on any phone; no camera left running. |
| D94 | **Amended by D117 (2026-10-21).** The confirm screen is always shown: both values editable, other readings as one-tap choices, the batch optional, "Check the register" disabled until a registration number is present. Only then does the normal lookup run, with the same `data_mode` DEMO banner and wording. | OCR misreads; the person stays in control and the result wording rules are unchanged. |

## Wholesale order requests (2026-10-12)

Code: `backend/app/services/orders.py`, `routers/orders.py`, `services/suppliers.py`, `schemas/order.py`; migration `0005_order_requests`; `frontend/components/suppliers/SupplierPage.tsx`, `components/orders/`, `components/company/IncomingOrders.tsx`.

| # | Decision | Reason |
|---|---|---|
| D95 | **Hidden as future work by D127 (2026-10-21).** Only members of **approved** `WHOLESALER` or `BOTH` companies can send order requests. Pending, rejected, or suspended companies cannot place orders, and a seller that is not listed in the directory (approved, with a reviewed location) cannot receive them or respond. A suspended seller's open requests can still be cancelled by the buyer. Supersedes Q6. | Founder instruction for this phase. |
| D96 | **Hidden as future work by D127 (2026-10-21).** Status flow: `REQUESTED` → `ACCEPTED` / `DECLINED` (seller) / `CANCELLED` (buyer); `ACCEPTED` → `FULFILLED` (seller). Every other change is refused with 409. `SUBMITTED` was renamed `REQUESTED` (migration 0005). Every action writes an audit entry with actor and old/new status. | Founder wording; one place (`TRANSITIONS`) defines the flow. |
| D97 | **Hidden as future work by D127 (2026-10-21).** The buyer is the company in the URL (membership checked); the seller is the company that owns the ordered products. Input never carries status, company IDs, user IDs, reviewer, or payment fields. One supplier per order, 1-20 lines, each product once, quantity > 0 (up to 3 decimals), unit 1-30 characters. Pickup needs one of the seller's reviewed locations; delivery needs an address or notes (5-500 characters). | Client input cannot set ownership; keeps the form simple. |
| D98 | **Hidden as future work by D127 (2026-10-21).** Seller messages: "Reply" (while requested or accepted) and a decline reason are stored in `seller_note`; the latest one is shown, earlier ones stay in the audit log. No message threads or notifications. | Minimal scope. |
| D99 | **Hidden as future work by D127 (2026-10-21).** When marking fulfilled, the seller may link each line to one or more of its own **approved** batches of that product. Allocations carry no quantity (FoodLens keeps no stock); `allocated_quantity` was dropped and a line links a batch only once. | Founder skipped inventory. |
| D100 | **Register part superseded by D104 and D127; hidden (2026-10-21).** `GET /api/suppliers/{company_id}` is public like the directory (D58) and returns 404 for unlisted companies. Each published product shows its result in the simulated register, checked in this order: `NO_NUMBER_GIVEN`, `NOT_FOUND_IN_DEMO_REGISTER`, `EXPIRED_OR_INACTIVE_IN_DEMO_REGISTER`, `REGISTERED_TO_ANOTHER_PRODUCT` (product or company name differs from the register record, compared as in D83), `ACTIVE_IN_DEMO_REGISTER`. Every label says "(demo data)"; the response has `data_mode` DEMO and a disclaimer; the page shows the demo banner. Directory search also matches published product names and brands. | Founder request (active / expired or inactive / not found). The extra "different product or company" result was added because the seeded "Sample Honey" carries a copied number and would otherwise show "Active". |
| D101 | **Hidden as future work by D127 (2026-10-21).** Seed adds "Demo Market Traders (fictional)" (wholesaler), owner accounts `buyer@demo.foodlens.invalid` (that company) and `seller@demo.foodlens.invalid` (Demo Harvest Foods), and one order in each of requested, accepted, declined, fulfilled. The accounts sign in only when `SEED_DEMO_PASSWORD` is set; otherwise their password hash is unusable. `/api/auth/me` membership now includes `company_type`. | Orders need users; no default password in the code. |
| D102 | **Superseded by D130 (2026-10-21).** Remaining phases re-ordered: 7 Wholesale order requests, 8 Deployment (cloud VM, Docker Compose, named Cloudflare Tunnel), 9 Polish and evaluation. Concern reports and scan analytics are deferred. | Founder instruction (2026-10-12). |

## Company contact edits (2026-10-12)

| # | Decision | Reason |
|---|---|---|
| D103 | `PATCH /api/companies/{company_id}/contact` lets the company **owner** change the public contact email and phone directly, in any review status, without admin review. Each real change writes an audit entry (`contact_updated`) with actor, time, and old and new values; an unchanged save writes nothing. The owner's directory contact follows when it still showed the old details (D65). Representatives cannot edit; other fields (name, type, claimed legal details, status) cannot be changed this way. Published product and batch details still change only through change notices; no PUT/PATCH/DELETE route exists for them, and a test checks that. | Rule 5: contact details are edited directly but logged. Closes Phase 4. |

## Scope change: unit-level product integrity (2026-10-21)

The founder changed FoodLens from a registration-number lookup into a unit-level product integrity platform.

- **Source of truth:** `docs/PRODUCT_INTEGRITY.md` (formerly `Update.md`), plus the planning prompt of 2026-10-21. Where the prompt adds detail, the prompt wins. That covers the hidden code, OCR of the hidden code, the before/after-purchase messages, POS integration, the privacy rules and the seed scenario.
- **Questions:** Q1–Q9 were answered by the founder on 2026-10-21.
- **Related docs:** phases are in `docs/PLAN.md`; the schema is in `docs/SCHEMA.md`.
- **Status:** every entry below is **Decided (2026-10-21)** unless it says otherwise.

### Scope, companies and catalogue

| # | Decision | Reason |
|---|---|---|
| D104 | **The simulated regulator register and the registration lookup are removed.** That covers `regulator_register`, `regulatory_agency`, `batch_scan`, `POST /api/lookups/registration` and the five lookup results. **Supersedes D80, D82–D87 and the register part of D100.** The registration number stays on products as information only (D107). | A registration number is shared by thousands of units, so it cannot identify one item. The new core is unit identity, lifecycle events and scan intelligence. |
| D105 | **Company types become three flags:** `is_manufacturer`, `is_distributor` and `is_retailer`. A company may have several of them; a CHECK requires at least one. Existing data maps as follows: WHOLESALER becomes distributor, and BOTH becomes manufacturer plus distributor. Admin company approval is unchanged (D54–D56). **Supersedes D66.** | Real firms both distribute and retail. |
| D106 | **Members are `OWNER` and `STAFF`.** One company per user still applies (D6). **Supersedes D26 and amends D64** ("one owner is enough").<br>• The owner adds staff by email. The person must be an existing registered user with no company. There is no invite email.<br>• The owner can deactivate staff.<br>• **Owner only:** staff management, contact edits, generating units and downloading labels, and voiding units.<br>• **Staff:** merchant events, the dashboard, alert notes and alert status. | Several people work the till and the warehouse. Codes and labels are the most sensitive actions, so only the owner can do them. |
| D107 | **New product fields:**<br>• `size`.<br>• `attributes`: a JSON object with at most 20 keys and string values.<br>• `gtin`: optional; 8, 12, 13 or 14 digits; must have a valid GS1 check digit; unique per company.<br>`registration_number` stays optional and not unique. It is shown as "NAFDAC number (as printed)" and is never checked.<br>Only approved manufacturers create products and batches; D61 still applies. Change notices may change size, attributes, gtin and registration number. **Amends D61, D68 and D81.** | The data model stays GS1-compatible (concept doc §6E). Products belong to manufacturers. |

### Identity

| # | Decision | Reason |
|---|---|---|
| D108 | **QR token:**<br>• Each unit and each carton gets a token from `secrets.token_urlsafe(16)`, which is 128 bits.<br>• The QR encodes `{PUBLIC_BASE_URL}/p/{token}`.<br>• Only `sha256(token)` (hex) is stored, under a unique constraint. Generation retries on a collision.<br>• The token is never derived from IDs, sequences or timestamps. | It cannot be guessed or enumerated (concept doc §7, Layer 1). A leaked database does not reveal printable tokens. |
| D109 | **Hidden scratch code:**<br>• **Format:** 16 Crockford Base32 characters (`0-9 A-Z` without `I L O U`), printed in groups of 4, then one **Luhn mod-32** check character from the same alphabet. Layout: `XXXX-XXXX-XXXX-XXXX-C`.<br>• **Tolerant input:** lowercase is accepted, hyphens and spaces are ignored, `O` is read as `0`, and `I` or `L` as `1`.<br>• **Browser check:** the browser validates the check character before calling the API.<br>• **Storage:** `HMAC-SHA256(CODE_HASH_PEPPER, normalised code)`, under a unique constraint, with a retry on collision. (Q2, Q7) | The standard Crockford check uses mod 37 with `* ~ $ = U`. Those are hard to type, and `U` breaks the "no U" rule. Mod 32 catches every single-character error and most swaps. The code has 80 bits of entropy, so a peppered hash keeps a leaked database without the env secret useless. |
| D110 | **Raw codes exist only at generation:**<br>• **Generation:** units for a batch are created in one transaction, at most 2,000 per request, optionally in cartons of N.<br>• **Download:** the response streams a one-time zip with a label PDF and a printer CSV. The PDF shows the QR, a scratch-panel area with the hidden code, "Check at {LABEL_CHECK_DOMAIN}", and the base URL in the footer.<br>• **No copies:** nothing raw is stored or logged. The page warns that the file holds every raw code and must be kept secure and deleted after printing.<br>• **Trade-off:** a lost file cannot be downloaded again. Instead, the owner **voids** the unreleased units and generates new ones. A void writes a `VOIDED` event with actor, time and a required reason, plus an audit entry.<br>• **Limits:** released units cannot be voided (409); use a recall instead. A voided code returns `INVALID_IDENTITY` and raises rule 9 (D124). (Q3) | Keeps the "hashes only" promise. The void path makes the trade-off workable, and rule 9 detects leaked label files. |
| D111 | **Amended by D136 (2026-10-22).** **Demo seed scenario (Phase 8):**<br>• **Cast:** one manufacturer, two products, one batch of about 50 units in cartons, one distributor, two retailers in different cities, and one POS partner.<br>• **Cases with an alert:** sold in Lagos then scanned in Kano 3 hours later; hidden code claimed in Lagos then entered in Abuja; a burst of invalid codes.<br>• **Cases without an alert:** a POS sale then a buyer rescan (just sold); a refund; never-sold units.<br>• **Other cases:** a recalled batch; one deliberately unreleased carton, labelled as a test case. Every other batch is released.<br>• **Built through the services**, so alerts come from the rules.<br>• **Exception to D108/D109:** scenario units use a few fixed raw codes from `demo_data.py`, so the README can print them. They are hashed like any other code. The production generator never accepts codes from a caller.<br>**Supersedes D5 and D53.** | The demo needs codes people can type. The exception stays inside the seed. |

### Lifecycle

| # | Decision | Reason |
|---|---|---|
| D112 | **Amended by D134 (2026-10-22).** **Append-only lifecycle events:**<br>• **Types:** `ISSUED, RELEASED, TRANSFERRED, RECEIVED, SOLD, RETURNED, SALE_CORRECTED, CLAIMED, RECALLED, VOIDED`.<br>• **Sources:** `MANUFACTURER, MERCHANT_APP, POS_API, CONSUMER_CHECK, SYSTEM`.<br>• **Recorded on each event:** actor user, actor company, POS partner and till, area, `occurred_at`, `recorded_at`, and optional transaction and payment references.<br>• **Derived fields:** `product_unit.lifecycle_status` (`ISSUED, RELEASED, IN_TRANSIT, IN_STOCK, SOLD, RECALLED, VOIDED`) and `current_holder_company_id`. Only `services/lifecycle.py` writes them, in the same transaction as the event, by replaying events in `occurred_at` order. This keeps late offline POS events correct.<br>• **Cartons** have one level. A carton event writes one carton row plus one row per unit, all sharing a `group_id`.<br>• **`SALE_CORRECTED`** needs a reason. It references the SOLD event it corrects (`corrects_event_id`) and never deletes it.<br>• **RETURNED and SALE_CORRECTED** put the unit back IN_STOCK at the retailer. | One audited history. Status can always be explained from the events. |
| D113 | **Custody is lenient but labelled:**<br>• An approved distributor or retailer may record RECEIVED or SOLD on a released, unsold, unrecalled and unvoided unit even with no TRANSFERRED to it. The timeline shows "received without a recorded transfer".<br>• TRANSFERRED is allowed only by the current holder, or by the manufacturer for a released unit it still holds. The receiver must be an approved company.<br>• Two companies recording RECEIVED or SOLD for one unit with no transfer between them raises rule 8 (D124). (Q1) | Informal supply chains skip steps, and strict custody would collapse sales coverage. The rule catches the pattern that a copied code produces. |
| D114 | **CLAIMED is a consumer-check event:**<br>• The first check of a hidden code writes `CLAIMED` (source `CONSUMER_CHECK`, no actor) and sets `secret_claimed_at` and `secret_claimed_area_id`.<br>• It never changes `lifecycle_status` or the sale status.<br>• Later checks show "first checked on {date} in {area}". | The concept doc §7 says a consumer scan cannot change lifecycle state. CLAIMED is evidence, not a status change. |

### Consumer check

| # | Decision | Reason |
|---|---|---|
| D115 | **Amended by D135 (2026-10-22).** **Check results: one main result plus details.** The main result is the first that applies:<br>1. `INVALID_IDENTITY`: unknown, voided, or from a manufacturer that is not approved.<br>2. `SUSPICIOUS_ACTIVITY` (D116).<br>3. `BATCH_OR_PRODUCT_WARNING`: an active recall.<br>4. A recognised state:<br>• `RECOGNISED_JUST_SOLD`: SOLD at or after `now − JUST_SOLD_WINDOW_HOURS` (env, default 6, inclusive). "Just sold by {retailer}, {area}, at {time}. If that was your purchase, this matches."<br>• `RECOGNISED_PREVIOUSLY_SOLD`: an older sale. "This code was already recorded as sold on {date} in {area}", with advice to ask the seller or choose another pack, and Report a concern.<br>• `RECOGNISED_NOT_SOLD`: "This code was issued by {manufacturer} and is in circulation", with the tip "Scan again after you pay. It should show this item as just sold by the shop."<br>**Other details:**<br>• An expired batch adds a warning.<br>• When no sale is recorded, an optional "I've bought this" shows "No sale recorded yet. Some shops don't record sales on FoodLens yet. This isn't a warning by itself." It changes nothing.<br>• Every result shows: product, manufacturer, batch, expiry, the NAFDAC number as information, recorded events in plain words, recalls and notices, Report a concern, the demo banner, and the note that no QR system catches every copied code. Recorded facts and possible patterns are labelled separately.<br>• A carton QR shows "This is a carton code; check the individual pack." | Prompt §5 and concept doc §3.2. The before/after-purchase messages turn a buyer's own purchase into evidence. |
| D116 | **When the main result is `SUSPICIOUS_ACTIVITY`:** the unit has a MEDIUM or HIGH alert that is OPEN or INVESTIGATING (including one raised by this scan), or any alert resolved as RESOLVED_SUSPECTED_COPY.<br>• LOW alerts show only on the dashboard.<br>• RESOLVED_LEGITIMATE clears the result.<br>• An unreleased unit checked in public is suspicious through rule 7. (Q4, Q6) | Does not alarm a buyer who scans at home in another city the next day (rule 1 is LOW). Unreleased stock should not be in shops. |
| D117 | **Ways to check.** `/check` keeps "Scan pack" with three inputs:<br>• **Scan QR:** an in-browser QR reader, self-hosted as in D89, using `BarcodeDetector` where available.<br>• **Scan secret code:** the D88 OCR, retargeted to the Crockford format. Its whitelist is the 32 symbols plus hyphen.<br>• **Type code.**<br>**`/p/{token}`** works from any phone camera. It records nothing on GET and verifies through a client-side `POST /api/check/qr`, so link-preview bots and prefetching never create scans.<br>Hidden codes use `POST /api/check/secret`. Images never leave the phone.<br>**Supersedes D85 and D91; amends D88 and D94** (the confirm screen now confirms the hidden code). | A WhatsApp preview fetched from another city would otherwise trigger rule 2. |
| D118 | **Location and privacy:**<br>• **What a scan stores:** only a coarse `area_id` (city or state).<br>• **Where the area comes from:**<br>  1. Cloudflare visitor-location headers (`cf-ipcity`, `cf-region`), trusted only under the D90 conditions.<br>  2. Otherwise an offline DB-IP Lite lookup.<br>  3. Otherwise, with `SIMULATE_LOCATION_ENABLED=true` (demo only, off by default), a chosen demo city.<br>  The IP is then discarded.<br>• **`scan_event` columns:** no IP, user agent, cookie, device ID, GPS or account column. A test checks the exact column list.<br>• **Retention:** scan rows are deleted after 12 months by `python -m app.jobs.purge`, run daily. Alert evidence keeps a snapshot, so it survives the purge.<br>• **Access by role:**<br>  - Consumers see only their own result.<br>  - Manufacturer members see scans, events, alerts and reports for their own units.<br>  - Distributors and retailers see the events they recorded and the units they hold.<br>  - Admins see platform totals, invalid-burst alerts and consumer reports.<br>  - POS partners see only the D121 lookup fields.<br>• **NDPA:** under the Nigeria Data Protection Act 2023, an IP address is personal data while it is processed. FoodLens uses it only to derive a coarse area, on the basis of legitimate interest in fraud detection. It stays in memory and no identifier is stored.<br>• **Cloudflare:** Cloudflare sees visitor IPs at its edge, outside FoodLens's storage, and the privacy notice says so. The deployment runbook checks that "Add visitor location headers" is switched on. A health check reports only whether `cf-ipcity` arrives.<br>**Supersedes D46 (and D8).** | Data minimisation and retention (concept doc §8). Cloudflare places Nigerian mobile users better than IP databases, which often see everyone as Lagos. |
| D119 | **Rate limits:**<br>• Check endpoints use the D40 consumer bucket.<br>• POS has a token bucket per partner (`RATE_LIMIT_POS_BURST`, `RATE_LIMIT_POS_REFILL_PER_SECOND`).<br>• Consumer reports: 5 per hour per IP.<br>• Counters stay in memory only.<br>**Amends D39 and D40.** | Resists enumeration, and stops partners starving each other. |
| D120 | **Consumer reports** are anonymous:<br>• **Fields:** an optional unit, the concern type, a description (at most 1,000 characters) and the area.<br>• **Visible to:** only the unit's manufacturer and admins.<br>• **Status:** `NEW, REVIEWED, CLOSED`.<br>• **No contact field.** An opt-in phone number is a stretch item. | Concept doc §3.2. Consumers stay anonymous. |

### POS integration

| # | Decision | Reason |
|---|---|---|
| D121 | **Amended by D134 and D135 (2026-10-22).** **POS API (`/api/pos/v1`):**<br>• **Partners and secrets:** admins create partners. API keys and the signing secret are each shown once. Keys are stored as a SHA-256 hash plus a display prefix, and can be revoked. The **signing secret is Fernet-encrypted** with env `POS_SECRET_KEY`, because verifying an HMAC needs the raw secret.<br>• **Headers:** `X-FoodLens-Key`; `X-FoodLens-Timestamp` (Unix seconds); `X-FoodLens-Signature`, the hex `HMAC-SHA256(secret, "{timestamp}.{raw_body}")`.<br>• **Rejected:** unsigned requests, invalid signatures, and stale requests (more than `POS_MAX_SKEW_SECONDS`, default 300, either way).<br>• **Retailer and till:** each request names `retailer_id` and `till_id`. The retailer must be approved, flagged as a retailer, and linked to the partner. The till must be registered to a reviewed location, which gives the area.<br>• **`units/lookup`:** QR token → product, GTIN, batch, expiry, status, and a warning flag when the unit is sold, recalled, unreleased, voided or alerted. It never changes anything.<br>• **`sales`:** `transaction_id`, `payment_reference`, `retailer_id`, `till_id`, `occurred_at`, `units[]`. Creates SOLD events (source `POS_API`) and returns a per-unit error list. Idempotent on (partner, transaction, unit, event type). Late offline events are accepted up to `POS_MAX_EVENT_AGE_DAYS` (default 7).<br>• **`refunds`:** creates RETURNED.<br>• **`voids`:** creates SALE_CORRECTED with a reason.<br>• **No payment data:** no amounts, card or customer data are stored.<br>Docs: `docs/POS_INTEGRATION.md`. (Q7) | Signing the timestamp together with the body stops replay of a captured body under a fresh timestamp. A sale is recorded only after the POS confirms payment. |
| D122 | **CLAUDE.md rule 6 reworded:** POS calls carry only an opaque `payment_reference` (at most 100 characters) and a transaction ID. No amounts, card, customer or checkout data. | Resolves the conflict between "no payment fields" and `payment_reference`. |
| D123 | **Simulated POS:** `/demo/pos` (with `DEMO_POS_ENABLED=true`, off by default) calls `/api/demo/pos/*`. That endpoint signs with the seeded partner's secret on the server and goes through the same verification path. The browser never holds a secret. | A demo till that does not leak a signing secret. |

### Risk rules

| # | Decision | Reason |
|---|---|---|
| D124 | **Amended by D132, D133 and D135 (2026-10-22).** **Deterministic, explainable risk rules:**<br>• **When they run:** synchronously on each check and on each POS call.<br>• **Thresholds:** set in env. Changing a default needs the founder's approval.<br>• **"Different area":** the area centroids are more than `RISK_DIFFERENT_AREA_KM` apart (default 50).<br>**Default rules:**<br>1. Scan after a recorded sale, in a different area, beyond the just-sold window. **LOW.**<br>2. The same identifier in two areas more than 100 km apart, at an implied speed above `RISK_MAX_TRAVEL_KMH` (default 120). **HIGH.**<br>3. More than `RISK_SCAN_VOLUME` checks (default 10) of one identifier in 24 hours. **MEDIUM.**<br>4. At least `RISK_INVALID_BURST` invalid identifiers (default 20) from one area in 10 minutes. **MEDIUM**, admin only.<br>5. Hidden code checked in a different area after CLAIMED. **HIGH.**<br>6. POS lookup or sale attempt on a unit already sold, recalled or voided. **MEDIUM.**<br>7. Unreleased unit checked by a consumer. **MEDIUM.**<br>8. Two companies record RECEIVED or SOLD for one unit with no transfer between them. **MEDIUM.**<br>9. Voided code checked ("voided code in use: possible leaked label file"). **HIGH.**<br>**Evidence:** each alert stores event IDs, scan IDs, a snapshot and a plain-words explanation.<br>**De-duplication:** there is only one OPEN or INVESTIGATING alert per (rule, unit); new evidence is appended to it.<br>**No alert for:** a buyer rescanning in the same area within the window, returns, or carton moves. | Concept doc §3.4 and §9: first versions are rule-based and reviewable. Alerts are signals, not verdicts. Rules 7–9 come from Q6, Q1 and Q3. |
| D125 | **Alert workflow:**<br>• **States:** `OPEN → INVESTIGATING → RESOLVED_LEGITIMATE` or `RESOLVED_SUSPECTED_COPY`. A resolved alert can be reopened.<br>• **Who:** members of the unit's manufacturer and admins change the status and add notes.<br>• **Recorded:** resolving sets `resolved_by` and `resolved_at`. Every change writes an audit entry. | An investigation trail (concept doc §3.5). |

### Recalls, hidden features, wording and domain

| # | Decision | Reason |
|---|---|---|
| D126 | **Recalls:**<br>• Announcements gain `kind` (`NOTICE`, `RECALL`) and an optional `batch_id`, so a recall targets a product or a batch.<br>• A recall goes live without review (the D75 exception) and adds `RECALLED` events to the affected units in the same transaction.<br>• Admins can hide a recall only with a reason; the events stay.<br>• Recall text follows D77 and D86. | Manufacturers must reach buyers quickly, and the events keep the recall visible to POS and in the timeline. |
| D127 | **Hidden features:**<br>• **Wholesale orders** (D95–D99, D101) stay in the code. Their routers register only when `ORDERS_ENABLED=true` (default false). They are taken out of navigation and marked as future work. Tests run with the flag on.<br>• **The supplier directory** stays public as the **"Partner directory"**, without register results. **Supersedes the register part of D100.** (Q8) | Keeps finished work without distracting from the new core. |
| D128 | **Banned words.** FoodLens's own wording never uses the whole words `original`, `genuine`, `authentic`, `safe`, `unsafe` or `fake`, in any case. Tests scan every check response and the frontend copy. The company announcement rules stay as D77 and D86. **Extends D52 and D84.** | A recognised code is not proof about the physical item. |
| D129 | **Domain.** The planned public domain is **`foodlens.online`** (the founder will buy it). It is set through `PUBLIC_BASE_URL` and `LABEL_CHECK_DOMAIN` and is never hard-coded. Labels generated before the domain is live use the dev or tunnel URL; the PDF footer shows which base URL was used. | QR codes are permanent once printed. |
| D130 | **Phases.** The phases are replaced by `docs/PLAN.md` phases 1–11, each with one session and one commit. **Stretch, after everything else:** opt-in simulated rewards when a hidden code is claimed (a phone number only if the consumer opts in), and results in local languages. **Supersedes D102.** | Founder instruction (2026-10-21). |

## Geo-batching and return dispositions (2026-10-22)

Founder additions made before Phase 1. Every entry below is **Decided (2026-10-22)**.

| # | Decision | Reason |
|---|---|---|
| D131 | **Batch allocations (geo-batching).** After generating units, the manufacturer's owners and staff split a batch into `batch_allocation` rows. Each row has: an optional destination company (an approved distributor or retailer), a required destination area, a quantity (> 0), a planned date, and an optional carton list (`allocation_carton`; a carton sits in at most one allocation). The allocated total never exceeds the issued units.<br>**Matching a unit to its allocation:** a unit in a listed carton belongs to that carton's allocation. Otherwise a receipt matches any allocation of the batch to that company or area that has quantity left. A batch with no allocations is never outside its allocation.<br>**Inventory view** per destination and area: allocated, received, in stock, sold, and returned (split by disposition). It is computed from events and nothing is stored. | Manufacturers plan where stock should go, and goods turning up elsewhere is a diversion or copy signal. |
| D132 | **Rule 10, "received outside its allocation".** A RECEIVED event (unit or carton) by a company or in an area that differs from the allocation sets `outside_allocation` on the event. The timeline shows "received outside its allocation", and a **LOW** alert is raised. The evidence includes the allocation. | Visible to the manufacturer without alarming consumers (D116: LOW stays on the dashboard). |
| D133 | **Rule 11, "outside allocated area".** A SOLD event or a consumer check whose area is more than `RISK_OUTSIDE_ALLOCATION_KM` (env, default 150) from the unit's allocated area raises an alert. It is **MEDIUM** when the same unit has another open alert or another rule fires on the same event, and **LOW** otherwise. The evidence includes the allocation. Units with no allocation are skipped. | Distance from the planned market is a diversion signal. On its own it is weak, because buyers travel. |
| D134 | **Return dispositions.**<br>• **Who:** RETURNED is accepted only from the company that recorded the standing SOLD event, or from a POS partner linked to that retailer. Anyone else gets 403.<br>• **Disposition:** each return needs one. `RESTOCK` (back on sale) sets IN_STOCK at the seller, clears `last_sold_*`, and counts the unit in inventory again. `NOT_FOR_RESALE` (opened or damaged) sets the new final status `WITHDRAWN`: no later sale, receipt or transfer.<br>• **History:** the SOLD event and the return both stay in the timeline. The return references the sale (`returns_event_id`).<br>• **Claimed codes:** if the unit's hidden code was CLAIMED, RESTOCK is refused (409) and the return must be NOT_FOR_RESALE.<br>• **POS refunds** carry the disposition.<br>• **Risk rules** ignore a sale that a valid return followed.<br>**Amends D112 and D121.** | A restocked unit must look unsold to its next buyer. A claimed code is spent, so that unit cannot go back on sale. |
| D135 | **Check results after returns.** A restocked unit gives `RECOGNISED_NOT_SOLD` with the text "In circulation, not yet sold". A withdrawn unit gives a new recognised state, `RECOGNISED_WITHDRAWN`: "Returned to the shop and withdrawn from sale", with Report a concern. It ranks with the other recognised states, below `BATCH_OR_PRODUCT_WARNING`. POS lookup flags a withdrawn unit, and a POS sale of one returns a per-unit error and raises rule 6. **Amends D115, D121 and D124.** | The founder supplied the wording. A new result keeps "withdrawn" distinct from "sold". |
| D136 | **Seed additions.** One batch is split between Lagos and Kano allocations. One retailer gets a reviewed Abuja location, and one Lagos-allocated unit is sold there to trigger rule 11. The scenario test also expects rule 11 on the existing Kano-scan and Abuja-claim cases, at MEDIUM there because rules 2 and 5 fire too. **Amends D111.** | Demonstrates geo-batching. Existing cases now carry an allocation signal as well. |
