import { describe, expect, it } from "vitest";
import {
  binarize,
  guideBoxInFrame,
  otsuThreshold,
  prepareForOcr,
  stretchContrast,
  toGreyscale,
  type Pixels,
} from "./preprocess";

function image(values: number[][], width: number): Pixels {
  const data = new Uint8ClampedArray(values.length * 4);
  values.forEach(([r, g, b], p) => data.set([r, g, b, 255], p * 4));
  return { data, width, height: values.length / width };
}

function greys(pixels: Pixels): number[] {
  return Array.from({ length: pixels.width * pixels.height }, (_, p) => pixels.data[p * 4]);
}

describe("image clean-up", () => {
  it("converts colour to greyscale luminance", () => {
    expect([...toGreyscale(image([[255, 255, 255], [0, 0, 0], [255, 0, 0]], 3))]).toEqual([
      255, 0, 76,
    ]);
  });

  it("stretches faint contrast to the full range", () => {
    const faint = new Uint8Array([100, 100, 110, 120, 130, 140, 150, 150]);

    const stretched = stretchContrast(faint);

    expect(Math.min(...stretched)).toBe(0);
    expect(Math.max(...stretched)).toBe(255);
  });

  it("finds a threshold between dark text and light background", () => {
    const grey = new Uint8Array([20, 25, 30, 200, 210, 220, 230, 240]);

    const threshold = otsuThreshold(grey);

    expect(threshold).toBeGreaterThanOrEqual(30);
    expect(threshold).toBeLessThan(200);
  });

  it("gives dark text on white, inverting light-on-dark labels", () => {
    const darkTextOnLight = new Uint8Array([10, 240, 240, 240]);
    const lightTextOnDark = new Uint8Array([240, 10, 10, 10]);

    expect(greys(binarize(darkTextOnLight, 128, 4, 1))).toEqual([0, 255, 255, 255]);
    expect(greys(binarize(lightTextOnDark, 128, 4, 1))).toEqual([0, 255, 255, 255]);
  });

  it("produces a pure black-and-white image of the same size", () => {
    const result = prepareForOcr(
      image([[30, 30, 30], [220, 220, 220], [200, 210, 220], [40, 35, 30]], 2),
    );

    expect(result.width).toBe(2);
    expect(result.height).toBe(2);
    expect(new Set(greys(result))).toEqual(new Set([0, 255]));
  });
});

describe("guideBoxInFrame", () => {
  it("maps the guide box to camera pixels when the frame matches the view", () => {
    expect(guideBoxInFrame(1000, 500, 1000, 500, { x: 100, y: 200, width: 800, height: 100 })).toEqual(
      { x: 100, y: 200, width: 800, height: 100 },
    );
  });

  it("accounts for object-fit: cover scaling and cropping", () => {
    // 1920x1080 camera shown in a 390x844 portrait view: scaled by 844/1080, sides cropped.
    const box = guideBoxInFrame(1920, 1080, 390, 844, { x: 20, y: 380, width: 350, height: 84 });
    const scale = 844 / 1080;
    const offsetX = (1920 * scale - 390) / 2;

    expect(box.x).toBe(Math.round((20 + offsetX) / scale));
    expect(box.y).toBe(Math.round(380 / scale));
    expect(box.width).toBe(Math.round(350 / scale));
    expect(box.x + box.width).toBeLessThanOrEqual(1920);
  });

  it("never goes outside the frame", () => {
    const box = guideBoxInFrame(640, 480, 640, 480, { x: -10, y: -10, width: 700, height: 600 });

    expect(box.x).toBe(0);
    expect(box.y).toBe(0);
    expect(box.width).toBeLessThanOrEqual(640);
    expect(box.height).toBeLessThanOrEqual(480);
  });
});
