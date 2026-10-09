import { useMutation } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch } from "./api";

// Mirrors backend/app/schemas/lookup.py.
export const lookupResults = [
  "DEMO_RECORD_FOUND",
  "BATCH_NOT_FOUND",
  "BATCH_EXPIRED",
  "DETAILS_MISMATCH",
  "CREDENTIAL_EXPIRED_OR_INACTIVE",
  "INSUFFICIENT_OR_AMBIGUOUS",
] as const;

const credentialStatusValues = [
  "ACTIVE_IN_DEMO_DATA",
  "EXPIRED_IN_DEMO_DATA",
  "INACTIVE_IN_DEMO_DATA",
  "NOT_YET_VALID_IN_DEMO_DATA",
] as const;

export const credentialStatuses: Record<(typeof credentialStatusValues)[number], string> = {
  ACTIVE_IN_DEMO_DATA: "Active in demo data",
  EXPIRED_IN_DEMO_DATA: "Expired in demo data",
  INACTIVE_IN_DEMO_DATA: "Inactive in demo data",
  NOT_YET_VALID_IN_DEMO_DATA: "Not yet valid in demo data",
};

const isoDate = z.string().nullable();

export const lookupResponseSchema = z.object({
  result: z.enum(lookupResults),
  data_mode: z.literal("DEMO"),
  disclaimer: z.string(),
  title: z.string(),
  message: z.string(),
  warnings: z.array(z.object({ code: z.string(), message: z.string() })),
  input: z.object({ product_code: z.string().nullable(), batch_number: z.string().nullable() }),
  mismatch: z.object({ field: z.enum(["product_code", "credential"]) }).nullable(),
  product: z
    .object({
      product_code: z.string(),
      name: z.string(),
      brand: z.string(),
      category: z.string(),
      package_size: z.string().nullable(),
      manufacturer_name: z.string(),
      company_display_name: z.string(),
    })
    .nullable(),
  batch: z
    .object({ batch_number: z.string(), production_date: isoDate, expiry_date: isoDate })
    .nullable(),
  credentials: z.array(
    z.object({
      agency: z.string(),
      scheme: z.string(),
      reference_number: z.string(),
      scope: z.literal("PRODUCT"),
      status: z.enum(credentialStatusValues),
      valid_from: isoDate,
      valid_until: isoDate,
      data_mode: z.literal("DEMO"),
      provenance: z.string(),
      checked_on: z.string(),
    }),
  ),
  credential_scope_note: z.string(),
  candidates: z.array(z.object({ product_code: z.string(), name: z.string(), brand: z.string() })),
  announcements: z.array(
    z.object({
      title: z.string(),
      message: z.string(),
      posted_at: z.string(),
      label: z.literal("Message from the company — not reviewed by FoodLens"),
    }),
  ),
});

export type LookupResponse = z.infer<typeof lookupResponseSchema>;
export type LookupQuery = { productCode: string; batchNumber: string };

export function useBatchLookup() {
  return useMutation({
    mutationFn: ({ productCode, batchNumber }: LookupQuery) =>
      apiFetch("/api/lookups/batch", lookupResponseSchema, {
        method: "POST",
        body: { product_code: productCode.trim(), batch_number: batchNumber.trim() },
      }),
  });
}

/** "2027-12-31" -> "31 Dec 2027", without timezone shifts. */
export function formatDate(value: string | null): string {
  if (!value) return "Not recorded";
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}
