/**
 * Pick the registration (NAFDAC/SON) number or batch number out of OCR text (D91).
 *
 * No single NAFDAC number format is assumed. Labels such as "NAFDAC Reg No", "Reg No",
 * "Batch", "BN", "B/N", "LOT" are the strongest clue; otherwise tokens are ranked by shape.
 * Common OCR confusions (O/0, I/1, S/5, B/8 ...) are only corrected inside digit-heavy parts.
 * The result is always shown to the person to confirm or edit before any lookup.
 */

export type ScanKind = "registration" | "batch";
export type Extraction = { value: string | null; candidates: string[] };

const MAX_CANDIDATES = 4;

const REGISTRATION_START = new Set(["NAFDAC", "SON", "MANCAP", "REG", "REGISTRATION", "REGN"]);
const BATCH_START = new Set(["BATCH", "BN", "LOT", "L"]);
// Words that may follow a label start and are part of the label, not the number.
const LABEL_FILLER = new Set(["REG", "REGISTRATION", "REGN", "NO", "N0", "NUMBER", "NUM", "NR", "CODE"]);
// Tokens after these are dates or other fields, never the number we want.
const OTHER_FIELD = new Set([
  "EXP", "EXPIRY", "EXPIRES", "MFD", "MFG", "MANUFACTURED", "PROD", "PRODUCED", "PRODUCTION",
  "BB", "BBE", "BEST", "BEFORE", "USE", "BY", "DATE", "NET", "WT", "WEIGHT", "PRICE",
]);  // prettier-ignore

const CONFUSABLE_DIGITS: Record<string, string> = {
  O: "0",
  Q: "0",
  D: "0",
  I: "1",
  L: "1",
  S: "5",
  B: "8",
  Z: "2",
  G: "6",
};

/** Upper-case, keep letters/digits/hyphens, join "A1 - 1234" into "A1-1234". */
export function normalizeOcrText(text: string): string[][] {
  return text
    .toUpperCase()
    .replace(/[‐-―−]/g, "-")
    .split(/\r?\n/)
    .map((line) =>
      line
        .replace(/[^A-Z0-9\- ]/g, " ")
        .replace(/\s*-\s*/g, "-")
        .replace(/^-+|-+$/g, "")
        .split(/\s+/)
        .map((token) => token.replace(/^-+|-+$/g, ""))
        .filter(Boolean),
    )
    .filter((tokens) => tokens.length > 0);
}

function digitCount(value: string): number {
  return (value.match(/[0-9]/g) ?? []).length;
}

/** Fix O/0, I/1, S/5 ... only in hyphen-separated parts that are mostly digits. A leading
 *  letter followed by a digit ("A1") is kept as a letter, since many numbers start that way. */
export function fixDigitConfusions(token: string): string {
  return token
    .split("-")
    .map((part) => {
      const digitsOrConfusable = [...part].filter((c) => /[0-9]/.test(c) || c in CONFUSABLE_DIGITS);
      if (part.length < 2 || digitCount(part) * 2 < part.length || digitsOrConfusable.length < part.length) {
        return part;
      }
      const keepFirst = /^[A-Z][0-9]/.test(part);
      // A letter after three or more real digits ("0921L", "0045B") is usually a genuine suffix.
      const keepLast = /[0-9]{3,}[A-Z]$/.test(part);
      return [...part]
        .map((c, i) =>
          (i === 0 && keepFirst) || (i === part.length - 1 && keepLast)
            ? c
            : (CONFUSABLE_DIGITS[c] ?? c),
        )
        .join("");
    })
    .join("-");
}

function isCandidateShape(token: string): boolean {
  return (
    /^[A-Z0-9]+(?:-[A-Z0-9]+)*$/.test(token) &&
    token.length >= 3 &&
    token.length <= 24 &&
    digitCount(token) >= 2 &&
    !REGISTRATION_START.has(token) &&
    !BATCH_START.has(token) &&
    !LABEL_FILLER.has(token) &&
    !OTHER_FIELD.has(token)
  );
}

function looksLikeDate(token: string): boolean {
  return /^\d{1,2}-\d{1,2}-\d{2,4}$/.test(token) || /^\d{1,2}-\d{4}$/.test(token) || /^\d{4}-\d{1,2}(-\d{1,2})?$/.test(token);
}

type Labelled = { token: string; label: "registration" | "batch" | "other" };

const GLUED_LABELS: RegExp[] = [
  /^(NAFDAC|MANCAP)(?:REGISTRATION|REG|REGN)?(?:NUMBER|NO|N0)?([A-Z0-9][A-Z0-9-]*)$/,
  /^(REG)(?:ISTRATION)?(?:NUMBER|NO|N0)([A-Z0-9][A-Z0-9-]*)$/,
  /^(BATCH|LOT)(?:NUMBER|NO|N0)?([A-Z0-9][A-Z0-9-]*)$/,
  /^(BN)([0-9][A-Z0-9-]*)$/,
  /^(EXP|MFD|MFG)([0-9][A-Z0-9-]*)$/,
];

/** Split a label stuck to its number ("NAFDACREGNOA1-1234" -> "NAFDAC", "A1-1234"). Only
 *  splits when the remainder contains a digit, so ordinary words are left alone. */
export function splitGluedLabel(token: string): string[] {
  for (const pattern of GLUED_LABELS) {
    const match = token.match(pattern);
    if (match && /[0-9]/.test(match[2])) return [match[1], match[2]];
  }
  return [token];
}

/** Walk each line; record which kind of label (if any) each token follows. */
function labelTokens(lines: string[][]): { labelled: Labelled[]; unlabelled: string[] } {
  const labelled: Labelled[] = [];
  const unlabelled: string[] = [];
  for (const line of lines) {
    const tokens = line.flatMap(splitGluedLabel);
    let i = 0;
    while (i < tokens.length) {
      const token = tokens[i];
      let label: Labelled["label"] | null = null;
      if (REGISTRATION_START.has(token) || /^NAFDAC(NO|N0|REG)/.test(token)) label = "registration";
      else if (token === "B" && tokens[i + 1] === "N") {
        label = "batch";
        i += 1; // "B/N" read as "B N"
      } else if (BATCH_START.has(token) || /^(BATCH|LOT)(NO|N0)$/.test(token)) label = "batch";
      else if (OTHER_FIELD.has(token)) label = "other";

      if (label === null) {
        unlabelled.push(token);
        i += 1;
        continue;
      }
      // Skip the rest of the label ("REG", "NO", ...).
      i += 1;
      while (i < tokens.length && (LABEL_FILLER.has(tokens[i]) || (label === "registration" && REGISTRATION_START.has(tokens[i])))) {
        i += 1;
      }
      if (i >= tokens.length) break;
      const first = tokens[i];
      const second = tokens[i + 1];
      // "A1 1234" (space instead of hyphen) after a label: offer the joined form first.
      if (second && /^[A-Z0-9]{1,3}$/.test(first) && /^[0-9OIL]{3,}$/.test(second)) {
        labelled.push({ token: `${first}-${second}`, label });
      }
      labelled.push({ token: first, label });
      i += 1;
    }
  }
  return { labelled, unlabelled };
}

function score(token: string): number {
  return (token.includes("-") ? 3 : 0) + Math.min(digitCount(token), 8) + (token.length >= 5 && token.length <= 16 ? 2 : 0);
}

/** Extract the registration or batch number from OCR text. */
export function extractNumber(text: string, kind: ScanKind): Extraction {
  const { labelled, unlabelled } = labelTokens(normalizeOcrText(text));
  const fromLabel = labelled
    .filter((item) => item.label === kind)
    .map((item) => fixDigitConfusions(item.token))
    .filter(isCandidateShape);
  const otherLabelled = new Set(labelled.filter((item) => item.label !== kind).map((item) => item.token));
  const ranked = unlabelled
    .filter((token) => !otherLabelled.has(token))
    .map(fixDigitConfusions)
    .filter(isCandidateShape)
    .filter((token) => !(kind === "batch" && looksLikeDate(token)))
    .sort((a, b) => score(b) - score(a));

  const candidates = [...new Set([...fromLabel, ...ranked])].slice(0, MAX_CANDIDATES);
  return { value: candidates[0] ?? null, candidates };
}
