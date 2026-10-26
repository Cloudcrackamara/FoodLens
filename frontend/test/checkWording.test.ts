// @vitest-environment node
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

// FoodLens's own consumer-check copy never uses these words (CLAUDE.md rule 1, D128, D141).
const BANNED = /\b(original|genuine|authentic|safe|unsafe|fake|adulteration)\b|verified by nafdac/i;
const root = join(__dirname, "..");
const checkSources = ["components/check", "app/check", "app/p", "lib/check.ts", "lib/qr.ts", "app/page.tsx"];

function files(path: string): string[] {
  const full = join(root, path);
  if (statSync(full).isFile()) return [full];
  return readdirSync(full).flatMap((name) => files(join(path, name)));
}

describe("check wording", () => {
  it("no banned word appears in the check pages and components", () => {
    const offending = checkSources
      .flatMap(files)
      .filter((path) => !/\.test\.tsx?$/.test(path))
      .filter((path) => BANNED.test(readFileSync(path, "utf8")))
      .map((path) => relative(root, path));

    expect(offending).toEqual([]);
  });
});
