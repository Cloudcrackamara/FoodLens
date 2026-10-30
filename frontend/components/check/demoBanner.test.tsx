import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DEMO_BANNER_TEXT } from "@/components/DemoDataBanner";
import { SiteChrome } from "@/components/SiteChrome";
import type { QrDecoder } from "@/lib/qr";
import { checkFixtures, DEMO_CODE } from "@/test/checkFixtures";
import { renderWithQuery, routeFetch } from "@/test/utils";
import { CheckPack } from "./CheckPack";
import { LinkCheck } from "./LinkCheck";

let pathname = "/";
vi.mock("next/navigation", () => ({ usePathname: () => pathname, useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  pathname = "/";
});

/** CLAUDE.md rule 2: the banner is on every consumer screen, once. */
const banners = () => screen.queryAllByText(DEMO_BANNER_TEXT, { selector: "[role=note]" });

function api(qr: object = checkFixtures.notSold, status = 200) {
  return routeFetch({
    "GET /api/check/demo-cities": { status: 404, body: { detail: "off" } },
    "POST /api/check/qr": { status, body: qr },
  });
}

function fakeCamera(code: string | null) {
  const stream = { getTracks: () => [{ stop: vi.fn() }] } as unknown as MediaStream;
  vi.stubGlobal("navigator", { ...navigator, mediaDevices: { getUserMedia: vi.fn().mockResolvedValue(stream) } });
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
  Object.defineProperty(HTMLMediaElement.prototype, "readyState", { configurable: true, get: () => 4 });
  const decoder: QrDecoder = {
    fromVideo: vi.fn().mockResolvedValue(code && `https://foodlens.online/p/${code}`),
    fromFile: vi.fn(),
  };
  return decoder;
}

function typeAndCheck() {
  fireEvent.click(screen.getByRole("button", { name: "Type code" }));
  fireEvent.change(screen.getByLabelText("The code printed under the QR"), { target: { value: DEMO_CODE } });
  fireEvent.click(screen.getByRole("button", { name: "Check this code" }));
}

describe("demo banner on /check", () => {
  it("is shown once on the ready, camera and typed-code screens", async () => {
    api();
    renderWithQuery(<CheckPack decoder={fakeCamera(null)} />);
    expect(banners()).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "Open the camera" }));
    await act(async () => {});
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(banners()).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "Type the code instead" }));
    expect(screen.getByRole("heading", { level: 1, name: "Type code" })).toBeInTheDocument();
    expect(banners()).toHaveLength(1);
  });

  it("is shown once while reading and on the result, with the site banner left off", async () => {
    pathname = "/check";
    vi.useFakeTimers({ shouldAdvanceTime: true });
    api();
    renderWithQuery(
      <>
        <SiteChrome />
        <CheckPack decoder={fakeCamera(DEMO_CODE)} />
      </>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Open the camera" }));

    expect(await screen.findByText("QR code read")).toBeInTheDocument();
    expect(banners()).toHaveLength(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4100);
    });
    await screen.findByRole("heading", { level: 2, name: "In circulation, not yet sold" });
    expect(banners()).toHaveLength(1);
  });

  it("is shown once on a typed-code result", async () => {
    api();
    renderWithQuery(<CheckPack />);
    typeAndCheck();
    await screen.findByRole("heading", { level: 2 });
    expect(banners()).toHaveLength(1);
  });

  it("is shown once when the check fails", async () => {
    api({ detail: "Too many checks. Try again later." }, 429);
    renderWithQuery(<CheckPack />);
    typeAndCheck();
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(banners()).toHaveLength(1);
  });
});

describe("demo banner on /p/{token}", () => {
  it("is shown once for a bad link, while checking and on a result", async () => {
    api();
    const bad = renderWithQuery(<LinkCheck token="not a code" />);
    expect(banners()).toHaveLength(1);
    bad.unmount();

    renderWithQuery(<LinkCheck token={DEMO_CODE} />);
    expect(banners()).toHaveLength(1);
    await screen.findByRole("heading", { level: 2 });
    expect(banners()).toHaveLength(1);
  });

  it("is shown once when the check fails", async () => {
    api({ detail: "Too many checks. Try again later." }, 429);
    renderWithQuery(<LinkCheck token={DEMO_CODE} />);
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(banners()).toHaveLength(1);
  });
});

describe("site banner", () => {
  it("is on pages outside the consumer check, and not duplicated on the check pages", () => {
    api();
    pathname = "/";
    const home = renderWithQuery(<SiteChrome />);
    expect(banners()).toHaveLength(1);
    home.unmount();

    for (const path of ["/check", "/p/7Q2M"]) {
      pathname = path;
      const { unmount } = renderWithQuery(<SiteChrome />);
      expect(banners()).toHaveLength(0);
      unmount();
    }
  });
});
