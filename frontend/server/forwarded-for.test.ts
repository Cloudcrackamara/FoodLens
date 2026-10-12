import { describe, expect, it } from "vitest";
import {
  clientAddress,
  normalizeAddress,
  setForwardedFor,
  tunnelOptionsFromEnv,
} from "./forwarded-for.mjs";

function request(remoteAddress: string | undefined, headers: Record<string, string> = {}) {
  return { socket: { remoteAddress }, headers: { ...headers } };
}

const tunnelOn = { trustCloudflareTunnel: true, cloudflaredIps: ["127.0.0.1", "::1"] };
const tunnelOff = { trustCloudflareTunnel: false, cloudflaredIps: ["127.0.0.1", "::1"] };

describe("without a tunnel (default)", () => {
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

  it("removes client-supplied Forwarded and CF-Connecting-IP headers", () => {
    const req = request("203.0.113.9", { forwarded: "for=1.1.1.1", "cf-connecting-ip": "1.1.1.1" });

    setForwardedFor(req, tunnelOff);

    expect(req.headers).not.toHaveProperty("forwarded");
    expect(req.headers).not.toHaveProperty("cf-connecting-ip");
  });

  it("ignores CF-Connecting-IP when the tunnel option is off, even from localhost", () => {
    const req = request("127.0.0.1", { "cf-connecting-ip": "198.51.100.7" });

    expect(clientAddress(req, tunnelOff)).toBe("127.0.0.1");
  });

  it("unwraps IPv4-mapped IPv6 addresses", () => {
    expect(clientAddress(request("::ffff:192.168.1.20"))).toBe("192.168.1.20");
  });
});

describe("with TRUST_CLOUDFLARE_TUNNEL=true", () => {
  it("uses CF-Connecting-IP on connections from cloudflared", () => {
    const req = request("127.0.0.1", { "cf-connecting-ip": "198.51.100.7" });

    setForwardedFor(req, tunnelOn);

    expect(req.headers["x-forwarded-for"]).toBe("198.51.100.7");
  });

  it("accepts IPv6 visitors and cloudflared on ::1 or ::ffff:127.0.0.1", () => {
    expect(clientAddress(request("::1", { "cf-connecting-ip": "2001:db8::5" }), tunnelOn)).toBe(
      "2001:db8::5",
    );
    expect(
      clientAddress(request("::ffff:127.0.0.1", { "cf-connecting-ip": "198.51.100.7" }), tunnelOn),
    ).toBe("198.51.100.7");
  });

  it("ignores CF-Connecting-IP from anyone who is not cloudflared", () => {
    const req = request("192.168.1.50", { "cf-connecting-ip": "198.51.100.7" });

    setForwardedFor(req, tunnelOn);

    expect(req.headers["x-forwarded-for"]).toBe("192.168.1.50");
  });

  it("falls back to the connection address when the header is missing or not an IP", () => {
    expect(clientAddress(request("127.0.0.1"), tunnelOn)).toBe("127.0.0.1");
    expect(
      clientAddress(request("127.0.0.1", { "cf-connecting-ip": "not-an-ip" }), tunnelOn),
    ).toBe("127.0.0.1");
    expect(
      clientAddress(request("127.0.0.1", { "cf-connecting-ip": "1.1.1.1, 2.2.2.2" }), tunnelOn),
    ).toBe("127.0.0.1");
  });

  it("still overwrites a forged X-Forwarded-For", () => {
    const req = request("127.0.0.1", {
      "cf-connecting-ip": "198.51.100.7",
      "x-forwarded-for": "10.0.0.1",
    });

    setForwardedFor(req, tunnelOn);

    expect(req.headers["x-forwarded-for"]).toBe("198.51.100.7");
  });
});

describe("tunnelOptionsFromEnv", () => {
  it("is off by default and trusts loopback cloudflared when on", () => {
    expect(tunnelOptionsFromEnv({}).trustCloudflareTunnel).toBe(false);
    expect(tunnelOptionsFromEnv({ TRUST_CLOUDFLARE_TUNNEL: "true" })).toEqual({
      trustCloudflareTunnel: true,
      cloudflaredIps: ["127.0.0.1", "::1"],
    });
  });

  it("reads custom cloudflared addresses and rejects invalid ones", () => {
    expect(
      tunnelOptionsFromEnv({ TRUST_CLOUDFLARE_TUNNEL: "TRUE", CLOUDFLARED_IPS: "172.18.0.3" })
        .cloudflaredIps,
    ).toEqual(["172.18.0.3"]);
    expect(() => tunnelOptionsFromEnv({ CLOUDFLARED_IPS: "cloudflared" })).toThrow(
      /not an IP address/,
    );
  });
});

describe("normalizeAddress", () => {
  it("leaves plain IPv6 alone and handles missing addresses", () => {
    expect(normalizeAddress("::1")).toBe("::1");
    expect(normalizeAddress(undefined)).toBe("");
  });
});
