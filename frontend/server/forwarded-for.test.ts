import { describe, expect, it } from "vitest";
import { normalizeAddress, setForwardedFor } from "./forwarded-for.mjs";

function request(remoteAddress: string | undefined, headers: Record<string, string> = {}) {
  return { socket: { remoteAddress }, headers: { ...headers } };
}

describe("setForwardedFor", () => {
  it("replaces a forged X-Forwarded-For with the connection address", () => {
    const req = request("203.0.113.9", { "x-forwarded-for": "198.51.100.1, 198.51.100.2" });

    setForwardedFor(req);

    expect(req.headers["x-forwarded-for"]).toBe("203.0.113.9");
  });

  it("sets the header when the client sent none", () => {
    const req = request("203.0.113.9");

    setForwardedFor(req);

    expect(req.headers["x-forwarded-for"]).toBe("203.0.113.9");
  });

  it("removes a client-supplied Forwarded header", () => {
    const req = request("203.0.113.9", { forwarded: "for=198.51.100.1" });

    setForwardedFor(req);

    expect(req.headers).not.toHaveProperty("forwarded");
  });

  it("unwraps IPv4-mapped IPv6 addresses", () => {
    const req = request("::ffff:192.168.1.20");

    setForwardedFor(req);

    expect(req.headers["x-forwarded-for"]).toBe("192.168.1.20");
  });
});

describe("normalizeAddress", () => {
  it("leaves plain IPv6 alone and handles missing addresses", () => {
    expect(normalizeAddress("::1")).toBe("::1");
    expect(normalizeAddress(undefined)).toBe("");
  });
});
