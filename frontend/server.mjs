// Custom Next.js server. Same as `next dev` / `next start`, except that it replaces any
// client-supplied X-Forwarded-For with the real connection address, so the API's
// per-network rate limits cannot be dodged with a forged header (docs/DECISIONS.md D45).
//
//   npm run dev     -> node server.mjs --dev
//   npm run start   -> node server.mjs        (after npm run build)
//
// Behind a Cloudflare Tunnel (phone testing, later deployment), set TRUST_CLOUDFLARE_TUNNEL=true
// so the visitor IP comes from CF-Connecting-IP on connections from cloudflared (D90).
// Without it, every visitor would share cloudflared's local address.

import { createServer } from "node:http";
import next from "next";
import { setForwardedFor, tunnelOptionsFromEnv } from "./server/forwarded-for.mjs";

const dev = process.argv.includes("--dev");
const port = Number.parseInt(process.env.PORT ?? "3000", 10);
// Used by Next.js for dev URLs; the server still listens on all interfaces (LAN usability tests).
const hostname = "localhost";

const httpServer = createServer();
const app = next({ dev, hostname, port, httpServer });
const handle = app.getRequestHandler();

await app.prepare();
// Read after prepare(), which loads .env / .env.local into process.env.
const tunnel = tunnelOptionsFromEnv();

httpServer.on("request", (req, res) => {
  setForwardedFor(req, tunnel);
  handle(req, res);
});

httpServer.listen(port, () => {
  console.log(`> FoodLens web on http://localhost:${port} (${dev ? "development" : "production"})`);
  if (tunnel.trustCloudflareTunnel) {
    console.log(`> Trusting CF-Connecting-IP from cloudflared at ${tunnel.cloudflaredIps.join(", ")}`);
  }
});
