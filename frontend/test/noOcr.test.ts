// @vitest-environment node
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

// The OCR stack is removed (D147): FoodLens reads only the QR code, in the browser.
const root = join(__dirname, "..");
const skipped = new Set(["node_modules", ".next", "public"]);

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    if (skipped.has(name)) return [];
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return /\.(ts|tsx|js|mjs|cjs)$/.test(name) ? [path] : [];
  });
}

describe("OCR removal", () => {
  it("no frontend file imports tesseract.js", () => {
    const importers = sourceFiles(root)
      .filter((path) => !path.endsWith("noOcr.test.ts"))
      .filter((path) => /from\s+["']tesseract\.js|require\(["']tesseract\.js|import\(["']tesseract\.js/.test(readFileSync(path, "utf8")))
      .map((path) => relative(root, path));

    expect(importers).toEqual([]);
  });

  it("package.json has no OCR dependencies or asset scripts", () => {
    const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
    const deps = { ...pkg.dependencies, ...pkg.devDependencies };

    expect(Object.keys(deps).filter((name) => name.includes("tesseract"))).toEqual([]);
    expect(Object.keys(pkg.scripts).filter((name) => /ocr|predev|prebuild/.test(name))).toEqual([]);
  });
});
