/**
 * In-browser OCR with Tesseract.js, loaded only when someone taps "Scan pack" (D89).
 *
 * All files come from FoodLens itself (/ocr/, copied by scripts/copy-ocr-assets.mjs), never a
 * CDN. Images are read in a Web Worker on the phone; nothing is uploaded. The browser caches the
 * English model (about 3 MB, no personal data) so later scans start faster.
 */

import type { Worker } from "tesseract.js";

export const OCR_ASSETS = {
  workerPath: "/ocr/worker.min.js",
  corePath: "/ocr/core",
  langPath: "/ocr/lang",
} as const;

/** Letters, digits and hyphens, plus the space: without it Tesseract glues words together
 *  ("NAFDACREGNOA1-1234"), as found when testing the real engine (D91). */
export const OCR_CHARACTERS =
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789- ";

export type OcrProgress = { status: string; progress: number };

let workerPromise: Promise<Worker> | null = null;
const listeners = new Set<(progress: OcrProgress) => void>();

/** Start loading the OCR engine (safe to call many times). */
export function loadOcr(onProgress?: (progress: OcrProgress) => void): Promise<Worker> {
  if (onProgress) listeners.add(onProgress);
  if (!workerPromise) {
    workerPromise = (async () => {
      const { createWorker, OEM, PSM } = await import("tesseract.js");
      const worker = await createWorker("eng", OEM.LSTM_ONLY, {
        ...OCR_ASSETS,
        workerBlobURL: false,
        gzip: true,
        logger: (message: { status: string; progress: number }) => {
          for (const listener of listeners) listener(message);
        },
      });
      await worker.setParameters({
        tessedit_char_whitelist: OCR_CHARACTERS,
        tessedit_pageseg_mode: PSM.SINGLE_BLOCK,
        preserve_interword_spaces: "1",
      });
      return worker;
    })().catch((error) => {
      workerPromise = null;
      throw error;
    });
  }
  return workerPromise;
}

/** Read text from a prepared (cropped, black-and-white) canvas. */
export async function recognize(canvas: HTMLCanvasElement): Promise<string> {
  const worker = await loadOcr();
  const { data } = await worker.recognize(canvas);
  return data.text;
}

/** Free the engine's memory (it is reloaded from cache next time). */
export async function releaseOcr(): Promise<void> {
  const pending = workerPromise;
  workerPromise = null;
  listeners.clear();
  if (pending) await (await pending).terminate();
}
