// Client IP handling for the custom server (docs/DECISIONS.md D45).
//
// Next.js keeps any X-Forwarded-For header the client sends, so the API's per-network rate
// limits could be dodged by forging it. This replaces the header with the address of the
// actual TCP connection before Next.js sees the request.

/** "::ffff:192.168.1.5" -> "192.168.1.5"; other addresses unchanged. */
export function normalizeAddress(address) {
  if (!address) return "";
  return address.startsWith("::ffff:") ? address.slice("::ffff:".length) : address;
}

/** Overwrite (never append to) X-Forwarded-For with the connecting address. */
export function setForwardedFor(req) {
  delete req.headers["forwarded"];
  req.headers["x-forwarded-for"] = normalizeAddress(req.socket?.remoteAddress);
}
