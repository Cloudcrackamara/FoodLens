#!/usr/bin/env node
// Reset the local database to the demo scenario in one go:
//   1. Postgres (Docker Compose), wait until healthy
//   2. Alembic migrations
//   3. Delete ALL data in DATABASE_URL (accounts included) and seed afresh
// The seed refuses before deleting anything unless APP_ENV=development and POS_SECRET_KEY,
// SEED_ADMIN_EMAIL, SEED_ADMIN_PASSWORD and SEED_DEMO_PASSWORD are set in backend/.env.
// The API and web app can stay running.
//
//   node scripts/reset-demo.mjs            (from the repo root)

import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const backend = join(root, "backend");

function run(command, cwd) {
  const result = spawnSync(command, { cwd, shell: true, stdio: "inherit" });
  if (result.status !== 0) {
    console.error(`\nFailed: ${command} (in ${cwd})`);
    process.exit(result.status ?? 1);
  }
}

function waitForDatabase() {
  for (let i = 0; i < 60; i += 1) {
    const result = spawnSync("docker compose ps db --format {{.Health}}", {
      cwd: root,
      shell: true,
      encoding: "utf8",
    });
    if (result.stdout?.trim() === "healthy") return;
    spawnSync(process.platform === "win32" ? "timeout /t 1 >nul" : "sleep 1", { shell: true });
  }
  console.error("Postgres did not become healthy. Is Docker Desktop running?");
  process.exit(1);
}

console.log("\n> Starting Postgres (Docker Compose)");
run("docker compose up -d db", root);
waitForDatabase();

console.log("\n> Applying migrations");
run("uv run alembic upgrade head", backend);

console.log("\n> Resetting and seeding the demo scenario");
run("uv run python -m app.seed --reset", backend);

console.log("\nDemo data is ready. Codes, logins and the walkthrough: README.md, docs/DEMO_SCRIPT.md");
