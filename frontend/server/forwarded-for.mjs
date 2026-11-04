// Client IP handling for the custom server (docs/DECISIONS.md D45, D90).
//
// Next.js keeps any X-Forwarded-For header the client sends, so the API's per-network rate
// limits could be dodged by forging it. This replaces the header with the real client address
// before Next.js sees the request:
//
// - Normally: the address of the actual TCP connection.
// - Through a Cloudflare Tunnel (only when enabled): every request arrives from the local
//   cloudflared process, so the visitor's address is taken from Cloudflare's CF-Connecting-IP
//   header, but only when the connection really comes from a trusted cloudflared address.

import { isIP } from "node:net";

/** @typedef {{ trustCloudflareTunnel: boolean, cloudflaredIps: string[] }} TunnelOptions */
/** @typedef {{ socket?: { remoteAddress?: string }, headers: Record<string, string | string[] | undefined> }} IncomingLike */

/** @type {TunnelOptions} */
const NO_TUNNEL = { trustCloudflareTunnel: false, cloudflaredIps: [] };

/**
 * "::ffff:192.168.1.5" -> "192.168.1.5"; other addresses unchanged.
 * @param {string | undefined} address
 * @returns {string}
 */
export function normalizeAddress(address) {
  if (!address) return "";
  return address.startsWith("::ffff:") ? address.slice("::ffff:".length) : address;
}

/**
 * Tunnel settings from the environment. Off by default.
 *   TRUST_CLOUDFLARE_TUNNEL=true      trust CF-Connecting-IP from cloudflared
 *   CLOUDFLARED_IPS=127.0.0.1,::1     addresses cloudflared connects from (exact IPs)
 * @param {Record<string, string | undefined>} [env]
 * @returns {TunnelOptions}
 */
export function tunnelOptionsFromEnv(env = process.env) {
  const trustCloudflareTunnel = (env.TRUST_CLOUDFLARE_TUNNEL ?? "").toLowerCase() === "true";
  const cloudflaredIps = (env.CLOUDFLARED_IPS ?? "127.0.0.1,::1")
    .split(",")
    .map((ip) => normalizeAddress(ip.trim()))
    .filter(Boolean);
  for (const ip of cloudflaredIps) {
    if (!isIP(ip)) throw new Error(`CLOUDFLARED_IPS: "${ip}" is not an IP address`);
  }
  return { trustCloudflareTunnel, cloudflaredIps };
}

/**
 * The visitor's address for this request.
 * @param {IncomingLike} req
 * @param {TunnelOptions} [options]
 * @returns {string}
 */
export function clientAddress(req, options = NO_TUNNEL) {
  const peer = normalizeAddress(req.socket?.remoteAddress);
  if (!options.trustCloudflareTunnel || !options.cloudflaredIps.includes(peer)) return peer;

  const header = req.headers["cf-connecting-ip"];
  const value = normalizeAddress(Array.isArray(header) ? header[0] : (header ?? "").trim());
  return isIP(value) ? value : peer;
}

/**
 * Overwrite (never append to) X-Forwarded-For with the visitor's address.
 * @param {IncomingLike} req
 * @param {TunnelOptions} [options]
 */
export function setForwardedFor(req, options = NO_TUNNEL) {
  const address = clientAddress(req, options);
  delete req.headers["forwarded"];
  delete req.headers["cf-connecting-ip"];
  req.headers["x-forwarded-for"] = address;
  // Cloudflare's visitor-location headers give the coarse area of a check (D118). They reach the
  // API only from a trusted cloudflared connection; anyone else could forge a city.
  if (!fromTrustedTunnel(req, options)) {
    for (const name of LOCATION_HEADERS) delete req.headers[name];
  }
}

const LOCATION_HEADERS = ["cf-ipcity", "cf-region", "cf-region-code", "cf-ipcountry"];

/**
 * @param {IncomingLike} req
 * @param {TunnelOptions} options
 */
function fromTrustedTunnel(req, options) {
  return (
    options.trustCloudflareTunnel &&
    options.cloudflaredIps.includes(normalizeAddress(req.socket?.remoteAddress))
  );
}
