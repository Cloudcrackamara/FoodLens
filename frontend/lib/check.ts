import { useMutation, useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { ApiError, apiFetch } from "./api";

/** Codes are 26 Crockford Base32 characters (D138). */
export const CODE_LENGTH = 26;
const CODE_PATTERN = /^[0-9A-HJKMNP-TV-Z]{26}$/;

/**
 * Same rules as the backend (D138): upper-case, spaces and hyphens removed, O read as 0,
 * I and L read as 1. "7q2m-8kd3 xh4n…" -> "7Q2M8KD3XH4N…".
 */
export function normaliseCode(input: string): string {
  return input
    .toUpperCase()
    .replace(/[\s-]/g, "")
    .replace(/O/g, "0")
    .replace(/[IL]/g, "1");
}

export function isWellFormedCode(code: string): boolean {
  return CODE_PATTERN.test(code);
}

/** Printed form: groups of 4, the last group has 2. */
export function groupCode(code: string): string {
  return code.replace(/(.{4})(?=.)/g, "$1 ");
}

/**
 * The code inside a scanned QR: a FoodLens link ".../p/{token}" (from any host, so a copied
 * label is still checked) or a bare code. Anything else returns null.
 */
export function codeFromQrText(text: string): string | null {
  const trimmed = text.trim();
  let candidate = trimmed;
  try {
    const url = new URL(trimmed);
    const match = /^\/p\/([^/?#]+)\/?$/.exec(url.pathname);
    if (!match) return null;
    candidate = decodeURIComponent(match[1]);
  } catch {
    // Not a URL: maybe the bare code.
  }
  const code = normaliseCode(candidate);
  return isWellFormedCode(code) ? code : null;
}

// Mirrors backend/app/schemas/check.py. No internal IDs, and only the last 4 code characters.
export const checkResultValues = [
  "INVALID_IDENTITY",
  "SUSPICIOUS_ACTIVITY",
  "BATCH_OR_PRODUCT_WARNING",
  "RECOGNISED_JUST_SOLD",
  "RECOGNISED_PREVIOUSLY_SOLD",
  "RECOGNISED_NOT_SOLD",
  "CARTON_CODE",
] as const;

export const checkResponseSchema = z.object({
  data_mode: z.literal("DEMO"),
  disclaimer: z.string().min(1),
  result: z.enum(checkResultValues),
  identifier_type: z.enum(["QR", "TYPED"]),
  subject: z.enum(["PACK", "CARTON"]).nullable(),
  code_last4: z.string().max(4),
  title: z.string(),
  message: z.string(),
  tip: z.string().nullable(),
  advice: z.string().nullable(),
  just_sold_window_hours: z.number(),
  product: z
    .object({
      name: z.string(),
      brand: z.string(),
      size: z.string().nullable(),
      manufacturer_name: z.string(),
      registration_number: z.string().nullable(),
    })
    .nullable(),
  batch: z
    .object({
      batch_number: z.string(),
      expiry_date: z.string().nullable(),
      expired: z.boolean(),
    })
    .nullable(),
  sale: z
    .object({ retailer_name: z.string().nullable(), area: z.string().nullable(), sold_at: z.string() })
    .nullable(),
  recorded_facts: z.array(z.string()),
  possible_patterns: z.array(z.string()),
  warnings: z.array(z.string()),
  notices: z.array(
    z.object({
      kind: z.enum(["NOTICE", "RECALL"]),
      title: z.string(),
      message: z.string(),
      posted_at: z.string(),
      label: z.string(),
    }),
  ),
  can_note_purchase: z.boolean(),
  copy_help: z.string(),
  can_report: z.boolean(),
});

export type CheckResponse = z.infer<typeof checkResponseSchema>;
export type CheckResult = CheckResponse["result"];
export type IdentifierType = CheckResponse["identifier_type"];

export type CheckRequest = {
  code: string;
  identifier_type: IdentifierType;
  simulated_city?: string | null;
};

/** Only the code (as text) is sent. Images from the camera or a photo never leave the phone. */
export function postCheck(request: CheckRequest): Promise<CheckResponse> {
  return apiFetch("/api/check/qr", checkResponseSchema, {
    method: "POST",
    body: { ...request, simulated_city: request.simulated_city || null },
  });
}

export function useCheck() {
  return useMutation({ mutationFn: postCheck });
}

/**
 * /p/{token}: verified by a client-side POST after the page mounts, so link previews and
 * prefetching never create a scan (D117). The query de-duplicates React's double mount.
 */
export function useLinkCheck(code: string, simulatedCity: string | null) {
  return useQuery({
    queryKey: ["check", "link", code, simulatedCity],
    queryFn: () => postCheck({ code, identifier_type: "QR", simulated_city: simulatedCity }),
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export const concernTypes = [
  { value: "PREVIOUSLY_SOLD", label: "It was already recorded as sold" },
  { value: "SUSPICIOUS_RESULT", label: "The result looks wrong or unusual" },
  { value: "PACKAGING", label: "Packaging or label looks different" },
  { value: "OTHER", label: "Something else" },
] as const;

export type ConcernType = (typeof concernTypes)[number]["value"];

const reportResponseSchema = z.object({
  data_mode: z.literal("DEMO"),
  disclaimer: z.string(),
  message: z.string(),
});

export function useReportConcern() {
  return useMutation({
    mutationFn: (report: {
      code: string | null;
      concern_type: ConcernType;
      description: string;
      simulated_city?: string | null;
    }) =>
      apiFetch("/api/check/report", reportResponseSchema, {
        method: "POST",
        body: { ...report, simulated_city: report.simulated_city || null },
      }),
  });
}

const demoCitySchema = z.object({ city: z.string(), state: z.string() });
export type DemoCity = z.infer<typeof demoCitySchema>;

/** Demo city picker; an empty list when SIMULATE_LOCATION_ENABLED is off (404). */
export function useDemoCities() {
  return useQuery({
    queryKey: ["check", "demo-cities"],
    queryFn: async () => {
      try {
        return await apiFetch("/api/check/demo-cities", z.array(demoCitySchema));
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return [];
        throw error;
      }
    },
    staleTime: Infinity,
    retry: false,
  });
}
