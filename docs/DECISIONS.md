# FoodLens decisions

Open choices from Section 13 of the handoff and answers to the pre-Phase-0 questions. Change any row by editing it and noting the date.

## Open choices (handoff §13)

| # | Choice | Decision | Status |
|---|---|---|---|
| D1 | Frontend framework | Next.js (App Router) + TypeScript + Tailwind + TanStack Query + Zod | Decided |
| D2 | PostgreSQL vs SQLite | PostgreSQL for dev, tests, and demo (via Docker Compose) | Proposed |
| D3 | Lookup input method | Manual product code + batch entry first. Optional QR holding an opaque FoodLens URL as stretch. No OCR. | Proposed |
| D4 | Consumer concern reports | Stretch (Phase 8), not MVP | Proposed |
| D5 | Seed data volume | 3 categories, 4 companies (2 manufacturers, 1 wholesaler, 1 both), ~10 products, ~25 batches, 2 agencies (NAFDAC simulated, SON/MANCAP simulated), 5 locations. Includes expired, inactive, mismatch, no-credential, pending, and not-found cases. | Proposed |
| D6 | Multiple users per company | Yes, via `COMPANY_MEMBER`. One company per user in MVP. | Proposed |
| D7 | Change-notice attachments | PDF, PNG, JPEG only; max 5 MB; private local storage; admin and owning company can download | Proposed |
| D8 | Scan logs | Off by default. If enabled, no user, IP, or location link. | Proposed |
| D9 | Fulfilment batch allocation | In MVP (Phase 7), simple allocation without inventory tracking | Proposed |
| D10 | Order status lifecycle | `SUBMITTED` → `ACCEPTED` or `DECLINED`; `ACCEPTED` → `FULFILLED`; buyer may cancel (`CANCELLED`) while `SUBMITTED`. Seller replies are notes on the order. | Proposed |
| D11 | Supplier-location review checklist | Address and area present; linked to an approved company; named contact representative; reviewer and timestamp recorded | Proposed |

## Implementation defaults

| # | Choice | Decision | Status |
|---|---|---|---|
| D12 | Auth mechanism | FastAPI httpOnly cookie session; bcrypt hashing; Next.js rewrites `/api/*` to FastAPI | Decided (2026-10-07) |
| D13 | Admin model | `is_admin` flag on `APP_USER`, set only by seed/CLI (not the separate `ADMIN_USER` table in the old ERD) | Proposed |
| D14 | DB session style | Sync SQLModel sessions | Proposed |
| D15 | Frontend tests | Vitest + Testing Library; Playwright E2E in Phase 9 | Proposed |
| D16 | Phase numbering | Gate + phases 0–9; handoff §12 step 8 split into supplier discovery (6) and order requests (7) | Proposed |

## Answers to pre-Phase-0 questions (2026-10-07)

### Q1 — Docs and ERD
Decided by Claude at the student's request ("do what is best").
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

### Q4 — Lookup result precedence
Each lookup returns one primary `result` plus a `warnings` list so secondary conditions are still shown. Checked in this order:

1. Input empty, malformed, or matching more than one record: `INSUFFICIENT_OR_AMBIGUOUS`.
2. Product code not found, or batch not found under that product (including batches that are pending or rejected): `BATCH_NOT_FOUND`. If the batch number exists under a different product, return `DETAILS_MISMATCH` with the differing field (`product_code`).
3. Batch expiry date has passed: `BATCH_EXPIRED` (new state). Message: "The expiry date stored for this batch in the demo data has passed."
4. Product has approved credentials but all are expired or inactive: `CREDENTIAL_EXPIRED_OR_INACTIVE`.
5. Product has no approved credential record: `DETAILS_MISMATCH` with differing field `credential`. Message says no credential record matches this product in the demo data. (Student's choice: mismatch rather than not-found, since the batch does exist.)
6. Otherwise: `DEMO_RECORD_FOUND`.

Every response carries `data_mode: "DEMO"` and the disclaimer regardless of result.

### Q5 — Company-entered credentials
Hidden from consumer lookups until an admin approves them.

### Q6 — Buyer approval
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

Changes to the draft ERD, all approved by the student. Implemented in migration `0002_initial_schema`; described in `docs/SCHEMA.md`.

| # | Decision | Reason |
|---|---|---|
| D17 | Change notice targets are four optional FKs (`product_id`, `batch_id`, `credential_id`, `location_id`) with a check that exactly one is set. Replaces `target_type` + `target_id`. | The database rejects notices pointing at records that do not exist. |
| D18 | `PRODUCT_ANNOUNCEMENT` has no `company_id`; the company comes from the product. | Avoids two copies of ownership that could disagree. |
| D19 | Credentials are product-level only; the `scope` / batch-specific option is removed for the MVP. | A batch-specific credential needs a batch link the model did not have; matches non-negotiable rule 3. |
| D20 | Database checks: quantities > 0, attachment size 1 byte–5 MB, `valid_until >= valid_from`, `expiry_date >= production_date`, buyer ≠ seller. | Enforce simple invariants even if a service has a bug. |
| D21 | Company-asserted identity fields are prefixed `claimed_` (`claimed_legal_name`, `claimed_business_identifier`, `claimed_address`). | Keeps claimed data visibly separate from reviewed fields. |
| D22 | All reviewable tables (company, product, batch, credential, location, change notice) share `review_status` / `status`, `reviewed_by_user_id`, `reviewed_at`, `review_note`. | One review pattern for services and tests. |
| D23 | **Superseded by D61 (2026-10-09).** Publishing a product needs admin review: `DRAFT → PENDING_REVIEW → PUBLISHED / REJECTED`, plus `WITHDRAWN`. | Without it a company could put any product in front of consumers unreviewed. Extends non-negotiable rule 4. |
| D24 | `USER_SESSION` table holds hashed session tokens with expiry and revocation. | Server-side sessions can be revoked on logout; JWT cookies cannot. |
| D25 | `COMPANY_MEMBER` gains `is_public_contact`, `public_title`, `public_phone`, `public_email`. | Supplier pages can name representatives without exposing login emails. |
| D26 | Member roles are `OWNER` and `REPRESENTATIVE` only. | `STAFF` had no distinct permissions. |
| D27 | `created_at` on every table; `updated_at` only on edited tables. Append-only tables (`audit_log`, `change_notice_field`, `notice_attachment`, `order_line`, `order_batch_allocation`, `user_session`) have none. | Makes immutability visible in the schema. |
| D28 | Enums stored as `VARCHAR` + `CHECK`, not native PostgreSQL enums. | Native enums need awkward migrations to add values. |
| D29 | `BATCH_SCAN` and `CONCERN_REPORT` are deferred to Phase 8's migration. They stay in `ERD.mmd`, marked Phase 8. | Optional features; no empty tables until needed. |
| D30 | `docs/PLAN.md` Phase 1 is now "Data model"; identity/roles moved to the start of Phase 2. | The whole schema was built in one phase at the student's request. |

## Auth decisions (2026-10-08)

Implements D12 (httpOnly cookie session, bcrypt) and D24 (`USER_SESSION` table). Code: `backend/app/core/security.py`, `core/auth.py`, `services/auth.py`, `routers/auth.py`.

| # | Decision | Reason |
|---|---|---|
| D31 | Passwords: bcrypt (12 rounds; 4 in tests only), 10 characters minimum, 72 bytes maximum (bcrypt's limit; longer passwords are rejected, not truncated). | Matches D12; rejection avoids silently ignoring part of a password. |
| D32 | Session token: 32 random bytes in a cookie named `foodlens_session`; only its SHA-256 hash is stored. Cookie is `HttpOnly`, `SameSite=Lax`, `Path=/`, `Secure` when `SESSION_COOKIE_SECURE=true`. Sessions last 24 hours. | A leaked database row cannot be replayed as a cookie. Lax blocks the cookie on cross-site POSTs (basic CSRF protection). |
| D33 | Logout revokes the session in the database and clears the cookie; deactivating a user ends all their sessions. | Server-side revocation is the reason for D24. |
| D34 | Login failures (unknown email, wrong password, inactive account) all return 401 "Invalid email or password", and unknown emails still run a bcrypt check. | Does not reveal which accounts exist, by message or timing. Registration still returns 409 for a taken email, an accepted trade-off for a demo. |
| D35 | Registration reads only `email`, `password`, `display_name`; any other field (e.g. `is_admin`, `is_active`, `review_status`, `user_id`) is ignored, not rejected. Email is stored lowercased. Registration signs the user in. | Student's instruction; the service takes explicit keyword arguments, so mass assignment is impossible. |
| D36 | Admins are created only by `uv run python -m app.seed` from `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD`. An existing account with that email is promoted; its password is not changed. | No API path can grant admin. |
| D37 | Dependencies: `current_user` (401), `require_admin` (403), `require_company_member(*roles)` (403; needs a `company_id` path parameter; admins do not pass as members). | One place for authorization checks; admins act through admin routes. |
| D38 | Not in scope yet: password reset, email verification. (Login rate limiting added in D41.) | Out of capstone MVP scope; listed so the report can name them as limitations. |

## Rate limiting (2026-10-08)

Approved by the student. Code: `backend/app/core/rate_limit.py`. All values configurable in `backend/.env`.

| # | Decision | Reason |
|---|---|---|
| D39 | Limits are per client IP address only (login adds the email). No cookies, fingerprinting, or per-consumer identifiers. Counters live in process memory, are never stored or logged, and are dropped once refilled. | Keeps consumer lookups anonymous. |
| D40 | Product lookups use a token bucket: burst 20, refill 1 per second (about 60 per minute) per IP. | Several consumers on shared Wi-Fi are not blocked; sustained scraping is. |
| D41 | Login: 5 per minute per IP + email. Registration: 5 per hour per IP. Both are token buckets (burst = the number, refilling evenly over the period). Login is checked before the password. | Limits password guessing and bulk account creation. Closes the rate-limiting part of D38. |
| D42 | `RATE_LIMIT_EXEMPT_IPS` (IPs or CIDR ranges, empty by default) is never limited; `RATE_LIMIT_ENABLED=false` turns limits off. Invalid entries stop the API at startup. | Usability-test sessions from one room must not be blocked. |
| D43 | Over the limit: HTTP 429 with a `Retry-After` header (whole seconds). The frontend explains the limit is shared by everyone on the same network and says when to retry. | Users understand it is not their fault and how long to wait. |
| D44 | Client IP: the connecting address, or, when the connection comes from `TRUSTED_PROXY_IPS` (the Next.js server), the right-most `X-Forwarded-For` entry that is not a trusted proxy. Limits are per API process. | The browser reaches FastAPI through the Next.js `/api` proxy. Several API processes would need a shared store (e.g. Redis). |
| D45 | `next dev` / `next start` keep a client-supplied `X-Forwarded-For` (`??=` in Next.js 16.4 `base-server.js`; the rewrite proxy does not append), so a forged header could dodge the limits. **Fixed** with a custom server, `frontend/server.mjs`, which replaces `X-Forwarded-For` with the real connection address (and drops `Forwarded`) before Next.js runs. `npm run dev` / `npm run start` use it. IPv4-mapped addresses (`::ffff:a.b.c.d`) are normalised on both sides. If a CDN or reverse proxy is ever placed in front of the web server, `server.mjs` must trust it instead, or all visitors share its IP. | Verified end to end from the LAN address: before the fix forged headers were never limited; after it the 6th login attempt got 429 with `Retry-After` despite a new forged IP on every request. |

## Consumer lookup (2026-10-08)

Code: `backend/app/services/lookup.py`, `routers/lookups.py`, `demo_data.py`; `frontend/components/lookup/`.

| # | Decision | Reason |
|---|---|---|
| D46 | Every lookup writes an anonymised `BATCH_SCAN` row: normalised input, matched batch (if any), result, time. No user, session, IP, user agent, or location. **Supersedes D8** (scan logs off by default) and brings that part of D29 forward, at the student's request. | Usage evidence for the evaluation without identifying anyone. |
| D47 | Six lookup states, not five: `BATCH_EXPIRED` kept from Q4 / non-negotiable rule 1 although the build request listed five. No approved credential returns `DETAILS_MISMATCH` (field `credential`), per Q4. | Follows recorded decisions; reversible if the student prefers five. |
| D48 | Product code is required to show a record. Batch number alone returns `INSUFFICIENT_OR_AMBIGUOUS` with the matching products as candidates (name, brand, code only) so the user can choose; choosing resubmits with the code. | Handoff §5: "ask for correction or manual selection"; a batch number alone never reveals a record. |
| D49 | Only approved batches of published products of approved companies, and approved credentials, are visible. Anything else looks like `BATCH_NOT_FOUND` (or no credential). | Rules 4-5 and Q5: unreviewed data never reaches consumers. |
| D50 | Input is trimmed, inner whitespace collapsed, upper-cased; max 64 characters of letters, digits, space and `- . / _`; otherwise `INSUFFICIENT_OR_AMBIGUOUS`. A mismatch on product code does not reveal which product owns the batch. | Tolerant of how people type codes; no data leakage. |
| D51 | Credential status shown is computed on the lookup date: `ACTIVE_IN_DEMO_DATA`, `EXPIRED_IN_DEMO_DATA` (past `valid_until`), `INACTIVE_IN_DEMO_DATA` (stored inactive), `NOT_YET_VALID_IN_DEMO_DATA` (before `valid_from`, counts as not active). One active credential is enough for `DEMO_RECORD_FOUND`; others not active add a warning. A batch expiring today is not expired. | One consistent rule for every response. |
| D52 | Result screen uses neutral colours (no green/red), repeats the demo banner inside every result, labels each credential "Product-level · Demo data", and shows the scope note "not to this batch … not a batch certificate or a test result". The banned-word check is whole-word (`safe`, `unsafe`, `fake`); the disclaimer's "food-safety test" is allowed. | Rules 1-3: a result describes a demo record, never fitness to eat. |
| D53 | Demo seed (`uv run python -m app.seed`): 4 fictional companies (1 pending), 8 products (1 draft), 11 batches (1 pending, 1 expired, 1 lot number shared by two products), NAFDAC (simulated) and SON MANCAP (simulated), 8 credentials (1 expired, 1 inactive, 1 pending). Dates are relative to the seeding day. `SEED_CASES` documents one lookup per state and is tested through the API. | Satisfies D5 at a smaller size; every state is demonstrable. |

## Companies, admin review, and supplier directory (2026-10-08)

Code: `backend/app/services/companies.py`, `services/suppliers.py`, `routers/companies.py`, `routers/admin.py`, `routers/suppliers.py`; `frontend/components/{company,admin,suppliers}/`.

| # | Decision | Reason |
|---|---|---|
| D54 | `POST /api/companies`: a signed-in user with no company creates a company in `PENDING_REVIEW` and becomes its `OWNER`. Only company fields are read; review status, reviewer, and IDs sent by the client are ignored. A user already in a company gets 409; admin accounts get 403. | Rule 4 and D21; one company per user (D6); admins stay neutral reviewers. |
| D55 | Company transitions: approve from `PENDING_REVIEW` or `SUSPENDED` (reinstate); reject from `PENDING_REVIEW`; suspend from `APPROVED`. Anything else is 409. Each decision sets reviewer, time, optional note, and writes `audit_log`. | Clear lifecycle; every decision attributable. |
| D56 | Admins can never review a company (or its locations) they are a member of: 403. | No self-approval, even for admins. |
| D57 | Supplier locations can be added only by members of an approved company and start `PENDING_REVIEW`. Admin can mark demo-reviewed (approve) or reject, only from pending, and only approve while the company is approved. A named contact is optional; if given it must be an active member of the same company. Editing reviewed locations is left to change notices (Phase 5). | Rule 5. D11's "named contact" is not enforced yet because D11 is still Proposed. |
| D58 | `GET /api/suppliers` is public, at the student's request (the handoff had wholesalers signing in). It lists approved companies that have at least one demo-reviewed location, shows only those locations, the company's public contact details, and members who opted in as public contacts. It never shows claimed fields, review notes, or login emails. | Rules 4 and 7; privacy of claimed data and accounts. |
| D59 | Badge text is exactly "FoodLens demo-reviewed profile", always with the note "Reviewed for the FoodLens demonstration database only. This is not a NAFDAC or SON approval, and it does not verify the company's identity or products." | Rule 4 wording. |
| D60 | Seed adds five fictional locations: three reviewed (Demo Harvest ×2, Sample Springs) and two pending (Example Grain Mills, Pending Demo Snacks), so the directory shows two suppliers. | Demonstrates both listed and hidden cases. |

## Company catalogue (2026-10-09)

Student decision: keep the catalogue simple. Code: `backend/app/services/catalogue.py`, `routers/catalogue.py`; `frontend/components/company/Catalogue.tsx`.

| # | Decision | Reason |
|---|---|---|
| D61 | Approved companies publish new products and batches directly: products are `PUBLISHED` and batches `APPROVED` on creation, with no admin step. **Supersedes D23** and the "new batches stay pending" part of rule 5. Pending, rejected, or suspended companies cannot add products (409), and their products are hidden from lookups anyway. | Less friction for companies; the credential review (D63) still stops unreviewed data from looking trustworthy. |
| D62 | A batch with `review_status = APPROVED` and no reviewer means "published by the company". Product codes, batch numbers, and credential references are stored normalised (trimmed, upper-case) and must be unique case-insensitively: product code across the catalogue, batch number per product, reference per agency. | Lookups normalise input, so stored codes must match exactly. |
| D63 | Company-entered credentials are claims: `PENDING_REVIEW`, status `ACTIVE`, `data_mode` `DEMO`, and fixed provenance "Entered by the company as a claim…", all set by the server (the client cannot set status). Hidden from lookups until an admin approves; rejected claims stay hidden. Admins review them at `/admin` with the same conflict-of-interest and audit rules as companies (D55-D56). | Rule 3 and Q5. Until a claim is approved, a company's new product returns `DETAILS_MISMATCH (credential)`, never "Demo record found". |
| D64 | Editing a published product is not built here; it goes through change notices (Phase 5). No separate product-approval flow. Extra representatives and a supplier detail page are skipped (one owner per company is enough). | Avoid over-engineering. |
| D65 | On company registration the owner becomes the directory contact: `is_public_contact`, title "Owner", and the company's contact email and phone. The owner's login email is never shown. | Directory must show the owner's contact (student request) without breaking D58. |
| D66 | Registration offers three company types: Manufacturer, Wholesaler, or Manufacturer and wholesaler (`MANUFACTURER`, `WHOLESALER`, `BOTH`). Any approved company type may add products. | Confirmed by the student; tested for all three. |
| D67 | (2026-10-09) Credential claims are stored `INACTIVE` + `PENDING_REVIEW`; only admin approval sets them `ACTIVE`. Rejected claims stay `INACTIVE`. Replaces the "status `ACTIVE`" part of D63. | Student instruction: a claim is never active until admin review. |

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
| D77 | Announcement text containing the whole words "safe" or "unsafe" is refused (422), so a company cannot claim its product is safe or unsafe. Whole-word matching means "safety", "safely", "fake", and "counterfeit" are allowed, so companies can warn about counterfeits ("beware of fake versions"). FoodLens's own wording still never uses "fake" (rule 1). Regulator claims such as "NAFDAC approved" are not blocked automatically; admins hide misleading ones. | Student decision (2026-10-09): allow counterfeit warnings, block only safe/unsafe claims. |
| D78 | Announcements never change product data. The company can withdraw its own; admins can hide any (except for a company they belong to). Both set `HIDDEN`, `hidden_by_user_id`, `hidden_at`, and write an audit entry. Hidden announcements are not shown again. | Rule 5 exception; accountability. |
| D79 | Admins see live announcements at `/admin` with a Hide button and optional reason (stored in the audit log). | Post-moderation instead of pre-approval. |
