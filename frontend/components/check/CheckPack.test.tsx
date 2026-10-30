import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DEMO_BANNER_TEXT } from "@/components/DemoDataBanner";
import type { QrDecoder } from "@/lib/qr";
import { checkFixtures, DEMO_CODE } from "@/test/checkFixtures";
import { renderWithQuery, routeFetch } from "@/test/utils";
import { CheckPack } from "./CheckPack";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function api() {
  return routeFetch({
    "GET /api/check/demo-cities": { status: 404, body: { detail: "Location simulation is off." } },
    "POST /api/check/qr": { body: checkFixtures.notSold },
  });
}

/** Every request body must be plain JSON text with no image data (CLAUDE.md rule 9). */
function expectNoImageSent(fetchMock: ReturnType<typeof api>) {
  for (const [, init = {}] of fetchMock.mock.calls) {
    const body = (init as RequestInit).body;
    expect(body === undefined || typeof body === "string").toBe(true);
    expect(String(body ?? "")).not.toMatch(/data:image|base64|blob:/i);
  }
}

function checkBodies(fetchMock: ReturnType<typeof api>) {
  return fetchMock.mock.calls
    .filter(([url]) => url === "/api/check/qr")
    .map(([, init]) => JSON.parse((init as RequestInit).body as string));
}

describe("Type code", () => {
  it("normalises the typed code before the request", async () => {
    const fetchMock = api();
    renderWithQuery(<CheckPack />);

    fireEvent.click(screen.getByRole("button", { name: "Type code" }));
    fireEvent.change(screen.getByLabelText("The code printed under the QR"), {
      target: { value: "7q2m-8kd3 xh4n oP1r 5s6t 9vOw ly" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check this code" }));

    await screen.findByText(DEMO_BANNER_TEXT, { selector: "[role=note]" });
    expect(checkBodies(fetchMock)).toEqual([
      { code: DEMO_CODE, identifier_type: "TYPED", simulated_city: null },
    ]);
    expect(screen.getByRole("heading", { level: 2, name: "In circulation, not yet sold" })).toBeInTheDocument();
  });

  it("asks for the full code instead of sending a short one", () => {
    const fetchMock = api();
    renderWithQuery(<CheckPack />);

    fireEvent.click(screen.getByRole("button", { name: "Type code" }));
    fireEvent.change(screen.getByLabelText("The code printed under the QR"), { target: { value: "7Q2M 8KD3" } });
    fireEvent.click(screen.getByRole("button", { name: "Check this code" }));

    expect(screen.getByRole("alert")).toHaveTextContent("You typed 8");
    expect(checkBodies(fetchMock)).toEqual([]);
  });
});

/** The hold on the reading step is for motion; these tests are about the camera and the request. */
function reduceMotion() {
  vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
}

describe("Scan QR", () => {
  function fakeCamera() {
    const stop = vi.fn();
    const stream = { getTracks: () => [{ stop }] } as unknown as MediaStream;
    const getUserMedia = vi.fn().mockResolvedValue(stream);
    vi.stubGlobal("navigator", { ...navigator, mediaDevices: { getUserMedia } });
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    Object.defineProperty(HTMLMediaElement.prototype, "readyState", { configurable: true, get: () => 4 });
    return { stop, getUserMedia };
  }

  it("checks the code from the QR link, sends no image, and stops the camera", async () => {
    reduceMotion();
    const camera = fakeCamera();
    const fetchMock = api();
    const decoder: QrDecoder = {
      fromVideo: vi.fn().mockResolvedValue(`https://foodlens.online/p/${DEMO_CODE}`),
      fromFile: vi.fn(),
    };
    renderWithQuery(<CheckPack decoder={decoder} />);

    fireEvent.click(screen.getByRole("button", { name: "Open the camera" }));

    await screen.findByRole("heading", { level: 2, name: "In circulation, not yet sold" });
    expect(camera.getUserMedia).toHaveBeenCalledWith({ video: { facingMode: { ideal: "environment" } }, audio: false });
    expect(camera.stop).toHaveBeenCalled();
    expect(checkBodies(fetchMock)).toEqual([{ code: DEMO_CODE, identifier_type: "QR", simulated_city: null }]);
    expectNoImageSent(fetchMock);
  });

  it("stops the camera when the scanner is closed", async () => {
    const camera = fakeCamera();
    api();
    const decoder: QrDecoder = { fromVideo: vi.fn().mockResolvedValue(null), fromFile: vi.fn() };
    renderWithQuery(<CheckPack decoder={decoder} />);

    fireEvent.click(screen.getByRole("button", { name: "Open the camera" }));
    await waitFor(() => expect(camera.getUserMedia).toHaveBeenCalled());
    await act(async () => {});
    fireEvent.click(screen.getByRole("button", { name: "Close" }));

    expect(camera.stop).toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("keeps scanning when the QR is not a FoodLens code", async () => {
    fakeCamera();
    const fetchMock = api();
    const decoder: QrDecoder = { fromVideo: vi.fn().mockResolvedValue("https://example.test/menu"), fromFile: vi.fn() };
    renderWithQuery(<CheckPack decoder={decoder} />);

    fireEvent.click(screen.getByRole("button", { name: "Open the camera" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("not a FoodLens pack code");
    expect(checkBodies(fetchMock)).toEqual([]);
  });

  it("falls back to a photo without a camera, and sends only the code", async () => {
    reduceMotion();
    vi.stubGlobal("navigator", { ...navigator, mediaDevices: undefined });
    const fetchMock = api();
    const decoder: QrDecoder = { fromVideo: vi.fn(), fromFile: vi.fn().mockResolvedValue(DEMO_CODE) };
    renderWithQuery(<CheckPack decoder={decoder} />);

    fireEvent.click(screen.getByRole("button", { name: "Open the camera" }));
    expect(screen.getByText(/camera is not available/)).toBeInTheDocument();
    const photo = new File([new Uint8Array([137, 80, 78, 71])], "pack.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("Photo of the QR"), { target: { files: [photo] } });

    await screen.findByRole("heading", { level: 2, name: "In circulation, not yet sold" });
    expect(decoder.fromFile).toHaveBeenCalledWith(photo);
    expect(checkBodies(fetchMock)).toEqual([{ code: DEMO_CODE, identifier_type: "QR", simulated_city: null }]);
    expectNoImageSent(fetchMock);
  });
});

describe("Reading step", () => {
  function setup(reducedMotion: boolean) {
    const stream = { getTracks: () => [{ stop: vi.fn() }] } as unknown as MediaStream;
    vi.stubGlobal("navigator", { ...navigator, mediaDevices: { getUserMedia: vi.fn().mockResolvedValue(stream) } });
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({ matches: reducedMotion, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
    );
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    Object.defineProperty(HTMLMediaElement.prototype, "readyState", { configurable: true, get: () => 4 });
    const fetchMock = api();
    const decoder: QrDecoder = {
      fromVideo: vi.fn().mockResolvedValue(`https://foodlens.online/p/${DEMO_CODE}`),
      fromFile: vi.fn(),
    };
    renderWithQuery(<CheckPack decoder={decoder} />);
    fireEvent.click(screen.getByRole("button", { name: "Open the camera" }));
    return fetchMock;
  }

  it("shows the three cards and holds the result until they have landed", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchMock = setup(false);

    expect(await screen.findByText("QR code read")).toBeInTheDocument();
    expect(screen.getByText(/Checking this code/)).toBeInTheDocument();
    expect(screen.getByText("Code ending", { exact: false })).toHaveTextContent("Code ending 0W1Y");

    // The check has returned, but the result still waits for the cards.
    await waitFor(() => expect(checkBodies(fetchMock)).toHaveLength(1));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3800);
    });
    expect(screen.queryByRole("heading", { level: 2, name: "In circulation, not yet sold" })).not.toBeInTheDocument();
    expect(screen.getByText("QR code read")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(400);
    });
    expect(screen.getByRole("heading", { level: 2, name: "In circulation, not yet sold" })).toBeInTheDocument();
    expect(screen.queryByText("QR code read")).not.toBeInTheDocument();
  });

  it("does not hold the result under reduced motion", async () => {
    setup(true);

    expect(await screen.findByRole("heading", { level: 2, name: "In circulation, not yet sold" })).toBeInTheDocument();
    expect(screen.queryByText("QR code read")).not.toBeInTheDocument();
  });
});

describe("Scan screen help", () => {
  function refuseCamera(name: string) {
    const getUserMedia = vi.fn().mockRejectedValue(new DOMException("camera refused", name));
    vi.stubGlobal("navigator", { ...navigator, mediaDevices: { getUserMedia } });
  }

  it("explains how to allow the camera when permission was denied", async () => {
    refuseCamera("NotAllowedError");
    api();
    renderWithQuery(<CheckPack decoder={{ fromVideo: vi.fn(), fromFile: vi.fn() }} />);

    fireEvent.click(screen.getByRole("button", { name: "Open the camera" }));

    expect(
      await screen.findByText(
        "We can't use the camera. If you blocked camera access, allow it in your browser settings, or take or choose a photo of the QR instead.",
      ),
    ).toBeInTheDocument();
  });

  it("keeps the plain message when the camera fails for another reason", async () => {
    refuseCamera("NotFoundError");
    api();
    renderWithQuery(<CheckPack decoder={{ fromVideo: vi.fn(), fromFile: vi.fn() }} />);

    fireEvent.click(screen.getByRole("button", { name: "Open the camera" }));

    expect(
      await screen.findByText("The camera is not available. Take or choose a photo of the QR instead."),
    ).toBeInTheDocument();
  });

  it.each([
    ["with a camera", () => fakeCameraOn()],
    ["without a camera", () => vi.stubGlobal("navigator", { ...navigator, mediaDevices: undefined })],
  ])("always offers Type the code instead (%s), which opens the Type code screen", async (_, setup) => {
    setup();
    api();
    renderWithQuery(<CheckPack decoder={{ fromVideo: vi.fn().mockResolvedValue(null), fromFile: vi.fn() }} />);

    fireEvent.click(screen.getByRole("button", { name: "Open the camera" }));
    await act(async () => {});
    fireEvent.click(screen.getByRole("button", { name: "Type the code instead" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Type code" })).toBeInTheDocument();
    expect(screen.getByLabelText("The code printed under the QR")).toBeInTheDocument();
  });

  it("tells the person only the code is sent", () => {
    api();
    renderWithQuery(<CheckPack />);

    expect(
      screen.getByText("Your photo is read on your phone and never uploaded. Only the pack code is sent to check it."),
    ).toBeInTheDocument();
  });
});

function fakeCameraOn() {
  const stream = { getTracks: () => [{ stop: vi.fn() }] } as unknown as MediaStream;
  vi.stubGlobal("navigator", { ...navigator, mediaDevices: { getUserMedia: vi.fn().mockResolvedValue(stream) } });
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
}

describe("Demo location", () => {
  it("sends the chosen demo city only when the API offers the picker", async () => {
    const fetchMock = routeFetch({
      "GET /api/check/demo-cities": { body: [{ city: "Kano", state: "Kano" }] },
      "POST /api/check/qr": { body: checkFixtures.notSold },
    });
    renderWithQuery(<CheckPack />);

    fireEvent.change(await screen.findByLabelText("Demo: check as if from"), { target: { value: "Kano" } });
    fireEvent.click(screen.getByRole("button", { name: "Type code" }));
    fireEvent.change(screen.getByLabelText("The code printed under the QR"), { target: { value: DEMO_CODE } });
    fireEvent.click(screen.getByRole("button", { name: "Check this code" }));

    await screen.findByRole("heading", { level: 2 });
    expect(checkBodies(fetchMock)[0].simulated_city).toBe("Kano");
  });

  it("hides the picker when location simulation is off", async () => {
    const fetchMock = api();
    renderWithQuery(<CheckPack />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(screen.queryByLabelText("Demo: check as if from")).not.toBeInTheDocument();
  });
});
