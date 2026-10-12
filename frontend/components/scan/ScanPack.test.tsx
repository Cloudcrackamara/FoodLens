import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LookupForm } from "@/components/lookup/LookupForm";
import { lookupFixtures } from "@/test/lookupFixtures";
import { mockFetch, renderWithQuery } from "@/test/utils";
import { ScanPack, type ScanReader } from "./ScanPack";

function fakeReader(texts: Partial<Record<"video" | "file", string[]>> = {}): ScanReader {
  const video = [...(texts.video ?? [])];
  const file = [...(texts.file ?? [])];
  return {
    prepare: vi.fn(async () => undefined),
    fromVideo: vi.fn(async () => video.shift() ?? ""),
    fromFile: vi.fn(async () => file.shift() ?? ""),
    release: vi.fn(async () => undefined),
  };
}

function photo(name = "pack.jpg") {
  return new File([new Uint8Array([0xff, 0xd8, 0xff])], name, { type: "image/jpeg" });
}

async function choosePhoto(file = photo()) {
  fireEvent.change(await screen.findByLabelText("Photo of the number"), { target: { files: [file] } });
}

function withCamera() {
  const stop = vi.fn();
  const stream = { getTracks: () => [{ stop }] } as unknown as MediaStream;
  const getUserMedia = vi.fn(async () => stream);
  vi.stubGlobal("navigator", { ...navigator, mediaDevices: { getUserMedia } });
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
  return { getUserMedia, stop };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ScanPack without a camera (photo fallback)", () => {
  it("reads both numbers from photos and shows them for confirmation", async () => {
    const reader = fakeReader({ file: ["NAFDAC REG NO: A1-1O34", "BATCH NO 2109A"] });
    const onConfirm = vi.fn();
    render(<ScanPack reader={reader} onConfirm={onConfirm} onCancel={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "Scan the NAFDAC or SON number" })).toBeInTheDocument();
    expect(screen.getByText(/never uploaded or saved/)).toBeInTheDocument();
    await choosePhoto();
    await screen.findByRole("heading", { name: "Scan the batch number (optional)" });
    await choosePhoto();

    const form = await screen.findByRole("form", { name: "Check what was read" });
    expect(within(form).getByLabelText("NAFDAC or SON number on the pack")).toHaveValue("A1-1034");
    expect(within(form).getByLabelText("Batch number (optional)")).toHaveValue("2109A");
    expect(reader.fromFile).toHaveBeenCalledTimes(2);
  });

  it("lets the person edit what was read before checking", async () => {
    const onConfirm = vi.fn();
    render(<ScanPack reader={fakeReader({ file: ["NAFDAC NO A1-1234"] })} onConfirm={onConfirm} onCancel={vi.fn()} />);

    await choosePhoto();
    fireEvent.click(await screen.findByRole("button", { name: "Skip batch number" }));
    const field = await screen.findByLabelText("NAFDAC or SON number on the pack");
    fireEvent.change(field, { target: { value: "A1-1235" } });
    fireEvent.change(screen.getByLabelText("Batch number (optional)"), { target: { value: "LOT9" } });
    fireEvent.click(screen.getByRole("button", { name: "Check the register" }));

    expect(onConfirm).toHaveBeenCalledWith({ registrationNumber: "A1-1235", batchNumber: "LOT9" });
  });

  it("offers other readings as one-tap choices", async () => {
    render(<ScanPack reader={fakeReader({ file: ["NAFDAC REG NO A1-1234\nB2-5678"] })} onConfirm={vi.fn()} onCancel={vi.fn()} />);

    await choosePhoto();
    fireEvent.click(await screen.findByRole("button", { name: "Skip batch number" }));
    fireEvent.click(await screen.findByRole("button", { name: "B2-5678" }));

    expect(screen.getByLabelText("NAFDAC or SON number on the pack")).toHaveValue("B2-5678");
  });

  it("says so when no number was found and keeps the check disabled until one is typed", async () => {
    render(<ScanPack reader={fakeReader({ file: ["PURE PALM OIL"] })} onConfirm={vi.fn()} onCancel={vi.fn()} />);

    await choosePhoto();
    fireEvent.click(await screen.findByRole("button", { name: "Skip batch number" }));

    expect(await screen.findByText(/No registration number was found/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check the register" })).toBeDisabled();
  });

  it("shows a friendly message when reading fails", async () => {
    const reader = fakeReader();
    reader.fromFile = vi.fn(async () => {
      throw new Error("worker crashed");
    });
    render(<ScanPack reader={reader} onConfirm={vi.fn()} onCancel={vi.fn()} />);

    await choosePhoto();

    expect(await screen.findByRole("alert")).toHaveTextContent(/Could not read that/);
    expect(screen.getByRole("heading", { name: "Scan the NAFDAC or SON number" })).toBeInTheDocument();
  });
});

describe("ScanPack with a camera", () => {
  it("uses the back camera, reads the guide box, and stops the camera afterwards", async () => {
    const { getUserMedia, stop } = withCamera();
    const reader = fakeReader({ video: ["NAFDAC REG NO A1-1234"] });
    const onCancel = vi.fn();
    const { unmount } = render(<ScanPack reader={reader} onConfirm={vi.fn()} onCancel={onCancel} />);

    const capture = await screen.findByRole("button", { name: "Capture" });
    await waitFor(() => expect(capture).toBeEnabled());
    expect(getUserMedia).toHaveBeenCalledWith(
      expect.objectContaining({ audio: false, video: expect.objectContaining({ facingMode: { ideal: "environment" } }) }),
    );
    fireEvent.click(capture);

    await screen.findByRole("heading", { name: "Scan the batch number (optional)" });
    expect(reader.fromVideo).toHaveBeenCalledTimes(1);
    expect(stop).toHaveBeenCalled(); // camera for step 1 stopped before step 2
    unmount();
    await act(async () => undefined);
    expect(reader.release).toHaveBeenCalled();
  });

  it("falls back to photos when camera permission is refused", async () => {
    vi.stubGlobal("navigator", {
      ...navigator,
      mediaDevices: { getUserMedia: vi.fn(async () => Promise.reject(new Error("NotAllowedError"))) },
    });
    render(<ScanPack reader={fakeReader()} onConfirm={vi.fn()} onCancel={vi.fn()} />);

    expect(await screen.findByLabelText("Photo of the number")).toBeInTheDocument();
  });
});

describe("Scan pack on the check page", () => {
  it("only sends the confirmed text to the lookup, never an image", async () => {
    const fetchMock = mockFetch({ status: 200, body: lookupFixtures.REGISTERED_ACTIVE });
    renderWithQuery(<LookupForm scanReader={fakeReader({ file: ["NAFDAC REG NO DEMO-NAFDAC-0001", "LOT DEMO-LOT-101"] })} />);

    fireEvent.click(screen.getByRole("button", { name: "Scan pack" }));
    await choosePhoto();
    await screen.findByRole("heading", { name: "Scan the batch number (optional)" });
    await choosePhoto();
    const confirm = await screen.findByRole("form", { name: "Check what was read" });
    expect(fetchMock).not.toHaveBeenCalled();

    fireEvent.click(within(confirm).getByRole("button", { name: "Check the register" }));

    await screen.findByRole("heading", { name: "Matches an active record in the simulated register" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/lookups/registration");
    expect(typeof init.body).toBe("string");
    expect(JSON.parse(init.body)).toEqual({
      registration_number: "DEMO-NAFDAC-0001",
      batch_number: "DEMO-LOT-101",
    });
    expect(screen.getByLabelText("NAFDAC or SON number on the pack")).toHaveValue("DEMO-NAFDAC-0001");
  });

  it("typing still works without scanning", () => {
    renderWithQuery(<LookupForm scanReader={fakeReader()} />);

    expect(screen.getByLabelText("NAFDAC or SON number on the pack")).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Scan pack" })).not.toBeInTheDocument();
  });
});
