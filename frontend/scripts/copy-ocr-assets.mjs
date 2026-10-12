// Copies the in-browser OCR files from node_modules into public/ocr/ so FoodLens serves them
// itself. Without this, Tesseract.js would fetch them from a CDN, letting a third party see
// who uses the scanner (docs/DECISIONS.md D89). Runs before dev and build; public/ocr is
// git-ignored.

import { copyFileSync, existsSync, mkdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const modules = join(root, "node_modules");
const target = join(root, "public", "ocr");

const files = [
  // Worker script (loaded directly, not as a blob URL).
  ["tesseract.js/dist/worker.min.js", "worker.min.js"],
  // LSTM-only engine builds; the browser downloads exactly one, matching its SIMD support.
  ["tesseract.js-core/tesseract-core-lstm.wasm.js", "core/tesseract-core-lstm.wasm.js"],
  ["tesseract.js-core/tesseract-core-simd-lstm.wasm.js", "core/tesseract-core-simd-lstm.wasm.js"],
  [
    "tesseract.js-core/tesseract-core-relaxedsimd-lstm.wasm.js",
    "core/tesseract-core-relaxedsimd-lstm.wasm.js",
  ],
  // English model, integer "best" variant (about 3 MB, already gzipped).
  ["@tesseract.js-data/eng/4.0.0_best_int/eng.traineddata.gz", "lang/eng.traineddata.gz"],
];

let copied = 0;
for (const [from, to] of files) {
  const source = join(modules, from);
  const destination = join(target, to);
  if (!existsSync(source)) {
    console.error(`copy-ocr-assets: missing ${from}; run npm install`);
    process.exit(1);
  }
  if (existsSync(destination) && statSync(destination).size === statSync(source).size) continue;
  mkdirSync(dirname(destination), { recursive: true });
  copyFileSync(source, destination);
  copied += 1;
}
console.log(`copy-ocr-assets: ${copied} file(s) copied, ${files.length - copied} up to date`);
