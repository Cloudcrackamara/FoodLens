/**
 * Image clean-up before OCR, on raw pixels (no DOM), so it can be unit-tested (D92).
 * Pipeline: greyscale -> contrast stretch -> Otsu threshold -> black text on white.
 * Everything runs on the phone; pixels are never sent anywhere.
 */

export type Pixels = { data: Uint8ClampedArray<ArrayBuffer>; width: number; height: number };
export type Rect = { x: number; y: number; width: number; height: number };

/** Luminance (ITU-R BT.601) per pixel, 0-255. */
export function toGreyscale({ data, width, height }: Pixels): Uint8Array {
  const grey = new Uint8Array(width * height);
  for (let i = 0, p = 0; p < grey.length; i += 4, p += 1) {
    grey[p] = Math.round(0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]);
  }
  return grey;
}

/** Stretch the 2nd-98th percentile range to 0-255 (helps faint or low-light print). */
export function stretchContrast(grey: Uint8Array): Uint8Array {
  const histogram = new Uint32Array(256);
  for (const value of grey) histogram[value] += 1;
  const cut = Math.floor(grey.length * 0.02);
  let low = 0;
  for (let seen = 0; low < 255 && seen + histogram[low] <= cut; low += 1) seen += histogram[low];
  let high = 255;
  for (let seen = 0; high > 0 && seen + histogram[high] <= cut; high -= 1) seen += histogram[high];
  if (high <= low) return grey.slice();
  const scale = 255 / (high - low);
  return grey.map((value) => Math.max(0, Math.min(255, Math.round((value - low) * scale))));
}

/** Otsu's threshold: the grey level that best separates text from background. */
export function otsuThreshold(grey: Uint8Array): number {
  const histogram = new Uint32Array(256);
  for (const value of grey) histogram[value] += 1;
  const total = grey.length;
  let sumAll = 0;
  for (let level = 0; level < 256; level += 1) sumAll += level * histogram[level];

  let sumBackground = 0;
  let weightBackground = 0;
  let best = 0;
  let threshold = 127;
  for (let level = 0; level < 256; level += 1) {
    weightBackground += histogram[level];
    if (weightBackground === 0) continue;
    const weightForeground = total - weightBackground;
    if (weightForeground === 0) break;
    sumBackground += level * histogram[level];
    const meanBackground = sumBackground / weightBackground;
    const meanForeground = (sumAll - sumBackground) / weightForeground;
    const between = weightBackground * weightForeground * (meanBackground - meanForeground) ** 2;
    if (between > best) {
      best = between;
      threshold = level;
    }
  }
  return threshold;
}

/** Black-and-white RGBA. Text is made dark on a light background: if most pixels end up dark
 *  (light print on a dark label), the image is inverted. */
export function binarize(grey: Uint8Array, threshold: number, width: number, height: number): Pixels {
  let dark = 0;
  for (const value of grey) if (value <= threshold) dark += 1;
  const invert = dark > grey.length / 2;
  const data = new Uint8ClampedArray(grey.length * 4);
  for (let p = 0, i = 0; p < grey.length; p += 1, i += 4) {
    const isDark = grey[p] <= threshold;
    const value = isDark !== invert ? 0 : 255;
    data[i] = value;
    data[i + 1] = value;
    data[i + 2] = value;
    data[i + 3] = 255;
  }
  return { data, width, height };
}

/** Full clean-up pipeline. */
export function prepareForOcr(image: Pixels): Pixels {
  const grey = stretchContrast(toGreyscale(image));
  return binarize(grey, otsuThreshold(grey), image.width, image.height);
}

/**
 * The part of the camera frame under the on-screen guide box. The video is shown with
 * `object-fit: cover`, so the frame is scaled up and its edges cropped; this maps the guide box
 * (in on-screen pixels, relative to the video element) back to camera-frame pixels.
 */
export function guideBoxInFrame(
  frameWidth: number,
  frameHeight: number,
  viewWidth: number,
  viewHeight: number,
  box: Rect,
): Rect {
  const scale = Math.max(viewWidth / frameWidth, viewHeight / frameHeight);
  const offsetX = (frameWidth * scale - viewWidth) / 2;
  const offsetY = (frameHeight * scale - viewHeight) / 2;
  const x = Math.max(0, Math.round((box.x + offsetX) / scale));
  const y = Math.max(0, Math.round((box.y + offsetY) / scale));
  return {
    x,
    y,
    width: Math.min(frameWidth - x, Math.round(box.width / scale)),
    height: Math.min(frameHeight - y, Math.round(box.height / scale)),
  };
}
