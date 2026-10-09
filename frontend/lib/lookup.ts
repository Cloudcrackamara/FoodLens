import { useMutation } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch } from "./api";

// Mirrors backend/app/schemas/lookup.py.
export const lookupResults = [
  "REGISTERED_ACTIVE",
  "REGISTRATION_NOT_FOUND",
  "REGISTRATION_EXPIRED_OR_INACTIVE",
  "REGISTRATION_MISMATCH",
  "INSUFFICIENT_OR_AMBIGUOUS",
] as const;

const registerStatusValues = [
  "ACTIVE_IN_DEMO_REGISTER",
  "EXPIRED_IN_DEMO_REGISTER",
  "INACTIVE_IN_DEMO_REGISTER",
] as const;

export const registerStatusLabels: Record<(typeof registerStatusValues)[number], string> = {
  ACTIVE_IN_DEMO_REGISTER: "Active in the simulated register",
  EXPIRED_IN_DEMO_REGISTER: "Expired in the simulated register",
  INACTIVE_IN_DEMO_REGISTER: "Inactive in the simulated register",
};

const isoDate = z.string().nullable();

export const lookupResponseSchema = z.object({
  result: z.enum(lookupResults),
  data_mode: z.literal("DEMO"),
  disclaimer: z.string(),
  title: z.string(),
  message: z.string(),
  warnings: z.array(z.object({ code: z.string(), message: z.string() })),
  input: z.object({
    registration_number: z.string().nullable(),
    batch_number: z.string().nullable(),
  }),
  register_record: z
    .object({
      agency: z.string(),
      scheme: z.string(),
      registration_number: z.string(),
      registered_product_name: z.string(),
      registered_company_name: z.string(),
      status: z.enum(registerStatusValues),
      expires_on: isoDate,
      data_mode: z.literal("DEMO"),
      provenance: z.string(),
      last_checked_on: z.string(),
    })
    .nullable(),
  mismatch: z
    .object({ reason: z.enum(["different_registration_number", "registered_names_differ"]) })
    .nullable(),
  product: z
    .object({
      name: z.string(),
      brand: z.string(),
      category: z.string(),
      package_size: z.string().nullable(),
      manufacturer_name: z.string(),
      company_display_name: z.string(),
      registration_number: z.string().nullable(),
    })
    .nullable(),
  batch: z
    .object({ batch_number: z.string(), production_date: isoDate, expiry_date: isoDate })
    .nullable(),
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

/** What the consumer (or, later, a scanner) supplies: the number on the pack and the batch. */
export type LookupQuery = { registrationNumber: string; batchNumber: string };

export function useRegistrationLookup() {
  return useMutation({
    mutationFn: ({ registrationNumber, batchNumber }: LookupQuery) =>
      apiFetch("/api/lookups/registration", lookupResponseSchema, {
        method: "POST",
        body: {
          registration_number: registrationNumber.trim(),
          batch_number: batchNumber.trim() || null,
        },
      }),
  });
}

/**
 * Initial values from the page URL, e.g. /check?reg=DEMO-NAFDAC-0001&batch=DEMO-LOT-101.
 * Lets a future scanner (or a printed link) open the check form already filled in.
 */
export function lookupQueryFromUrl(search: string): LookupQuery {
  const params = new URLSearchParams(search);
  return {
    registrationNumber: params.get("reg") ?? params.get("registration_number") ?? "",
    batchNumber: params.get("batch") ?? params.get("batch_number") ?? "",
  };
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
