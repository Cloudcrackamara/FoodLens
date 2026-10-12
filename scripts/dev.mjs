#!/usr/bin/env node
// Start FoodLens locally in one go:
//   1. Postgres (Docker Compose), wait until healthy
//   2. Alembic migrations and the demo seed
//   3. API (http://localhost:8000) and web app (http://localhost:3000), with prefixed logs
// Press Ctrl+C to stop the API and web app. The database keeps running; stop it with
// `docker compose stop db`.
//
//   node scripts/dev.mjs            (from the repo root)

import { spawn, spawnSync } from "node:child_process";
import { createConnection } from "node:net";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const backend = join(root, "backend");
const frontend = join(root, "frontend");
const isWindows = process.platform === "win32";

function step(message) {
  console.log(`\n> ${message}`);
}

function run(command, cwd) {
  const result = spawnSync(command, { cwd, shell: true, stdio: "inherit" });
  if (result.status !== 0) {
    console.error(`\nFailed: ${command} (in ${cwd})`);
    process.exit(result.status ?? 1);
  }
}

function portInUse(port) {
  return new Promise((resolve) => {
    const socket = createConnection({ port, host: "127.0.0.1" });
    socket.once("connect", () => (socket.destroy(), resolve(true)));
    socket.once("error", () => resolve(false));
  });
}

async function waitFor(url, label, seconds = 120) {
  for (let i = 0; i < seconds; i += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // not up yet
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`${label} did not respond at ${url}`);
}

function waitForDatabase() {
  for (let i = 0; i < 60; i += 1) {
    const result = spawnSync("docker compose ps db --format {{.Health}}", {
      cwd: root,
      shell: true,
      encoding: "utf8",
    });
    if (result.stdout?.trim() === "healthy") return;
    spawnSync(isWindows ? "timeout /t 1 >nul" : "sleep 1", { shell: true });
  }
  console.error("Postgres did not become healthy. Is Docker Desktop running?");
  process.exit(1);
}

const children = [];

function start(name, command, cwd) {
  const child = spawn(command, { cwd, shell: true, stdio: ["ignore", "pipe", "pipe"] });
  const prefix = `[${name}] `;
  const forward = (stream, target) => {
    let buffer = "";
    stream.on("data", (chunk) => {
      buffer += chunk;
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() ?? "";
      for (const line of lines) target.write(prefix + line + "\n");
    });
  };
  forward(child.stdout, process.stdout);
  forward(child.stderr, process.stderr);
  child.on("exit", (code) => {
    if (!stopping) {
      console.error(`${prefix}exited with code ${code}; stopping everything.`);
      stop(1);
    }
  });
  children.push(child);
}

let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (child.exitCode !== null) continue;
    if (isWindows) {
      // shell: true wraps the server in cmd.exe; kill the whole process tree.
      spawnSync(`taskkill /pid ${child.pid} /T /F`, { shell: true, stdio: "ignore" });
    } else {
      child.kill("SIGTERM");
    }
  }
  console.log("\nAPI and web app stopped. The database is still running: docker compose stop db");
  process.exit(code);
}
process.on("SIGINT", () => stop(0));
process.on("SIGTERM", () => stop(0));

for (const port of [8000, 3000]) {
  if (await portInUse(port)) {
    console.error(
      `Port ${port} is already in use. Stop whatever is running there (maybe an earlier ` +
        "FoodLens server) and try again.",
    );
    process.exit(1);
  }
}

step("Starting Postgres (Docker Compose)");
run("docker compose up -d db", root);
waitForDatabase();

step("Applying migrations");
run("uv run alembic upgrade head", backend);

step("Seeding demo data");
run("uv run python -m app.seed", backend);

step("Starting the API and the web app");
start("api", "uv run fastapi dev app/main.py --port 8000", backend);
start("web", "npm run dev", frontend);

try {
  await waitFor("http://localhost:8000/api/health", "API");
  await waitFor("http://localhost:3000/api/health", "Web app (proxy to API)");
} catch (error) {
  console.error(`\n${error.message}`);
  stop(1);
}

console.log(`
FoodLens is running (demo data):
  Landing     http://localhost:3000/
  Check       http://localhost:3000/check
  Suppliers   http://localhost:3000/suppliers
  Company     http://localhost:3000/company
  Admin       http://localhost:3000/admin
  API docs    http://localhost:8000/docs

Press Ctrl+C to stop the API and web app. Stop the database with: docker compose stop db
`);
