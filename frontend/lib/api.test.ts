import { afterEach, describe, expect, it, vi } from "vitest";
import { mockFetch } from "@/test/utils";
import { ApiError, apiFetch, describeError } from "./api";

describe("apiFetch", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("reads Retry-After from a 429 response", async () => {
    mockFetch({
      status: 429,
      body: { detail: "Too many requests from your network. Try again in 7 seconds." },
      headers: { "Retry-After": "7" },
    });

    const error = await apiFetch("/api/anything", null).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(429);
    expect((error as ApiError).retryAfterSeconds).toBe(7);
  });
});

describe("describeError", () => {
  it("explains that rate limits are per network and when to retry", () => {
    const message = describeError(new ApiError(429, "Too many requests", 7));

    expect(message).toMatch(/same network/i);
    expect(message).toMatch(/Wi-Fi/);
    expect(message).toMatch(/try again in about 7 seconds/i);
  });

  it("uses minutes for longer waits", () => {
    expect(describeError(new ApiError(429, "x", 600))).toMatch(/in about 10 minutes/);
  });

  it("gives a general retry time without Retry-After", () => {
    expect(describeError(new ApiError(429, "x", null))).toMatch(/in a minute or two/);
  });

  it("passes other errors through unchanged", () => {
    expect(describeError(new ApiError(401, "Invalid email or password"))).toBe(
      "Invalid email or password",
    );
  });
});
