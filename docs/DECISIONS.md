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
| D23 | Publishing a product needs admin review: `DRAFT → PENDING_REVIEW → PUBLISHED / REJECTED`, plus `WITHDRAWN`. | Without it a company could put any product in front of consumers unreviewed. Extends non-negotiable rule 4. |
| D24 | `USER_SESSION` table holds hashed session tokens with expiry and revocation. | Server-side sessions can be revoked on logout; JWT cookies cannot. |
| D25 | `COMPANY_MEMBER` gains `is_public_contact`, `public_title`, `public_phone`, `public_email`. | Supplier pages can name representatives without exposing login emails. |
| D26 | Member roles are `OWNER` and `REPRESENTATIVE` only. | `STAFF` had no distinct permissions. |
| D27 | `created_at` on every table; `updated_at` only on edited tables. Append-only tables (`audit_log`, `change_notice_field`, `notice_attachment`, `order_line`, `order_batch_allocation`, `user_session`) have none. | Makes immutability visible in the schema. |
| D28 | Enums stored as `VARCHAR` + `CHECK`, not native PostgreSQL enums. | Native enums need awkward migrations to add values. |
| D29 | `BATCH_SCAN` and `CONCERN_REPORT` are deferred to Phase 8's migration. They stay in `ERD.mmd`, marked Phase 8. | Optional features; no empty tables until needed. |
| D30 | `docs/PLAN.md` Phase 1 is now "Data model"; identity/roles moved to the start of Phase 2. | The whole schema was built in one phase at the student's request. |
