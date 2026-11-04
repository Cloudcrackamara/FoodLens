import { describe, expect, it } from "vitest";
import { codeFromQrText, groupCode, isWellFormedCode, normaliseCode } from "./check";

const CODE = "7Q2M8KD3XH4N0P1R5S6T9V0W1Y";

describe("normaliseCode (D138)", () => {
  it("upper-cases, drops spaces and hyphens, reads O as 0 and I or L as 1", () => {
    expect(normaliseCode("7q2m-8kd3 xh4n oP1r 5s6t 9vOw ly")).toBe(CODE);
    expect(normaliseCode("i-L-l-I o O")).toBe("111100");
  });
});

describe("codeFromQrText", () => {
  it("reads the code from a FoodLens link on any host", () => {
    expect(codeFromQrText(`https://foodlens.online/p/${CODE}`)).toBe(CODE);
    expect(codeFromQrText(`http://localhost:3000/p/${CODE.toLowerCase()}/`)).toBe(CODE);
  });

  it("reads a bare code", () => {
    expect(codeFromQrText(` ${groupCode(CODE)} `)).toBe(CODE);
  });

  it("refuses other QR content", () => {
    expect(codeFromQrText("https://example.test/menu")).toBeNull();
    expect(codeFromQrText("WIFI:S:Demo;;")).toBeNull();
    expect(codeFromQrText(`https://foodlens.online/p/${CODE.slice(0, 20)}`)).toBeNull();
  });
});

describe("helpers", () => {
  it("groups in fours with a last group of two", () => {
    expect(groupCode(CODE)).toBe("7Q2M 8KD3 XH4N 0P1R 5S6T 9V0W 1Y");
  });

  it("accepts only 26 Crockford characters", () => {
    expect(isWellFormedCode(CODE)).toBe(true);
    expect(isWellFormedCode(`${CODE.slice(0, 25)}U`)).toBe(false);
    expect(isWellFormedCode(CODE.slice(1))).toBe(false);
  });
});
