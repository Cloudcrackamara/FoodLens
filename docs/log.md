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
