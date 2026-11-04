/**
 * QR reading in the browser only (D117, CLAUDE.md rule 9). Uses the built-in BarcodeDetector
 * where the phone has it, otherwise jsQR, which is bundled and served by FoodLens itself (no CDN).
 * Frames and photos are read from a canvas in memory and cleared straight after; no image is
 * uploaded, stored or logged. Only the decoded text leaves this module.
 */

export type QrDecoder = {
  fromVideo: (video: HTMLVideoElement) => Promise<string | null>;
  fromFile: (file: File) => Promise<string | null>;
};

type Source = CanvasImageSource & { width?: number; height?: number };

type Detector = { detect: (source: CanvasImageSource) => Promise<{ rawValue: string }[]> };

async function nativeDetector(): Promise<Detector | null> {
  const ctor = (globalThis as { BarcodeDetector?: { new (o: object): Detector; getSupportedFormats?: () => Promise<string[]> } })
    .BarcodeDetector;
  if (!ctor) return null;
  try {
    const formats = (await ctor.getSupportedFormats?.()) ?? ["qr_code"];
    return formats.includes("qr_code") ? new ctor({ formats: ["qr_code"] }) : null;
  } catch {
    return null;
  }
}

/** Longest side read by jsQR; larger frames are scaled down for speed on cheap phones. */
const MAX_SIDE = 960;

async function decodeWithJsQr(source: Source, width: number, height: number): Promise<string | null> {
  if (!width || !height) return null;
  const { default: jsQR } = await import("jsqr");
  const scale = Math.min(1, MAX_SIDE / Math.max(width, height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) return null;
  try {
    context.drawImage(source, 0, 0, canvas.width, canvas.height);
    const image = context.getImageData(0, 0, canvas.width, canvas.height);
    return jsQR(image.data, image.width, image.height, { inversionAttempts: "attemptBoth" })?.data ?? null;
  } finally {
    // Drop the pixels at once.
    canvas.width = 0;
    canvas.height = 0;
  }
}

export function createQrDecoder(): QrDecoder {
  const detector = nativeDetector();

  async function decode(source: Source, width: number, height: number): Promise<string | null> {
    const native = await detector;
    if (native) {
      try {
        const [first] = await native.detect(source);
        if (first?.rawValue) return first.rawValue;
        return null;
      } catch {
        // Fall through to jsQR.
      }
    }
    return decodeWithJsQr(source, width, height);
  }

  return {
    fromVideo: (video) => decode(video, video.videoWidth, video.videoHeight),
    fromFile: async (file) => {
      const bitmap = await createImageBitmap(file);
      try {
        return await decode(bitmap, bitmap.width, bitmap.height);
      } finally {
        bitmap.close();
      }
    },
  };
}
