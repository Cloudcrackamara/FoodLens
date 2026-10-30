import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch } from "./api";
import type { User } from "./auth";

// Mirrors backend/app/schemas/merchant.py. The API never returns a unit or carton ID, and a
// request carries only a code, an event type, a receiving company or a reason (never a status).

export const merchantEvents = ["RECEIVED", "TRANSFERRED", "SOLD", "RETURNED", "SALE_CORRECTED"] as const;
export type MerchantEvent = (typeof merchantEvents)[number];

export const eventLabels: Record<MerchantEvent, { title: string; hint: string; done: string }> = {
  RECEIVED: { title: "Received", hint: "Stock arrived at your company", done: "received" },
  TRANSFERRED: { title: "Transferred", hint: "Sent to another approved company", done: "transferred" },
  SOLD: { title: "Sold", hint: "Sold to a customer", done: "recorded as sold" },
  RETURNED: { title: "Returned", hint: "A customer brought it back", done: "recorded as returned" },
  SALE_CORRECTED: { title: "Sale corrected", hint: "The sale was recorded by mistake", done: "corrected" },
};

export const REASON_MAX = 500;

const statusSchema = z.enum(["ISSUED", "RELEASED", "IN_TRANSIT", "IN_STOCK", "SOLD", "RECALLED", "VOIDED"]);

export const lookupSchema = z.object({
  subject: z.enum(["UNIT", "CARTON"]),
  code_last4: z.string(),
  product_name: z.string(),
  brand: z.string(),
  size: z.string().nullable(),
  batch_number: z.string(),
  expiry_date: z.string().nullable(),
  packs: z.number(),
  status_counts: z.array(z.object({ status: statusSchema, packs: z.number() })),
  recalled: z.boolean(),
  you_hold: z.number(),
  sold_by_you: z.number(),
  allowed_events: z.array(z.enum(merchantEvents)),
  blocked_reason: z.string().nullable(),
});
export type Lookup = z.infer<typeof lookupSchema>;

export const eventResultSchema = z.object({
  event_type: z.enum(merchantEvents),
  subject: z.enum(["UNIT", "CARTON"]),
  packs: z.number(),
  status_after: statusSchema,
  notes: z.array(z.string()),
});
export type EventResult = z.infer<typeof eventResultSchema>;

export const destinationSchema = z.object({ company_id: z.string(), display_name: z.string() });

export const memberSchema = z.object({
  member_id: z.string(),
  email: z.string(),
  display_name: z.string(),
  role: z.enum(["OWNER", "STAFF"]),
  membership_status: z.enum(["ACTIVE", "INACTIVE"]),
});
export type TeamMember = z.infer<typeof memberSchema>;

export type EventRequest = {
  code: string;
  event_type: MerchantEvent;
  to_company_id?: string;
  reason?: string;
};

/** Approved distributors and retailers use the merchant page. The server enforces this too. */
export function canUseMerchant(user: User | null | undefined): boolean {
  const membership = user?.membership;
  return (
    membership?.company_review_status === "APPROVED" &&
    (membership.is_distributor || membership.is_retailer)
  );
}

const base = (companyId: string) => `/api/companies/${companyId}`;

export function useLookup(companyId: string) {
  return useMutation({
    mutationFn: (code: string) =>
      apiFetch(`${base(companyId)}/merchant/lookup`, lookupSchema, { method: "POST", body: { code } }),
  });
}

export function useRecordEvent(companyId: string) {
  return useMutation({
    mutationFn: (request: EventRequest) =>
      apiFetch(`${base(companyId)}/merchant/events`, eventResultSchema, { method: "POST", body: request }),
  });
}

export function useDestinations(companyId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["merchant", companyId, "destinations"],
    queryFn: () => apiFetch(`${base(companyId)}/merchant/destinations`, z.array(destinationSchema)),
    enabled,
  });
}

export function useMembers(companyId: string) {
  return useQuery({
    queryKey: ["merchant", companyId, "members"],
    queryFn: () => apiFetch(`${base(companyId)}/members`, z.array(memberSchema)),
  });
}

export function useAddStaff(companyId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (email: string) =>
      apiFetch(`${base(companyId)}/members`, memberSchema, { method: "POST", body: { email } }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["merchant", companyId, "members"] }),
  });
}

export function useDeactivateStaff(companyId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (memberId: string) =>
      apiFetch(`${base(companyId)}/members/${memberId}/deactivate`, memberSchema, { method: "POST" }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["merchant", companyId, "members"] }),
  });
}
