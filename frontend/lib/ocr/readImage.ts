/**
 * Turn a camera frame or a chosen photo into OCR text, entirely on the phone (D92-D93).
 * The image lives only in a canvas for the moment of reading; nothing is stored or sent.
 */

import { recognize } from "./engine";
import { guideBoxInFrame, prepareForOcr, type Rect } from "./preprocess";

const TARGET_WIDTH = 1400; // small print gets enlarged, huge frames reduced

function canvasFor(width: number, height: number): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  return canvas;
}

async function readRegion(source: CanvasImageSource, region: Rect): Promise<string> {
  const scale = Math.min(3, Math.max(0.5, TARGET_WIDTH / Math.max(1, region.width)));
  const width = Math.max(1, Math.round(region.width * scale));
  const height = Math.max(1, Math.round(region.height * scale));
  const canvas = canvasFor(width, height);
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) throw new Error("Canvas is not available");
  context.imageSmoothingQuality = "high";
  context.drawImage(source, region.x, region.y, region.width, region.height, 0, 0, width, height);

  const prepared = prepareForOcr(context.getImageData(0, 0, width, height));
  context.putImageData(new ImageData(prepared.data, width, height), 0, 0);
  try {
    return await recognize(canvas);
  } finally {
    // Drop the pixels straight away.
    canvas.width = 0;
    canvas.height = 0;
  }
}

/** Read the part of the live camera frame under the guide box. */
export function readFromVideo(video: HTMLVideoElement, guide: Rect): Promise<string> {
  const view = video.getBoundingClientRect();
  const region = guideBoxInFrame(video.videoWidth, video.videoHeight, view.width, view.height, guide);
  return readRegion(video, region);
}

/** Read a photo chosen or taken through the file picker (fallback when the camera is blocked). */
export async function readFromFile(file: File): Promise<string> {
  const bitmap = await createImageBitmap(file);
  try {
    return await readRegion(bitmap, { x: 0, y: 0, width: bitmap.width, height: bitmap.height });
  } finally {
    bitmap.close();
  }
}
