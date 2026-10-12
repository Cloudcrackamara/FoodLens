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
| 39 | Requirements | New request: products and batches go live without admin review, which contradicted rule 4, rule 5, and D23. | Student simplified the workflow. | Rules and decisions updated (D61-D63); the credential review remains the gate, so unreviewed products never show "Demo record found". | Decision |
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
| 47 | Requirements | Camera OCR requested, but CLAUDE.md said "never add OCR". | Rule written before scanning was wanted. | Student approved changing it to "OCR only in the browser; no image leaves the device" (D88). | Decision |
| 48 | Phone testing | The student uses an iPhone, so USB port forwarding (Android only) cannot give the camera an HTTPS page. | Browsers only allow the camera on HTTPS or localhost. | Cloudflare quick tunnel is the default; mkcert documented as a backup (README). | Decision |
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
| 62 | Wording | The live smoke test showed "Sample Honey" as "Active" on the supplier page, though its number belongs to another product and company. | The first version only checked the register status, not the names (D83). | Added `REGISTERED_TO_ANOTHER_PRODUCT` ("Number belongs to a different product or company in the simulated register (demo data)"), same name check as lookups (D100). Reuses approved lookup wording; flagged for the student. | Decision |
| 63 | Requirements | Seed orders need user accounts, but seeded companies have none, and a default password in the code would be a secret. | Orders reference `created_by_user_id`. | Demo accounts get a password only from `SEED_DEMO_PASSWORD`; otherwise login is impossible (D101). | Decision |

## 2026-10-12 — Closing Phase 4

| # | Area | Challenge | Cause | Resolution | Status |
|---|---|---|---|---|---|
| 64 | Scope | Seven Phase 4 checklist items were still unticked after Phase 7. | Most were covered by tests written in Phases 4-7 but never ticked; contact-detail editing was never built (marked "optional"). | Matched each item to its tests; built the owner contact edit with audit (D103); added a test that products and batches have no direct edit routes. | Resolved |
