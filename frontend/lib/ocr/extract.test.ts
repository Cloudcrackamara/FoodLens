import { describe, expect, it } from "vitest";
import { extractNumber, fixDigitConfusions, normalizeOcrText } from "./extract";

describe("registration number from OCR text", () => {
  it.each([
    ["NAFDAC REG NO: A1-1234", "A1-1234"],
    ["NAFDAC Reg. No. 01-2345", "01-2345"],
    ["NAFDAC NO A7-0921L", "A7-0921L"],
    ["Reg No 04-5578", "04-5578"],
    ["NAFDAC REGISTRATION NUMBER B1 4567", "B1-4567"],
    ["NAFDACNO A1-1234", "A1-1234"],
    ["SON MANCAP NO MC-2019-0042", "MC-2019-0042"],
    ["nafdac reg no demo-nafdac-0001", "DEMO-NAFDAC-0001"],
    ["NAFDAC REG NO A1 — 1234", "A1-1234"],
  ])("reads %j", (text, expected) => {
    expect(extractNumber(text, "registration").value).toBe(expected);
  });

  it("fixes O/0 and I/1 confusions in the digit part only", () => {
    expect(extractNumber("NAFDAC REG NO A1-1O34", "registration").value).toBe("A1-1034");
    expect(extractNumber("NAFDAC REG NO 0I-23S4", "registration").value).toBe("01-2354");
  });

  it("finds an unlabelled number by its shape when the label was not captured", () => {
    expect(extractNumber("Demo Harvest Palm Oil\nA1-1234\n1 Litre", "registration").value).toBe(
      "A1-1234",
    );
  });

  it("does not return the batch number as the registration number", () => {
    const text = "BATCH NO 210345\nNAFDAC REG NO A1-1234";

    expect(extractNumber(text, "registration")).toEqual({
      value: "A1-1234",
      candidates: ["A1-1234"],
    });
  });

  it("returns nothing when no number-like text was read", () => {
    expect(extractNumber("PURE PALM OIL", "registration")).toEqual({ value: null, candidates: [] });
    expect(extractNumber("", "registration").value).toBeNull();
  });
});

describe("batch number from OCR text", () => {
  it.each([
    ["BATCH NO: 210345", "210345"],
    ["Batch 2109A", "2109A"],
    ["BN 23-0412", "23-0412"],
    ["B/N KT2307", "KT2307"],
    ["LOT L2309-05", "L2309-05"],
    ["LOT NO 0045B", "0045B"],
    ["BATCHNO 7781", "7781"],
  ])("reads %j", (text, expected) => {
    expect(extractNumber(text, "batch").value).toBe(expected);
  });

  it("ignores dates after EXP / MFD labels", () => {
    const text = "MFD 01-2026 EXP 12-2027\nBATCH 77801";

    expect(extractNumber(text, "batch").value).toBe("77801");
    expect(extractNumber(text, "batch").candidates).not.toContain("12-2027");
  });

  it("does not offer unlabelled dates as batch numbers", () => {
    expect(extractNumber("12-05-2027 KT2307", "batch").value).toBe("KT2307");
  });

  it("does not return the NAFDAC number as the batch number", () => {
    expect(extractNumber("NAFDAC REG NO A1-1234\nLOT 5521", "batch").value).toBe("5521");
  });

  it("lists other likely readings as candidates", () => {
    const { candidates } = extractNumber("BATCH 2109A\nX7781 Q-1234", "batch");

    expect(candidates[0]).toBe("2109A");
    expect(candidates.length).toBeGreaterThan(1);
  });
});

describe("labels glued to the number (OCR dropped the spaces)", () => {
  it.each([
    ["NAFDACREGNOA1-1234", "registration", "A1-1234"],
    ["NAFDACNo01-2345", "registration", "01-2345"],
    ["REGNO04-5578", "registration", "04-5578"],
    ["BATCHNOKT2307EXP122027", "batch", "KT2307EXP122027"],
    ["LOT2309-05", "batch", "2309-05"],
    ["BN230412", "batch", "230412"],
  ] as const)("reads %j", (text, kind, expected) => {
    expect(extractNumber(text, kind).value).toBe(expected);
  });

  it("does not split ordinary words or DEMO- numbers", () => {
    expect(extractNumber("NAFDAC REG NO DEMO-NAFDAC-0001", "registration").value).toBe(
      "DEMO-NAFDAC-0001",
    );
    expect(extractNumber("BATCHES ARE PRINTED", "batch").value).toBeNull();
  });
});

describe("helpers", () => {
  it("normalises spacing around hyphens and strips punctuation", () => {
    expect(normalizeOcrText("Reg. No.: A1 -1234\n\n lot: 55")).toEqual([
      ["REG", "NO", "A1-1234"],
      ["LOT", "55"],
    ]);
  });

  it("leaves letter-heavy parts alone", () => {
    expect(fixDigitConfusions("DEMO-NAFDAC-0O01")).toBe("DEMO-NAFDAC-0001");
    expect(fixDigitConfusions("KT2307")).toBe("KT2307");
    expect(fixDigitConfusions("A1-1S34")).toBe("A1-1534");
  });
});
