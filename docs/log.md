# FoodLens challenge log

Problems met while building FoodLens, what caused them, and how they were resolved. Newest entries go at the bottom of each section's table, and new dates get a new section. Useful for the capstone report's "challenges and lessons" chapter.

**Status:** Resolved · Workaround · Open · Decision (needed a choice, not a fix)

---

## 2026-10-06 — Planning

| # | Area | Challenge | Cause | Resolution | Status |
|---|---|---|---|---|---|
| 1 | Docs | The brief named `docs/HANDOFF.md` and `docs/ERD.mmd`, but the real files had different names. | Files were exported with long names. | Renamed to `docs/HANDOFF.md`; old ERD moved to `docs/archive/`. | Resolved |
| 2 | Data model | The ERD in the repo was the old consumer-only design; the current expanded ERD the handoff referred to (`/home/ubuntu/…`) was missing. | Handoff written in another environment. | Rebuilt the ERD from handoff §7 and later from the actual models (`docs/ERD.mmd`). | Resolved |
| 3 | Requirements | Handoff left key rules open: which edits need review, lookup state order, what "POPs" meant, buyer approval. | Brief was a concept, not a spec. | Answered as Q1–Q9 in `docs/DECISIONS.md`. | Resolved |
| 4 | Requirements | Answer to Q3 (company changes auto-approved) contradicted the pasted rules and non-negotiable rules 4–5 (admin review). | Two goals in tension: ease for companies vs. trustworthy data. | Split: pop-up announcements ("POPs") go live instantly but are labelled unreviewed; real data changes need admin review. | Decision |
| 5 | Planning | Handoff §12 had 10 steps but the plan needed phases 0–9. | Counting mismatch. | Scope confirmation became a gate before Phase 0; ordering split into discovery and requests. | Decision |

## 2026-10-07 — Foundation and data model

| # | Area | Challenge | Cause | Resolution | Status |
|---|---|---|---|---|---|
| 6 | Tooling | `python` command not found. | Python not installed globally on Windows. | `uv` downloads and manages Python 3.12 per project. | Resolved |
| 7 | Docker | Database could not start: "the docker daemon is not running". | Docker Desktop was closed. | Started Docker Desktop. Recurred on 2026-10-08 (see #19). | Resolved |
| 8 | Database | `password authentication failed for user "foodlens"` although the password was right. | A native Windows PostgreSQL 18 service (`postgresql-x64-18`) also listens on port 5432 and answered first. | Moved FoodLens Postgres to host port **5433**; left the native service untouched. | Resolved |
| 9 | Frontend | `create-next-app` installed Next.js 16.4, whose APIs differ from older docs; it added `AGENTS.md` warning about this. | New major version. | Read the bundled docs in `node_modules/next/dist/docs/` before writing config. | Resolved |
| 10 | Frontend | `tsc` failed: `Cannot find name 'LayoutProps'`. | Next 16 generates route types only during `next dev/build/typegen`. | `npm run typecheck` now runs `next typegen && tsc --noEmit`. | Resolved |
| 11 | Frontend | `npm install` failed with ERESOLVE (Vitest 5 vs `@types/node@20`). | Peer dependency conflict. | Upgraded `@types/node` to ^24 to match Node 24. | Resolved |
| 12 | Backend | Test warning: "Using `httpx` with `starlette.testclient` is deprecated". | Upstream change. | Switched dev dependency to `httpx2`. | Resolved |
| 13 | Frontend | Vite warned the `vite-tsconfig-paths` plugin is redundant. | Vite now supports tsconfig paths natively. | Removed plugin; set `resolve.tsconfigPaths: true`. | Resolved |
| 14 | Git | "LF will be replaced by CRLF" warnings on every file. | Windows `core.autocrlf`; Docker/shell files break with CRLF. | Added `.gitattributes` (`* text=auto eol=lf`). | Resolved |
| 15 | Git | First commit title included "Phase 0"; later commits were asked not to use phase names. | Naming preference set after the first push. | Later commits use Conventional Commits (`feat(scope): …`). The pushed commit was left unchanged to avoid rewriting GitHub history. | Workaround |
| 16 | Migrations | Alembic autogenerate wrote every enum CHECK constraint twice (plus the enum's own). | How Alembic renders non-native SQLAlchemy enums. | `render_item` hook in `alembic/env.py`: enums rendered as `sa.String`, duplicate bare-named checks dropped. Verified 24 constraints in the DB. | Resolved |
| 17 | Lint | Ruff E501 (line too long) in generated migrations and the seed case table. | Generated code and readable one-row-per-case tables. | Per-file ignores in `pyproject.toml`. | Resolved |
| 18 | Tests | A test factory crashed when a test overrode `email`. | Keyword passed twice. | Factories merge default and override dicts. | Resolved |

## 2026-10-08 — Auth, rate limiting, lookup, companies

| # | Area | Challenge | Cause | Resolution | Status |
|---|---|---|---|---|---|
| 19 | Docker | 58 test errors after a 4.6-minute hang (`OperationalError`). | Docker Desktop closed overnight; every DB connection timed out. | Restarted Docker Desktop. Lesson: check `docker compose ps` first when DB tests fail en masse. | Resolved |
| 20 | Lint | Ruff B008: `Depends(...)` in argument defaults. | Older FastAPI style. | Switched to `Annotated[..., Depends(...)]`. | Resolved |
| 21 | Tooling | A script could not read a file written to `/tmp` in Git Bash. | Git Bash `/tmp` is not the same folder Windows Python sees. | Use the session scratchpad path for temporary files. | Resolved |
| 22 | Scope | Request "users are not meant to log in" — confirmed consumers never need accounts. | Clarification. | Only admins and company users sign in; lookups are anonymous. | Decision |
| 23 | Security | Rate limits could be bypassed by sending a fake `X-Forwarded-For` header. | Next.js keeps a client-supplied `X-Forwarded-For` (`??=`) and the rewrite proxy does not append the real IP. | Custom server `frontend/server.mjs` overwrites the header with the real connection address. Verified from the LAN IP: forged headers now blocked. | Resolved |
| 24 | Testing | An early end-to-end check of the spoofing gap was inconclusive. | `curl` from the same machine is `127.0.0.1`, which is itself a trusted proxy address. | Re-tested using the machine's LAN IP (`192.168.2.199`). | Resolved |
| 25 | Config | `HOSTNAME` env var could break the custom server inside Docker. | Docker sets `HOSTNAME` to the container ID. | Server uses a fixed hostname and listens on all interfaces. | Resolved |
| 26 | Networking | Windows reported some IPv4 clients as `::ffff:192.168.x.x`, which would not match exempt IPs. | IPv4-mapped IPv6 addresses. | Normalised on both server and API, with tests. | Resolved |
| 27 | Tooling | Next.js warned about `C:\Users\…\Desktop\package-lock.json` outside the repo. | Stray file (86 bytes, dated 2 Oct) on the Desktop. | Left untouched; can be deleted if not needed. | Open |
| 28 | Requirements | Lookup request listed 5 states; recorded rules have 6 (`BATCH_EXPIRED`). | Request written before Q4 was answered. | Kept 6 states to follow recorded decisions (D47); reversible. | Decision |
| 29 | Privacy | Lookup request asked for a scan log, but D8 said scan logs off by default. | Requirement changed. | Implemented anonymised `batch_scan` (no IP/user/device); recorded as D46 superseding D8. | Decision |
| 30 | Frontend | TypeScript error indexing credential statuses (`z.enum(Object.keys(...))` widened to `string`). | Zod type inference. | Used a typed tuple of status values. | Resolved |
| 31 | Wording | The disclaimer contains "food-safety test" while a test bans the word "safe". | Substring vs whole word. | Banned-word checks are whole-word (`\bsafe\b`); "safety" is allowed (D52). | Decision |
| 32 | Running the app | "The page is not opening" at `localhost:3000/check`. | Servers had been stopped after automated testing, and the run steps were not repeated. | Started both servers; README "Run" section lists the two commands. Lesson: say clearly when servers are stopped. | Resolved |
| 33 | Testing | An end-to-end check got HTTP 500 (`ECONNREFUSED ::1:8000`). | Started checking when the web server was up but the API was still starting. | Wait for the API health check before testing. | Resolved |
| 34 | Running the app | New company/admin routes returned 404. | FastAPI dev auto-reload ran mid-edit and missed the later `main.py` change. | Restarted the API dev server. Lesson: restart the backend if new routes 404. | Resolved |
| 35 | Requirements | Supplier directory requested as public; handoff had wholesalers signing in to search. | Requirement changed. | Public directory showing only reviewed data (D58). | Decision |
| 36 | Dev data | No admin account exists in the dev database, so `/admin` cannot be used yet. | Test accounts were cleaned up and `SEED_ADMIN_*` is not set. | Set `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` in `backend/.env` and run `uv run python -m app.seed`. | Open |
| 37 | Scope | Phase 4 is only partly done (no representative management or product/batch/credential entry yet). | Request covered registration, review, locations, and directory only. | Remaining items listed in `docs/PLAN.md` Phase 4 progress. | Open |

## 2026-10-09 — Company catalogue

| # | Area | Challenge | Cause | Resolution | Status |
|---|---|---|---|---|---|
| 38 | Docker | Test run hung past 5 minutes; every test errored. | Docker Desktop was closed again at the start of a new session (same as #19). | Started Docker Desktop and waited for Postgres to be healthy. Lesson: start Docker Desktop first each day. | Resolved |
| 39 | Requirements | New request: products and batches go live without admin review, which contradicted rule 4, rule 5, and D23. | Founder simplified the workflow. | Rules and decisions updated (D61-D63); the credential review remains the gate, so unreviewed products never show "Demo record found". | Decision |
| 40 | Privacy | Directory had to show the owner's contact, but D58 forbids showing login emails. | Two requirements overlapping. | Owner shown with the company's public contact email and phone (D65). | Decision |
| 41 | Tooling | A long inline script failed with "unexpected EOF while looking for matching quote". | Bash heredoc quoting broke on mixed quotes in a long document edit. | Wrote the script to a scratch file and ran it from there. | Resolved |
| 42 | Wording | The announcement filter blocked "fake", so companies could not warn "beware of fake versions". | First version banned every rule-1 word in company text. | Filter now blocks only the whole words "safe" and "unsafe"; counterfeit warnings allowed. Rule 1 narrowed to FoodLens's own wording (D77). | Decision |
| 43 | Requirements | Core purpose corrected: consumers must check registration against the regulator's records, but credentials were company claims approved by a FoodLens admin. | Earlier design proved FoodLens accepted a claim, not that a regulator registered the product. | Replaced credentials with a seeded, read-only simulated register; lookup now starts from the printed number (D80-D87). Old credential data, endpoints, and ~35 tests removed or rewritten. | Decision |
| 44 | Migrations | Autogenerate could not handle the switch: old scan results, a renamed column, and changed CHECK constraints. | Alembic does not compare CHECK constraints and treats renames as drop + add. | Migration `0004` hand-written (delete old scans, rename column, replace constraints) and tested with upgrade, downgrade, upgrade. | Resolved |
| 45 | Frontend | ESLint refused setting form state from the URL inside an effect (`react-hooks/set-state-in-effect`). | Reading `window.location` after render causes an extra render. | The `/check` page reads `?reg=&batch=` on the server inside `Suspense` (Next 16 with `cacheComponents`) and passes initial values to the form. | Resolved |
| 46 | Wording | Case-insensitive "SON approved" filter also blocks "my son approved...". | "SON" is also an everyday word. | Kept as requested and documented as a known limitation (D86). | Open |

## 2026-10-12 — Camera scanning

| # | Area | Challenge | Cause | Resolution | Status |
|---|---|---|---|---|---|
| 47 | Requirements | Camera OCR requested, but CLAUDE.md said "never add OCR". | Rule written before scanning was wanted. | Founder approved changing it to "OCR only in the browser; no image leaves the device" (D88). | Decision |
| 48 | Phone testing | The founder uses an iPhone, so USB port forwarding (Android only) cannot give the camera an HTTPS page. | Browsers only allow the camera on HTTPS or localhost. | Cloudflare quick tunnel is the default; mkcert documented as a backup (README). | Decision |
| 49 | Rate limits | Through a tunnel every phone arrives from cloudflared's local address, so all visitors would share one rate-limit bucket. | The tunnel is a proxy on the same machine. | `server.mjs` trusts `CF-Connecting-IP` only when enabled and only from cloudflared's address (D90); 13 tests. | Resolved |
| 50 | Tooling | `tesseract.js` 7.0.0 brings `tesseract.js-core` 7.0.0, and by default downloads its engine and English model from the jsDelivr CDN. | Library defaults. | A copy script serves the files from `/ocr/` (D89); a test checks no path starts with `http`. | Resolved |
| 51 | OCR | The real engine read "NAFDAC REG. NO: A1-1234" as `NAFDACREGNOA1-1234`. | The character whitelist had no space, so Tesseract dropped word gaps. | Added the space to the whitelist and split labels glued to numbers; the real engine then read all three test images correctly. | Resolved |
| 52 | OCR | Glued `NAFDACREGNOA1-1234` gave `OA1-1234`. | The pattern tried `REGN` before `REG`, taking the `N` of `NO`. | Reordered the alternatives; test added. | Resolved |
| 53 | Frontend | `npm run typecheck` failed on the tunnel tests (`never[]` not assignable). | TypeScript inferred types from the plain-JS default parameter in `forwarded-for.mjs`. | Added JSDoc types. | Resolved |
| 54 | Frontend | ESLint reported errors in `public/ocr/`. | It linted the copied, minified third-party files. | Ignored `public/ocr/**` in `eslint.config.mjs`. | Resolved |
| 55 | Phone testing | `TRUST_CLOUDFLARE_TUNNEL=true` in `.env.local` would have been ignored. | `server.mjs` read the setting before Next.js loaded `.env.local`. | Read it after `app.prepare()`; checked the server log shows the trusted addresses. | Resolved |
| 56 | OCR | Accuracy on real packs is unknown; only synthetic images were tried. | No real packs tested yet. | `docs/OCR_ACCURACY.md` sheet for about 20 packs. | Open |

## 2026-10-12 — Wholesale order requests

| # | Area | Challenge | Cause | Resolution | Status |
|---|---|---|---|---|---|
| 57 | Requirements | The order request said only approved wholesalers may order; Q6 said buyers need no approval. Status was `SUBMITTED`, the request said "requested". Allocations required a quantity, but inventory was skipped. | Requirements changed since Phase 1. | Followed the new request and recorded it: D95 supersedes Q6; `SUBMITTED` renamed `REQUESTED` (D96); `allocated_quantity` dropped (D99); migration `0005`. | Decision |
| 58 | Docker | `docker compose` could not connect to the Docker engine. | Docker Desktop was closed again (as in #19 and #38). | Started Docker Desktop. | Resolved |
| 59 | Migrations | Migration 0005 failed: constraint `ck_wholesale_order_ck_wholesale_order_order_status` does not exist. Then `downgrade -1` rolled the dev database back from 0004 to 0003, which emptied the simulated register. | The naming convention added the `ck_wholesale_order_` prefix a second time; and `downgrade -1` was chained after the failed upgrade. | Wrapped the names in `op.f()`. Upgrade, downgrade, upgrade, and `alembic check` all pass. Re-seeded the dev database. Lesson: stop if an upgrade fails, and don't chain a downgrade after it. | Resolved |
| 60 | Tooling | A long inline seed edit failed with "unexpected EOF while looking for matching quote". | Bash heredoc quoting, as in #41. | Wrote the edit as a script file. | Resolved |
| 61 | Tooling | The smoke-test commands failed with `python: command not found`. | No system Python on PATH; Python only runs through `uv`. | Ran the smoke test with `uv run python`. | Resolved |
| 62 | Wording | The live smoke test showed "Sample Honey" as "Active" on the supplier page, though its number belongs to another product and company. | The first version only checked the register status, not the names (D83). | Added `REGISTERED_TO_ANOTHER_PRODUCT` ("Number belongs to a different product or company in the simulated register (demo data)"), same name check as lookups (D100). Reuses approved lookup wording; flagged for the founder. | Decision |
| 63 | Requirements | Seed orders need user accounts, but seeded companies have none, and a default password in the code would be a secret. | Orders reference `created_by_user_id`. | Demo accounts get a password only from `SEED_DEMO_PASSWORD`; otherwise login is impossible (D101). | Decision |

## 2026-10-12 — Closing Phase 4

| # | Area | Challenge | Cause | Resolution | Status |
|---|---|---|---|---|---|
| 64 | Scope | Seven Phase 4 checklist items were still unticked after Phase 7. | Most were covered by tests written in Phases 4-7 but never ticked; contact-detail editing was never built (marked "optional"). | Matched each item to its tests; built the owner contact edit with audit (D103); added a test that products and batches have no direct edit routes. | Resolved |

## 2026-10-12 — One-command local start

| # | Area | Challenge | Cause | Resolution | Status |
|---|---|---|---|---|---|
| 65 | Seed | `uv run python -m app.seed` crashed with `DetachedInstanceError` after seeding. | Once `SEED_ADMIN_*` was set, `main()` printed `admin.email` after the session had closed and later commits had expired the object. It had never run before because no admin was configured. | Read the email inside the session block. The data had already been committed. | Resolved |
| 66 | Local env | Appending `SEED_DEMO_PASSWORD` to `backend/.env` glued a comment onto the end of the `SEED_ADMIN_PASSWORD` line. | The file had no final newline. | Removed the glued text straight away and checked the line. Lesson: check for a final newline before appending to `.env`. | Resolved |
| 67 | Running the app | Port 3000 was still in use after stopping the earlier dev server. | Stopping the background shell left the `node server.mjs --dev` child process running. | Checked the process command line, then stopped its process tree. `scripts/dev.mjs` stops its servers with `taskkill /T` on Windows. | Resolved |

## 2026-10-21: Scope change to unit-level product integrity (planning)

| # | Area | Challenge | Cause | Resolution | Status |
|---|---|---|---|---|---|
| 68 | Requirements | FoodLens changed from a registration-number lookup to unit-level product integrity. The register, the lookup results and the NAFDAC OCR parsing became obsolete, and orders no longer fit the core. | A new product concept (`Update.md`, now `docs/PRODUCT_INTEGRITY.md`) and a planning prompt. | Planned before any code: a keep/rework/remove/hide list; D104–D130; PLAN rewritten as phases 1–11. Orders are hidden behind a flag, not deleted. | Decision |
| 69 | Identity | The prompt asked for Crockford Base32 "without I, L, O, U" plus a check character. Crockford's own check uses mod 37 with `* ~ $ = U`. | The standard check alphabet is larger than the data alphabet. | Luhn mod-32 over the same 32 characters (D109). Approved by the founder (Q2). | Decision |
| 70 | Security | The prompt said POS keys are stored hashed, but verifying an HMAC signature needs the raw signing secret. | Hashing is one-way. | API keys are hashed; the signing secret is Fernet-encrypted with `POS_SECRET_KEY` (D121, Q7). The signature covers the timestamp as well as the body, so a captured body cannot be replayed. | Decision |
| 71 | Requirements | "First check of the hidden code records CLAIMED" conflicts with "a consumer scan never changes status" (concept doc §7). | Two rules from different sources. | CLAIMED is a `CONSUMER_CHECK` event that sets only the claim fields; lifecycle and sale status never change (D114). | Decision |
| 72 | Requirements | CLAUDE.md rule 6 ("no payment fields") conflicts with the POS `payment_reference`. | The rule was written for order requests. | Rule reworded: an opaque reference and a transaction ID only; no amounts, card or customer data (D122). | Decision |
| 73 | Requirements | The README must print demo codes, but codes must be random and stored only as hashes. | The demo needs codes people can type. | The seed alone uses a few fixed demo codes, hashed like any other code; the production generator never accepts caller codes (D111). | Decision |
| 74 | Dependencies | During planning, the dev dependency `httpx2` was flagged as a possible typosquat of `httpx`. | Unfamiliar name; entry #12 was not checked first. | Checked properly: the PyPI owner is the Pydantic organisation (maintainer Kludex); source `github.com/pydantic/httpx2`. `starlette/testclient.py` imports it first and deprecates `httpx`. The installed files have no `.pth` hook and no exec/base64/subprocess patterns. Kept. Lesson: search this log before flagging a dependency. | Resolved |
| 75 | Tooling | Appending the new decisions with a bash heredoc failed: "unexpected EOF while looking for matching `'`". | Long document text with mixed quotes, as in #41 and #60. | Appended with the editor tool instead. Lesson: write long document text with the file tools, not heredocs. | Resolved |
| 76 | Privacy | Risk rules need a coarse area, but IP geolocation in Nigeria often places mobile users in Lagos. | Carrier NAT and coarse IP databases. | Cloudflare visitor-location headers first (trusted only under D90), then DB-IP Lite, then a demo-only simulate flag. The IP is discarded; area only (D118, Q5). | Decision |
| 77 | Requirements | The prompt put "foodlens.ng" on labels; the founder plans to buy `foodlens.online`. | Domain not yet chosen when the prompt was written. | The domain comes from `PUBLIC_BASE_URL` and `LABEL_CHECK_DOMAIN`, never hard-coded (D129). | Decision |
| 78 | Risk rules | Rule 1 (scan after a sale in a different area) would alarm a buyer who scans at home in another city the next day. | Legitimate travel looks like a copied code. | Rule 1 is LOW and only shows on the dashboard; only MEDIUM/HIGH alerts change the consumer result (D116, Q4). | Decision |
| 79 | Docs | The founder expected a "founder, not student" wording change to be in place already, but it had never reached this session. | The instruction was not in the conversation. | Applied before committing: "student" became "founder" across the docs, and CLAUDE.md describes FoodLens as a startup product at the demonstration-prototype stage, with the capstone as its first milestone. | Resolved |

## 2026-10-22: Geo-batching and return dispositions (planning)

| # | Area | Challenge | Cause | Resolution | Status |
|---|---|---|---|---|---|
| 80 | Requirements | Rule 11 needs a distance threshold "from env", but no default was given. | Request left the value open. | Default `RISK_OUTSIDE_ALLOCATION_KM=150`, recorded in D133. The founder can change it. | Decision |
| 81 | Requirements | A withdrawn unit needs its own consumer message, but no result code was given for it. | The existing results (D115) cover only unsold, just sold and previously sold. | Added the recognised state `RECOGNISED_WITHDRAWN` with the founder's wording (D135). | Decision |
| 82 | Data model | An allocation given as a quantity only, with no cartons, does not say which units belong to it, so "outside its allocation" was undefined. | Allocations can be quantity-based. | A receipt matches any allocation of the batch to that company or area with quantity left. A batch with no allocations is never outside (D131). | Decision |

## 2026-10-22: Final design, QR only (planning)

| # | Area | Challenge | Cause | Resolution | Status |
|---|---|---|---|---|---|
| 83 | Process | The founder's message said "the full final design follows", but the design text was missing. | The paste was cut off before the design. | Listed only the differences implied by the four answers and asked for the design. It arrived in the next message. | Resolved |
| 84 | Requirements | The final design removes the hidden scratch code, OCR, `WITHDRAWN` and the allocation alerts (rules 10 and 11), which were decided earlier the same day. | The founder simplified the design before Phase 1. | D137–D147 supersede D108, D109, D114, D132–D136 and the D124 rule list; CLAUDE.md, PLAN, SCHEMA and ERD updated. The hidden code is listed as future work. | Decision |
| 85 | Requirements | "No internal identifiers in public responses" listed the public fields without the NAFDAC number and recalls, which D115 shows on every result. | The field list was written for identifiers, not content. | Keep the NAFDAC number (as printed, information only) and live recalls and notices; neither is an internal identifier (D138). Approved by the founder. | Decision |
| 86 | Risk rules | "No allocation for a batch and area means no allocation checks" would let units turn up in an unallocated area without ever raising rule 9. | The rule was worded per area. | For a batch with any allocation, an unallocated area counts as 0; only a batch with no allocations is skipped (D142). Approved by the founder. | Decision |
| 87 | Data model | Rule 9 is about a batch and an area, not a unit, so the per-unit alert de-duplication did not fit; the scanning panel needed rate-limit hits by day, but counters lived only in memory. | Earlier rules all had a unit subject; D119 kept counters in memory. | Added `risk_alert.batch_id` with a per (rule, batch, area) index, and a `rate_limit_daily` table with no IP column (D143, D144). Approved by the founder. | Decision |
| 88 | Docs | OCR docs would describe removed code, or removed docs would leave running code undocumented. | The OCR code is still in the app until Phase 1. | `docs/OCR_ACCURACY.md`, the OCR code and the README OCR section are removed together in Phase 1 (D147). The old version stays at tag `v1-registration-check`. | Decision |

## 2026-10-22: Phase 1, data model and migrations

| # | Area | Challenge | Cause | Resolution | Status |
|---|---|---|---|---|---|
| 89 | Tooling | Bash heredocs failed again with "unexpected EOF while looking for matching `'`", and one heredoc turned `\b` in a regex into a backspace character. | The shell mangles quotes and backslashes in long heredoc bodies, as in #75. | Wrote each multi-line edit as a script file in the scratch folder and ran it. Lesson from #75 confirmed: no long heredocs. | Resolved |
| 90 | Data model | SCHEMA and ERD listed `allocation_carton`, `allocation_unit` and `rate_limit_daily` without a primary key, but the convention test requires one UUID key on every table. `rate_limit_daily.area_id` is nullable, so it cannot be part of a composite key, and a plain unique index would allow one row per hit for an unknown area. | The target schema was drawn before the convention test was applied to it. | Added surrogate UUID keys (`allocation_carton_id`, `allocation_unit_id`, `rate_limit_id`). The `(area_id, day, bucket)` unique constraint uses `NULLS NOT DISTINCT` (PostgreSQL 15+). SCHEMA and ERD updated. | Decision |
| 91 | Data model | "Append-only lifecycle events" was only a service rule, so a schema test could not prove it. | Nothing in the database stopped an UPDATE or DELETE. | A trigger function, `foodlens_refuse_change()`, refuses UPDATE and DELETE on `lifecycle_event`, and UPDATE on `scan_event`. DELETE stays allowed on `scan_event` because the 12-month purge needs it. | Decision |
| 92 | Migrations | Renaming `product.package_size` to `size` would leave existing change-notice rows naming a field that no longer exists. | `change_notice_field.field_name` stores the field name as text. | Migration 0006 renames those field names too, and the downgrade reverses it. | Resolved |
| 93 | Tests | Enum tests expected an IntegrityError, but `'REPRESENTATIVE'` and other long values raised a DataError. | The role column shrank to VARCHAR(5), so the length check fails before the CHECK constraint. | The enum tests accept either error: both mean the database refused the value. | Resolved |
| 94 | Requirements | The PLAN test "no `WITHDRAWN` in the schema" also matches `product.status = WITHDRAWN`, a catalogue state that has nothing to do with returns. | The word is used for two different things. | The founder renamed the catalogue status to `DISCONTINUED` (migration 0006 maps existing rows both ways). The test now checks that no table or enum anywhere allows `WITHDRAWN`. | Resolved |
| 95 | Wording | Removing the lookup left the home page, `/check` and the catalogue hint describing a register check that no longer exists. | The pages were written for the old design. | `/check` shows a placeholder until Phase 3. The home page uses the CLAUDE.md rule 1 wording (recorded facts, copied QR help text, no QR system catches every copied code). The NAFDAC number is "as printed", information only (D107). Approved by the founder on 2026-10-23. | Resolved |
| 96 | Frontend | `components/scan` (camera capture and confirm screen) imported the OCR code and the lookup, but PLAN did not list it for removal. | It was the OCR user interface. | Removed with the OCR stack (D147). Phase 3 builds the QR reader. | Decision |
| 97 | Requirements | D107 says only approved manufacturers create products and batches, but the API let any approved company do it. | Before the type flags, every company that registered could add products. | The catalogue service refuses companies without `is_manufacturer` (403), with tests. | Resolved |
| 98 | Tests | The test that hid a suspended company's announcements went through the lookup. | The rule lived in the lookup service. | Removed with the lookup. Phase 3 covers it: a code from an unapproved manufacturer gives `INVALID_IDENTITY` (D115). | Decision |
| 99 | Orders | The API flag `ORDERS_ENABLED` cannot reach the browser bundle. | Next.js only exposes `NEXT_PUBLIC_*` variables to the client. | The web app reads `NEXT_PUBLIC_ORDERS_ENABLED`; both default to false and must match. The server flag is the control; the client flag only hides links. | Decision |

## 2026-10-23: Phase 2, unit and code generation, label export

| # | Area | Challenge | Cause | Resolution | Status |
|---|---|---|---|---|---|
| 100 | Labels | D139 asks for "a printer CSV", but one CSV with both carton and pack rows cannot tell a printer which row is a carton label without a fifth column. | A carton row and its packs share the same `carton_ref`. | Two files with the same four columns: `units.csv` and `cartons.csv`. The PDF heads carton labels "CARTON C001". Approved by the founder on 2026-10-23. | Decision |
| 101 | Labels | The first PDF printed the code on one line, which overflowed into the next label. | 32 characters of 8 pt Courier are about 54 mm wide; a label column is 48 mm. | The code prints on two lines: four groups, then the last three. Checked by rendering the page. | Resolved |
| 102 | Labels | The QR images had no quiet zone, so a cut label could fail to scan. | The PNG was written with `border=0`. | A 4-module quiet zone is added outside the chosen size, so "15 mm" stays the size of the code itself. A rendered 15 mm page decoded 18 of 18 labels with OpenCV. | Resolved |
| 103 | Performance | A 2,000-pack label file took 18 s to build. | segno scores all 8 QR masks per code in pure Python, and the PNGs were large. | Smaller PNGs (the PDF does not smooth pixels): about 15 s. Mask scoring was kept because it gives the most readable code. The page says it can take up to a minute. | Workaround |
| 104 | Tooling | No PDF renderer was installed to check the layout. | poppler is not on this machine. | Rendered pages and decoded the QRs with pypdfium2 and OpenCV in a throwaway environment; neither is a project dependency. | Resolved |
| 105 | Requirements | D106 lists generate, download and void as owner only, but says nothing about release and allocation. | Release and allocation were added later (D131, D139). | Owners and staff release and allocate; only owners generate and void. Approved by the founder on 2026-10-23. | Decision |
| 106 | Data model | Units need a holder from the start for later custody checks (D113). | Custody begins with the manufacturer. | `ISSUED` sets `current_holder_company_id` to the manufacturer; release keeps it. | Decision |

## 2026-10-26: Phase 3, consumer check

| # | Area | Challenge | Cause | Resolution | Status |
|---|---|---|---|---|---|
| 107 | Requirements | The task said to reuse the existing camera components, but `components/scan` was removed with OCR in Phase 1 (#96). | The camera code lived inside the OCR scanner. | Took the camera handling from `ScanPack.tsx` at tag `v1-registration-check` (back lens, no audio, every track stopped, photo picker when there is no camera) into the new `components/check/ScanQr.tsx`, which reads continuously instead of on a Capture button. | Resolved |
| 108 | Requirements | D117 asks for a self-hosted QR reader using `BarcodeDetector` where available, but iPhone Safari and Firefox have no `BarcodeDetector`. | Browser support differs. | Added `jsqr` as the fallback. It is bundled by Next.js and served by FoodLens, loaded only when the native detector is missing (no CDN, D89). Frames and photos are read from an in-memory canvas that is cleared straight after. | Decision |
| 109 | Data model | A carton code has no sale state, but `scan_event.result` must hold one of the six results, and D115 lists no carton result. | The result enum is per pack. | A carton check logs `RECOGNISED_NOT_SOLD` (or `BATCH_OR_PRODUCT_WARNING` under a recall, or `INVALID_IDENTITY` when voided) with `carton_id` set. The response has `subject: "CARTON"` and the D115 carton message, with no "scan again after you pay" tip and no purchase note. Superseded the same day: the founder chose a separate `CARTON_CODE` result (D148, migration 0008). | Decision |
| 110 | Requirements | An unreleased pack checked in public should be suspicious through rule 6 (D116), but risk rules arrive in Phase 6. | PLAN Phase 3 says `SUSPICIOUS_ACTIVITY` comes only from existing alerts until then. | Until Phase 6 an unreleased pack gives its normal recognised result, with the recorded fact "Not yet recorded as released for sale by the manufacturer". | Workaround |
| 111 | Rate limits | D144 counts rate-limit hits per area, but the area may come from the demo city picker in the request body, which a route dependency cannot read before the limit. | The existing `limit_checks` dependency runs before the body is parsed. | The check and report routes resolve the area first, then apply the limit; a 429 adds 1 to `rate_limit_daily` for that area, day (Nigeria time) and bucket. A blocked check is not logged as a scan. | Decision |
| 112 | Privacy | Cloudflare's `cf-ipcity` and `cf-region` headers could be forged by any client and would then set the stored area. | Next.js forwards every header to the API. | `server.mjs` removes the Cloudflare location headers unless the connection comes from trusted cloudflared (D90), and the API reads them only from a trusted proxy. Tests on both sides. | Resolved |
| 113 | Location | D118 puts the demo city picker last, after Cloudflare and DB-IP. Through the Cloudflare tunnel the real city therefore wins and the picker has no effect. | D118's order. | Kept the D118 order. For a demo through the tunnel, leave `TRUST_CLOUDFLARE_TUNNEL=false` while presenting, or demo on `localhost`. The founder decided: with the flag on, the picked city wins; with it off nothing changes (D148). Tests cover both. | Resolved |
| 114 | Reports | A concern report must reach the pack's manufacturer, but responses carry no unit ID (D138). | Public responses hide internal identifiers. | The browser keeps the checked code in memory and sends it with the report; the API hashes it to find the unit and manufacturer and never stores the code. | Decision |
| 115 | Tooling | `next build` and `npm run dev` stopped once with "Your version of Next.js is affected by a known security vulnerability", and suggested running `next upgrade --agent=security`. | A Next.js 16.4.0 advisory nudge. | The founder approved the upgrade: `next` and `eslint-config-next` pinned to 16.4.3 in a separate commit (`chore: upgrade Next.js for security advisory`). It fixes GHSA-2464-fhr4-w9xw, GHSA-673q-mjm6-r5xr and GHSA-p3m5-59mp-jv5r. Lint, typecheck, tests and build were unchanged. `npm audit` still reports `zod <4.6.6` (high), which is outside that commit. | Resolved |
| 116 | Wording | D115 and D141 give the wording for most results, but not for an unrecognised scanned code, the suspicious result, the recall result or the pattern lines. | Only part of the copy was specified. | Wrote neutral copy that labels recorded facts and possible patterns separately and uses no banned words (tests scan every response and the check source files). The founder reviewed every message on 2026-10-26 and changed the suspicious result ("This code may have been copied", badge "Warning"), the typed not-found body, the copied-QR help text, the privacy notes and the camera-denied message, and removed the repeated banner words from the API disclaimer (the page banner shows them). Tests updated. | Resolved |
| 117 | Migrations | Migration 0008 failed with `constraint "ck_scan_event_ck_scan_event_check_result" ... does not exist`. A follow-up `alembic downgrade -1` on the dev database then ran past 0007 and 0006, which dropped and recreated the unit-identity tables empty. | Hand-written constraint names were prefixed again by the naming convention; they need `op.f()`. Running a downgrade on the dev database after a failed upgrade was a mistake. | Wrapped the names in `op.f()`; the dev database is back at head and re-seeded. Companies, products and batches survived (0006 maps them both ways); packs and cartons generated there earlier were lost and must be generated again. Downgrades are now tested only on the test database, which the test suite rebuilds from base on every run. | Resolved |
| 118 | Git | Keeping the Next.js upgrade in its own commit while Phase 3 was uncommitted. | Both changed `package.json` and `package-lock.json` (`jsqr` and `next`). | Stashed Phase 3 (with a backup copy), upgraded and committed on a clean tree, then restored the stash. The package-file conflict was resolved by keeping the upgraded files and running `npm install jsqr` again. The restored tree matched the backup. Stale `.next/dev` types from the stashed `/p/[token]` route broke one typecheck; clearing `.next` fixed it. | Resolved |

## 2026-10-26: Design reference review

| # | Area | Challenge | Cause | Resolution | Status |
|---|---|---|---|---|---|
| 119 | Design | The approved UI design's sample text breaks CLAUDE.md rules 1–3: "original", a safety chip, the NAFDAC/SON banner, and results that say a number "matches an active registration". Its result boards also cover registration states that no longer exist. | The prototype was drawn during the registration-lookup phase. | Listed the text never to copy and mapped every current result to a board for layout only in `design/README.md`. CLAUDE.md now says the consumer text in the code was approved on 26 Oct 2026 and must not change without approval. `CARTON_CODE` uses the info tone and the recall result gets its own alert styling, approved by the founder. | Decision |

## 2026-10-26: Design reference

| # | Area | Challenge | Cause | Resolution | Status |
|---|---|---|---|---|---|
| 119 | Wording | The approved UI design contains text that breaks CLAUDE.md: "Na original o!", a "NOT A SAFETY TEST" chip, the NAFDAC/SON banner and the registration-lookup result copy. | The prototype was drawn for the earlier registration lookup. | `design/README.md` lists the text never to copy and maps each check result to a board for layout only. The founder chose replacements: the home tagline "Check am before you buy!" and the chip "NOT A LAB TEST". "It is not a safety test" stays blocked. | Decision |

## 2026-10-26: Design foundation (tokens and shared components)

| # | Area | Challenge | Cause | Resolution | Status |
|---|---|---|---|---|---|
| 120 | Design | The design has no dark theme, but every component had `dark:` classes. | The app started from the Next.js template. | The founder chose light only. All `dark:` classes were removed with the token swap. | Decision |
| 121 | Design | The recall result (`BATCH_OR_PRODUCT_WARNING`) has no board, so its status card border was not specified. | The prototype predates recalls. | The founder chose the alert background (`--color-alert-bg`) with no border. Icon: the warning triangle from `ResultMismatch`; body text: `--color-text`. | Decision |
| 122 | Design | The design has no clock icon for the amber status card; its icon is a calendar for "expired". | The amber board showed an expired registration. | Used the clock from the board's own "Expired" pill, so no shape was invented. | Resolved |
| 123 | Tooling | The founder asked for Playwright screenshots, but Playwright is not a project dependency and `npx playwright` wanted a browser revision that is not installed. | Only the Chromium browser build (`chromium-1243`) was installed on this machine. | Installed `playwright@1.64.1` in a throwaway scratch folder and launched the installed Chromium with `executablePath`. Check results came from the frontend test fixtures through request interception, since the seed has no raw codes. Nothing was added to the project. | Workaround |
| 124 | Tooling | Scripted class swaps failed with "missing" on strings that were visibly in the file. | Some files have CRLF line endings, so multi-line search strings did not match. | The edit script normalises to LF, edits, then restores CRLF. | Resolved |

## 2026-10-29: Scan and report screens (design)

| # | Area | Challenge | Cause | Resolution | Status |
|---|---|---|---|---|---|
| 125 | Tooling | `typecheck` and `lint` failed on `CheckPack.tsx` (`Cannot find name 'busyButtonClass'`, `'Spinner' is not defined`) and 11 `CheckPack` tests failed. | The restyle was left half-finished: the typed-code screen used the busy button and spinner without importing them, and the tests still looked for the old "Type code" tab. | Added the imports. Tests now use the Type code button and the Type code screen heading. | Resolved |
| 126 | Requirements | The Scan button label: the restyle changed "Open the camera" to "Scan QR", but the tests and the label approved on 26 Oct 2026 say "Open the camera", and no decision records a change. | Wording is approved text and must not change without approval. | Restored "Open the camera" on the scan screen and kept "Scan QR" on the typed-code screen, as in the approved tabs. The question went to the founder. | Open |
| 127 | Design | `ScanReadingHero` (the reading cards) was built but never shown, and there was no hold. | The reading state was not wired into `CheckPack`. | Wired it in after a QR read. The result waits for the last card (4.03s) and for the check; no hold under reduced motion. Recorded as D149. Tests use fake timers and a `matchMedia` stub. | Resolved |
| 128 | Requirements | The demo banner appeared twice while the camera was open: the scan screen under it and the camera dialog each drew one. | `ScanQr` is a full-screen layer on top of the scan screen, which stayed mounted. | `CheckPack` renders the camera screen alone while it is open. New `demoBanner.test.tsx` counts the banner on every consumer screen and result state (exactly one). | Resolved |
| 129 | Tooling | The first two `CheckPack` QR tests timed out at 1s after the hold was added. | `findBy` waits 1s; the reading step now lasts 4.03s. | Those two tests stub reduced motion, since they test the camera and the request. The hold has its own tests. | Resolved |
| 130 | Git | `frontend/screenshots/` was ignored only through the local `.git/info/exclude`, so a fresh clone could commit it. | Local exclude is not shared. | Added `/screenshots/` to `frontend/.gitignore`. | Resolved |

## 2026-10-30: Phase 4, merchant page

| # | Area | Challenge | Cause | Resolution | Status |
|---|---|---|---|---|---|
| 131 | Infra | Backend tests gave 430 `OperationalError`s, and `docker start foodlens-db-1` and `docker inspect` hung. | The Docker Desktop daemon had stopped (`open //./pipe/docker_engine: The system cannot find the file specified`). | Started Docker Desktop and waited for `docker info`; the database came up healthy and all backend tests passed. | Resolved |
| 132 | Tooling | `cloudflared` was not installed for the phone test. | Not a project dependency. | Downloaded the official Windows release into the session scratch folder and ran a quick tunnel from there. Nothing added to the repo. | Workaround |
| 133 | Labels | QR labels generated earlier pointed at `http://localhost:3000`, so a phone camera could not open them. | `PUBLIC_BASE_URL` defaults to localhost. | Started the API with `PUBLIC_BASE_URL` set to the tunnel URL in the process environment only (`.env` unchanged) and generated fresh codes. Labels made through a quick tunnel stop working when the tunnel URL changes. | Workaround |
| 134 | Tooling | Two `pytest` runs at once failed with database errors. | Both rebuild the same test database from base. | Run one suite at a time. | Resolved |
| 135 | Tooling | Shell heredocs failed with "unexpected EOF while looking for matching `'`" when the text held apostrophes (can't, isn't). | The Bash tool wrapper mis-parses quoted heredocs that contain `'`. | Wrote files with the editor tool and ran small scripts from files instead of heredocs. | Workaround |
| 136 | Frontend | `/merchant` returned 500: "Functions are not valid as a child of Client Components". Unit tests passed. | The server page passed a render function as children to the client `MerchantShell`; tests render client-side only. | Moved the render function into client screen components (`MerchantRecordScreen`, `MerchantTeamScreen`); checked both routes return 200 and took screenshots in a real browser. | Resolved |
| 137 | Requirements | Several merchant details were not specified: what to do when one pack in a carton cannot take the event, which location gives the area, how a quantity allocation "counts down", what a lookup shows when nothing is allowed, and the transfer state. | D112, D113, D140 and D142 describe the rules, not these edges. | Recorded as D150: carton events are all or nothing; the area comes from the oldest reviewed location with an area; quantity left is the allocation minus earlier in-allocation receipts for the same batch, company and area; a lookup with no allowed event returns the reason; TRANSFERRED sets `IN_TRANSIT` with the receiver as holder. | Decision |
| 138 | Design | There is no board for the merchant page or the team page. | The prototype predates the merchant flow. | Composed from the workspace shell (Supplier.dc.html), the scan screen, the code field (Confirm.dc.html), radio cards (Report.dc.html), status pills and panels. The shell keeps the demo banner above it, which the Supplier board does not show. | Decision |
| 139 | Data | No company could record merchant events from the UI: a location added at `/company` never got an `area_id`, and the demo distributor had no location at all. | `add_location` stored only the free-text area; only the seed matched it to a seeded city. | `add_location` now uses the seed's rule (the first comma-separated part naming a seeded city, case-insensitive) through `companies.area_from_text`; no match leaves it empty. The seed gives Demo Market Traders a reviewed Lagos location. Tested. | Resolved |
| 140 | Tooling | The running dev API answered 404 for the new merchant routes. | `fastapi dev` reloaded once and then stopped picking up new files. | Restarted the API (same `PUBLIC_BASE_URL`); an end-to-end run through the Next.js proxy then received, sold, returned and checked a released code. | Resolved |
