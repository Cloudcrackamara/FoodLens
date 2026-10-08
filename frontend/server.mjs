// Custom Next.js server. Same as `next dev` / `next start`, except that it replaces any
// client-supplied X-Forwarded-For with the real connection address, so the API's
// per-network rate limits cannot be dodged with a forged header (docs/DECISIONS.md D45).
//
//   npm run dev     -> node server.mjs --dev
//   npm run start   -> node server.mjs        (after npm run build)
//
// If a CDN or reverse proxy is ever put in front of this server, it must be trusted here
// instead, or every visitor will share that proxy's IP.

import { createServer } from "node:http";
import next from "next";
import { setForwardedFor } from "./server/forwarded-for.mjs";

const dev = process.argv.includes("--dev");
const port = Number.parseInt(process.env.PORT ?? "3000", 10);
// Used by Next.js for dev URLs; the server still listens on all interfaces (LAN usability tests).
const hostname = "localhost";

const httpServer = createServer();
const app = next({ dev, hostname, port, httpServer });
const handle = app.getRequestHandler();

await app.prepare();

httpServer.on("request", (req, res) => {
  setForwardedFor(req);
  handle(req, res);
});

httpServer.listen(port, () => {
  console.log(`> FoodLens web on http://localhost:${port} (${dev ? "development" : "production"})`);
});
