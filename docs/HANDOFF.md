# FoodLens — Claude Code Project Context Handoff

**Prepared:** 6 October 2026  
**Purpose:** Give a coding assistant the project background, current intended behaviour, proposed architecture, data model, constraints, and implementation priorities.  
**Project status:** Concept and design artifacts have been developed in this conversation. **No application source code has been implemented here yet.** Treat this file as the current product/design brief; do not assume an existing codebase or regulator integration.

---

## 1. Short description

**FoodLens** is a proposed Nigerian food-product traceability and trusted-sourcing platform. Consumers can check a packaged product and batch against a FoodLens database. Food companies can manage their profiles, representatives, products, batches, credential records, and product-change notices. Wholesalers can discover FoodLens-reviewed supplier locations, contact company representatives, and submit wholesale order requests. Platform administrators review company and supplier profiles, product updates, and records.

For the capstone, regulatory and company data will be **fictional, seeded demonstration data** because the student has no authorized NAFDAC, SON, or other regulator integration. The system must show a prominent **DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE** banner wherever a consumer sees a lookup result.

### Critical product rule

**Do not show “Product Safe.”** A database lookup is not a laboratory test, does not verify the physical condition of the particular package, and does not prove that a batch number or QR code has not been copied. Return precise record states such as **“Demo record found,” “No match in demo data,” “Details do not match,”** or **“Credential shown as expired in demo data.”**

---

## 2. How the idea evolved

The original voice-note idea was to help people in Nigerian markets who worry about food adulteration—examples raised included chemically ripened produce, dyed palm oil, and fake drinks. The initial concept was a phone app to scan packaged and unpackaged products, return a safety/adulteration score, and send alerts to authorities or legitimate manufacturers.

The design was narrowed because a phone-camera photo cannot chemically identify hidden adulterants. A credible first concept was a consumer product-information checker and concern-reporting workflow. Later, the project vision expanded to include batch lookup, simulated regulatory records, company onboarding, representative contacts, change notices, vetted supplier locations, and wholesaler order requests.

**Current scope is the expanded platform**, not the first small consumer-only design. The previous consumer-only ERD and workflow are historical and should not be treated as the final data model. The consumer concern-report idea can remain as a small optional feature, but the capstone’s main differentiator is the connection between product/batch records and B2B trusted sourcing.

The student also mentioned “drop POPs” when companies make changes. This brief interprets that as **company product-change notices with optional supporting documents**. If “POPs” means a specific document type, implement it as an attachment or notice category after clarifying.

---

## 3. Problem, users, and value

### Problem being addressed

A buyer may have difficulty checking the product and batch information on a package, identifying a business contact, or finding a wholesale supplier whose profile and product records have been reviewed. Companies may need a structured way to maintain product/batch information and communicate changes to their buyers.

FoodLens does not replace NAFDAC/SON or promise food-safety detection. Its capstone contribution is a software workflow that ties together:

- Product and batch records.
- Explicitly sourced regulatory-record metadata.
- Company and representative profiles.
- Reviewed supplier locations.
- Auditable product-change notices.
- Wholesale order requests and optional fulfilled-batch traceability.

### User roles

1. **Consumer:** no account required for a basic batch lookup; can optionally submit a discrepancy/concern report.
2. **Company representative:** belongs to a company account; maintains product/batch data, credential claims, company contact details, and change notices; responds to wholesaler order requests.
3. **Wholesaler/buyer:** belongs to a buyer company; searches reviewed supplier profiles and submits order requests.
4. **Platform administrator:** approves/rejects company profiles, supplier locations, change notices, and demonstration records. This is a FoodLens review, not an official government determination.

One user account may have a company membership and role. For a simple MVP, a single company membership per account is enough; a many-to-many membership model is more flexible.

---

## 4. Capstone scope

### Recommended MVP

Build a mobile-friendly web app with these connected parts:

1. Manual product-code and batch-number lookup against seeded demo records.
2. Product-level credential records stored separately from batch-level records.
3. Company sign-up/profile with **Pending review** state.
4. Company representatives, product and batch maintenance, and credential metadata entry.
5. Admin-reviewed supplier locations shown in a directory with an honest badge such as **FoodLens demo-reviewed profile**.
6. Product-change notices with reason, proposed change, optional documents, pending/approved/rejected review states, and a record of the reviewer.
7. Wholesaler order **requests** (not payments) with seller response and status tracking.
8. Optional link from fulfilled order lines to actual product batches.
9. Optional consumer concern report linked to a product/batch when known.
10. Functional tests and a usability evaluation that checks comprehension of the result wording and demo-data limitation.

### Stretch / future work, not necessary for the MVP

- Official NAFDAC/SON API or database integration (requires a permitted technical interface and permission; do not assume one exists).
- OCR, automatic photo-based recognition, AI adulteration scoring, or chemical testing.
- Unique per-package serialization, non-reusable tamper-evident tokens, or manufacturer production-system integration.
- Map-based discovery, notifications, payments, delivery, inventory synchronization, reviews, or public vendor ratings.
- Real company identity or certification verification outside the scope of a documented demo review process.

A static QR or printed batch number can be copied. It can support traceability in a demo but is not tamper-proof authentication.

---

## 5. Product and credential result logic

### Lookup inputs

Minimum useful lookup: product identifier (barcode/product code or a manual product selection) **and** batch number. The frontend should show the recognized value and allow correction. OCR/barcode scanning is optional; manual entry is enough for the first working version.

### Backend decision flow

1. Validate and normalize submitted product code and batch number.
2. Find the product in FoodLens catalogue.
3. Find a batch associated with that exact product.
4. Retrieve credential records linked to the product and their agency/scheme, reference number, status, validity dates, source mode, and checked date.
5. Return distinct states; do not collapse missing, expired, mismatch, and positive demo lookup into a “safe/unsafe” score.

### User-facing states

- `DEMO_RECORD_FOUND`: matching product + batch exists in the seeded dataset; show linked credential information and mark everything as simulated.
- `BATCH_NOT_FOUND`: no batch match; say it is not in the FoodLens demo dataset. Do **not** say fake or unsafe.
- `DETAILS_MISMATCH`: one or more comparable fields differ; display which field differs and permit correction.
- `CREDENTIAL_EXPIRED_OR_INACTIVE`: the database record has an expired/inactive status; say that is the status of the stored demo record, not an official enforcement result.
- `INSUFFICIENT_OR_AMBIGUOUS`: the entered fields cannot identify a unique record; ask for correction or manual selection.

A product-level registration/certification is not necessarily a batch-specific certificate. Keep `PRODUCT_BATCH` separate from `CREDENTIAL_RECORD`. Only show a batch-level credential if the supporting record is actually batch-specific.

### Example response shape (not a locked API contract)

```json
{
  "result": "DEMO_RECORD_FOUND",
  "data_mode": "DEMO",
  "message": "A matching product and batch record was found in the FoodLens demonstration dataset. This is not an official verification or a safety test.",
  "product": {"name": "Sample Palm Oil", "brand": "Demo Harvest"},
  "batch": {"batch_number": "DEMO-LOT-001", "expiry_date": "2027-12-31"},
  "credentials": [
    {
      "agency": "NAFDAC (simulated)",
      "scheme": "Food product registration (demo)",
      "reference": "DEMO-NAFDAC-0001",
      "status": "ACTIVE_IN_DEMO_DATA",
      "valid_until": "2027-12-31",
      "source_mode": "DEMO"
    }
  ]
}
```

Use obviously fictional product/company names, numbers prefixed with `DEMO-`, fake contact information reserved for tests, and no real regulator logos. Store a machine-readable `data_mode = DEMO` and enforce the disclaimer in both backend response and frontend, so it cannot be accidentally hidden by one UI screen.

---

## 6. Workflows

### A. Consumer check

1. Consumer opens the scan/check screen.
2. Enters or scans product code and batch number.
3. Frontend displays the values for correction and sends a request to FastAPI.
4. FastAPI searches product, batch, and related product-level credentials.
5. The app displays the relevant status, issuer/scheme, dates, and data provenance, always labelled as demo data.
6. Consumer can finish or open **Report a concern**; the report may carry the checked product/batch values.

### B. Company registration and catalogue management

1. Company submits business profile and one or more representative accounts.
2. Profile is initially `PENDING_REVIEW`.
3. Platform admin reviews and sets `APPROVED`, `REJECTED`, or `SUSPENDED` in the demo platform.
4. Approved members create/edit product and batch records and add credential claims.
5. Credential status/provenance is not self-certified just because a company entered it. For the capstone, it remains visibly `DEMO` and admin review is clearly labelled as FoodLens demo review.

### C. Company product-change notice

1. Company representative selects product (and optionally batch) and submits a notice with type, reason, proposed changes, effective date, and optional attachment.
2. The notice is `PENDING_REVIEW`; published data remain unchanged.
3. Admin approves, rejects, or requests clarification.
4. Only an approved change updates the published catalogue. Preserve the old values/notice for audit.

### D. Wholesaler sourcing and ordering

1. Wholesaler signs in and searches approved suppliers, products, and reviewed locations.
2. Supplier detail shows nominated reps/contact options and what FoodLens reviewed.
3. Wholesaler creates an order request with product, quantity, and pickup/delivery details.
4. Seller representative accepts, declines, or replies; no payment is collected in MVP.
5. At fulfilment, seller may allocate one or more batches to each order line. This is useful for traceability and later issue investigation.

### E. Optional consumer concern report

Consumer submits product/batch details, concern type, description, optional purchase area and photo. The report is private, clearly an unverified consumer submission, and can be reviewed in an admin queue. Do not publish an accusation or claim it has reached NAFDAC unless an authorized integration is actually implemented.

---

## 7. Proposed data model

A conceptual schema for the expanded platform is below. Names and field details may change during implementation, but preserve the relationships and data provenance.

| Table | Main purpose / important fields |
|---|---|
| `APP_USER` | `user_id`, unique email, password hash, display name, platform-admin flag, active flag. Never store plaintext passwords. |
| `COMPANY` | `company_id`, legal/display name, company type (manufacturer/wholesaler/both), claimed business identifier, profile status, `approved_by_user_id`, created time. Clearly distinguish claimed business data from verified facts. |
| `COMPANY_MEMBER` | Join between `APP_USER` and `COMPANY`, role, membership status. Supports company reps and buyer staff. |
| `PRODUCT` | Owning company, name, brand, category, barcode/product code, status. |
| `PRODUCT_BATCH` | Product FK, batch number, optional production/expiry date, status, optional QR token. Use uniqueness on `(product_id, batch_number)`; do not pretend a plain batch number is secret. |
| `REGULATORY_AGENCY` | Separate issuer/scheme metadata, e.g. NAFDAC vs SON/MANCAP; do not combine them as one generic “certified” flag. |
| `CREDENTIAL_RECORD` | Product FK, agency FK, certificate/registration number, scope, status, validity dates, `data_mode`, evidence/provenance, checked date. Credential usually links to product, not every batch. |
| `SUPPLIER_LOCATION` | Company FK, name/address/area, FoodLens review status, reviewer/time. Any badge means only what the FoodLens demo reviewed. |
| `CHANGE_NOTICE` | Company FK, optional product FK, submitter and reviewer user FKs, change type, reason, proposed changes, review status, dates. Use immutable notice/change history rather than silent edits. |
| `NOTICE_ATTACHMENT` | Change notice FK, storage reference, MIME/file type, timestamp. Restrict file types and size. |
| `WHOLESALE_ORDER` | Buyer company FK, seller company FK, creating user, request status, delivery/pickup details, timestamps. No payment fields in MVP. |
| `ORDER_LINE` | Order FK, product FK, quantity and unit. |
| `ORDER_BATCH_ALLOCATION` | Order-line FK, batch FK, allocated quantity; used only when actual fulfilment is recorded. |
| `BATCH_SCAN` | Optional anonymized scan log; input product/batch values, optional recognized batch FK, result, timestamp. Avoid consumer identity by default. |
| `CONCERN_REPORT` | Optional product/batch FKs, product/batch snapshots, concern type, description, status, timestamp. Never treat as confirmed finding. |

### Main cardinalities

- Company 1-to-many company members, products, supplier locations, change notices, and orders as buyer or seller.
- Product 1-to-many batches and credential records.
- Regulatory agency 1-to-many credential records.
- Product 1-to-many order lines.
- Order 1-to-many order lines; an order line may be allocated to one or more batches when fulfilled.
- Product/batch can be optional references on a consumer report or batch scan when the lookup failed.

The earlier ERD made only for product checks and reports is **superseded** by this expanded model. A current conceptual ERD source was drafted as `/home/ubuntu/FoodLens_Current_ERD.mmd`, but it is a design artifact, not a database migration or an approved final schema.

---

## 8. Architecture and implementation recommendations

### Recommended stack (not all choices are locked)

- **Frontend:** responsive browser app; React + TypeScript is a reasonable default. Other course-approved frameworks are acceptable.
- **Backend:** Python + FastAPI.
- **Database:** PostgreSQL for deployment; SQLite is acceptable for local early development/testing.
- **ORM/migrations:** SQLAlchemy or SQLModel, plus Alembic if the project has time.
- **Authentication:** secure password hashing, session/JWT approach chosen consistently; server-side role and company membership checks on every protected route.
- **QR:** optional generated codes containing an opaque FoodLens URL/token; never encode “safe” into the QR itself.
- **File uploads:** validate MIME type, extension and size; store file references and keep documents private unless explicitly approved for display.

Suggested separation:

```text
frontend screens/components
   -> typed API client
      -> FastAPI routers (auth, companies, catalogue, scans, changes, suppliers, orders, reports, admin)
         -> service/business rules (authorization, lookup, approval, order status)
            -> SQLAlchemy models/repositories
               -> database
```

Do not place all rules in frontend components or in one giant API route. Validate every submitted field server-side. Enforce which company owns each product/location and which user belongs to the buyer/seller company. Use environment variables for secrets; never commit credentials.

### Suggested route families

These are a starting point, not a fixed contract:

- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `POST /api/lookups/batch`, `GET /api/lookups/{scan_id}` (the latter only if lookup history is stored)
- `GET /api/products`, `GET /api/products/{id}`
- `POST /api/companies`, `GET /api/companies/{id}`, `PATCH /api/companies/{id}`
- `POST /api/company/products`, `POST /api/company/products/{id}/batches`
- `POST /api/company/products/{id}/credentials`
- `POST /api/company/change-notices`, `PATCH /api/admin/change-notices/{id}/decision`
- `GET /api/suppliers`, `GET /api/suppliers/{id}`
- `POST /api/orders`, `GET /api/company/orders`, `PATCH /api/orders/{id}/status`
- `POST /api/orders/{id}/lines/{line_id}/batch-allocations`
- `POST /api/reports` (optional), admin review endpoints

---

## 9. UI screen checklist

1. Public landing page with FoodLens explanation and demo-data banner.
2. Consumer scan/manual product + batch form.
3. Lookup results with status, agency/scheme details, provenance, and caveat.
4. Optional report-a-concern form and acknowledgement.
5. Company registration and pending-review state.
6. Company dashboard: profile, reps, products, batches, credentials, change notices, order requests.
7. Wholesaler dashboard: supplier search, location/profile, rep contact, order request and order tracking.
8. Admin dashboard: pending companies/locations, record review, changes, orders/reports, audit details.

---

## 10. Security, privacy, and responsible presentation

- Demo names, credentials, contact details, and logos should be fictional and visibly labelled.
- No regulator endorsement or real regulatory connection should be implied.
- Do not collect a consumer account, exact GPS, health data, or scan history unless needed and approved.
- Make consumer contact details and concern photos optional; restrict their access and define deletion/retention.
- Keep submitted company claims separate from admin-reviewed fields.
- Do not let company users self-approve records or supplier badges.
- Keep user reports private; do not publicly accuse a company/vendor based on an unverified report.
- Prevent mass assignment: client input must not set `is_admin`, verification status, credential activation, order ownership, or company approval fields.
- Protect upload endpoints; use non-public storage keys, size/type restrictions, and safe filenames.
- Log meaningful changes with actor/time. Avoid placing passwords, tokens, or unnecessary PII in logs.

---

## 11. Testing and capstone evaluation

### Backend/function tests

- Known demo product + batch returns the correct simulated record.
- Unknown batch returns `BATCH_NOT_FOUND`, not “fake” or “unsafe.”
- Mismatched code and batch are distinguished from no record.
- Expired/inactive credential status is calculated/displayed consistently.
- Product-level credential is not falsely represented as a batch test.
- Company member cannot edit another company’s products or orders.
- Company member cannot self-approve credentials, locations, or changes.
- Unapproved change remains pending and does not replace published data.
- Approved change updates active catalogue and keeps prior audit evidence.
- Wholesaler can order only from permitted company/product listings.
- Seller can accept/decline only orders addressed to their company.
- Order fulfilment batch allocation references the correct product.
- Upload validation and authentication/authorization errors work.

### Usability evaluation

With supervisor approval and consent, ask a small group of users to scan/enter a demo batch, interpret the result, find a reviewed demo supplier, and place an order request. Measure task completion, errors, time, and especially whether participants understand that demo records are not regulator confirmation and do not guarantee safety. Do not have participants consume food or make health conclusions.

---

## 12. Suggested build sequence

1. **Confirm scope:** get supervisor approval for simulation, user roles, category count, privacy, and no-payment order requests.
2. **Repository foundation:** frontend/backend structure, environment config, DB connection, migrations, seed data, linting and tests.
3. **Identity and roles:** admin, company member, wholesaler; enforce company ownership.
4. **Catalogue and batches:** product/batch models, admin seed records, manual lookup API, demo-safe result wording.
5. **Credential record display:** issuer/scheme, number, scope, date/status, `data_mode` disclaimer.
6. **Company workflow:** registration, admin review, representatives, supplier locations.
7. **Change notice workflow:** submit, attach evidence, approve/reject, preserve history.
8. **Order-request workflow:** supplier discovery, order request, seller response, optional batch allocation.
9. **Optional concern reporting and scan analytics** if time allows.
10. **Evaluation, documentation, demo and final capstone report.**

---

## 13. Current decisions versus open choices

### Decisions / constraints already established

- Project name: **FoodLens** (working name).
- Context: Nigerian food product/supply chain.
- Backend requested by student: **Python + FastAPI**.
- No access to NAFDAC/SON systems; capstone uses dummy/simulated data.
- Never claim product is “safe” based only on the app/database.
- Companies, reps, wholesalers, supplier locations, changes, and order requests are part of the expanded vision.
- Order requests should not require payments in the MVP.
- Batch traceability is desired; exact batch lookup is possible against seeded data.
- “POPs” currently interpreted as product change notices and supporting documents.

### Choices still open for student/supervisor

- React/TypeScript vs another frontend framework.
- PostgreSQL vs SQLite for final demo/deployment.
- Whether the product lookup is manual entry only or includes QR/barcode scanning.
- Whether to include consumer concern reports in the MVP or treat them as a stretch feature.
- Number of demo product categories, companies, batches, agencies, and locations.
- Whether a company can have multiple users/members in the first version.
- Which documents a company change notice may attach and how admins review them.
- Whether to retain scan logs; privacy-minimizing default is not to link them to a person.
- Whether fulfilment-level batch allocation is MVP or stretch.
- Exact order status lifecycle and supplier-location review checklist.

---

## 14. Research references already consulted

- [NAFDAC Product Registration & Regulation](https://nafdac.gov.ng/our-services/product-registrationevaluation/) — official registration guidance, including the issuance of registration numbers/certificates and product samples/laboratory analysis where requested.
- [NAFDAC Food Products Database](https://nafdac.gov.ng/food-products-database/) — official food-products database landing page. Do not assume that a page implies API access or authorization for automated data reuse.
- [SON MANCAP service](https://son.gov.ng/mancapservice/) — official description of MANCAP for conformity to Nigerian Industrial Standards; food product sector is included.
- [Smartphone-based optical assays in food safety](https://pmc.ncbi.nlm.nih.gov/articles/PMC7457721/) — research review on camera/sensor assay constraints such as calibration, illumination, device variation, sample prep, and validation.
- [Method development and survey of Sudan I–IV in palm oil and chilli products](https://pmc.ncbi.nlm.nih.gov/articles/PMC4888373/) — example of laboratory LC-MS/MS analysis for specific adulterants, underscoring why a phone-only universal safety test is outside this project.

---

## 15. Earlier artifacts and how to treat them

The conversation produced an initial instructor proposal, an initial consumer/admin workflow guide, a simple consumer-report ERD, a simple workflow image, and an expanded project design brief. Those documents explain the origin and reasoning but the first proposal/ERD predate the current company + wholesaler + batch-traceability scope. This handoff supersedes the earlier narrow ERD as the current design summary.

A newer conceptual expanded ERD source is at `/home/ubuntu/FoodLens_Current_ERD.mmd`. It is a draft for discussion, not guaranteed production schema. Revisit its fields/cardinalities during implementation, especially role membership, statuses, audit history, batch-specific claims, and optional concern reports.

---

## 16. Instructions for Claude Code

1. Read this handoff before making architecture decisions.
2. Inspect the actual repository and report what exists before assuming files, frameworks, or setup.
3. Treat this document as the current product direction, but surface contradictions or missing decisions before implementing major scope.
4. Start with the MVP in Section 4 and build in the sequence in Section 12; do not silently add payments, live regulator scraping, AI safety scores, or broad public ratings.
5. Keep all seed credentials and companies obviously fictional and force demo-mode labels in backend responses and frontend.
6. Implement authorization checks server-side, including tenant/company ownership and moderator-only review actions.
7. Write tests for lookup outcomes and permissions before adding optional OCR or other enhancements.
8. Keep a `README` with install/run/test/seed instructions and document the database schema/migrations.
9. Ask the student before making material choices that change business rules, privacy, or official-claim wording; use reversible defaults for minor implementation details and explain them.

**One-sentence build target:** Build a responsive, role-based FoodLens prototype where consumers can look up simulated product/batch/credential records, companies can manage reviewed catalogue data and submit change notices, and wholesalers can discover demo-reviewed suppliers and place traceable order requests—without making official certification or product-safety claims.
