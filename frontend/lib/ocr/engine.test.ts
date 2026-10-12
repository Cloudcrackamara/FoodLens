import { afterEach, describe, expect, it, vi } from "vitest";

const createWorker = vi.fn();
const setParameters = vi.fn(async () => ({}));
const recognize = vi.fn(async () => ({ data: { text: "NAFDAC REG NO A1-1234" } }));
const terminate = vi.fn(async () => undefined);

vi.mock("tesseract.js", () => ({
  createWorker: async (...args: unknown[]) => {
    createWorker(...args);
    return { setParameters, recognize, terminate };
  },
  OEM: { LSTM_ONLY: 1 },
  PSM: { SINGLE_BLOCK: "6" },
}));

describe("OCR engine", () => {
  afterEach(async () => {
    const { releaseOcr } = await import("./engine");
    await releaseOcr();
    vi.clearAllMocks();
  });

  it("loads every OCR file from FoodLens itself, never a CDN", async () => {
    const { loadOcr } = await import("./engine");

    await loadOcr();

    const [lang, oem, options] = createWorker.mock.calls[0];
    expect(lang).toBe("eng");
    expect(oem).toBe(1);
    expect(options).toMatchObject({
      workerPath: "/ocr/worker.min.js",
      corePath: "/ocr/core",
      langPath: "/ocr/lang",
      workerBlobURL: false,
    });
    for (const key of ["workerPath", "corePath", "langPath"]) {
      expect(options[key]).not.toMatch(/^https?:/);
    }
  });

  it("limits recognition to letters, digits, hyphens and spaces", async () => {
    const { loadOcr, OCR_CHARACTERS } = await import("./engine");

    await loadOcr();

    expect(setParameters).toHaveBeenCalledWith(
      expect.objectContaining({ tessedit_char_whitelist: OCR_CHARACTERS }),
    );
    expect(OCR_CHARACTERS).toMatch(/^[A-Za-z0-9 -]+$/);
    expect(OCR_CHARACTERS).toContain(" ");
  });

  it("creates the engine once and reuses it", async () => {
    const { loadOcr, recognize: read } = await import("./engine");

    await Promise.all([loadOcr(), loadOcr()]);
    const text = await read(document.createElement("canvas"));

    expect(createWorker).toHaveBeenCalledTimes(1);
    expect(text).toBe("NAFDAC REG NO A1-1234");
  });

  it("frees the engine when released", async () => {
    const { loadOcr, releaseOcr } = await import("./engine");
    await loadOcr();

    await releaseOcr();

    expect(terminate).toHaveBeenCalledTimes(1);
  });
});
