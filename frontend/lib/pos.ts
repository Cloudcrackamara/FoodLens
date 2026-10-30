import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch } from "./api";

// Mirrors backend/app/schemas/pos.py. The demo till sends only a till and a code; the server
// builds, signs and records the request (D123, D151), so no key or secret reaches the browser.

const statusSchema = z.enum(["ISSUED", "RELEASED", "IN_TRANSIT", "IN_STOCK", "SOLD", "RECALLED", "VOIDED"]);
const messageSchema = z.object({ code: z.string(), message: z.string() });

export const posLookupSchema = z.object({
  subject: z.enum(["UNIT", "CARTON"]),
  code_last4: z.string(),
  product_name: z.string(),
  brand: z.string(),
  size: z.string().nullable(),
  gtin: z.string().nullable(),
  batch_number: z.string(),
  expiry_date: z.string().nullable(),
  status: statusSchema,
  warning: messageSchema.nullable(),
});
export type PosLookup = z.infer<typeof posLookupSchema>;

export const posEventSchema = z.object({
  transaction_id: z.string(),
  event_type: z.enum(["SOLD", "RETURNED", "SALE_CORRECTED"]),
  recorded: z.number(),
  errors: z.number(),
  units: z.array(
    z.object({
      index: z.number(),
      code_last4: z.string(),
      result: z.enum(["RECORDED", "ERROR"]),
      error: messageSchema.nullable(),
    }),
  ),
});
export type PosEventResult = z.infer<typeof posEventSchema>;

export const demoTillSchema = z.object({
  till_ref: z.string(),
  retailer_name: z.string(),
  location_name: z.string(),
  area: z.string(),
});
export type DemoTill = z.infer<typeof demoTillSchema>;

export type TillAction = "sales" | "refunds" | "voids";
export type TillRequest = { till_ref: string; code: string; reason?: string };

export const REASON_MAX = 500;

export function useDemoTills(enabled: boolean) {
  return useQuery({
    queryKey: ["demo-pos", "tills"],
    queryFn: () => apiFetch("/api/demo/pos/tills", z.array(demoTillSchema)),
    enabled,
    retry: false,
  });
}

export function useTillLookup() {
  return useMutation({
    mutationFn: (request: TillRequest) =>
      apiFetch("/api/demo/pos/lookup", posLookupSchema, { method: "POST", body: request }),
  });
}

export function useTillAction() {
  return useMutation({
    mutationFn: ({ action, request }: { action: TillAction; request: TillRequest }) =>
      apiFetch(`/api/demo/pos/${action}`, posEventSchema, { method: "POST", body: request }),
  });
}

// --- Admin ------------------------------------------------------------------------------------

const keySchema = z.object({
  key_id: z.string(),
  key_prefix: z.string(),
  created_at: z.string(),
  revoked_at: z.string().nullable(),
});
export type PartnerKey = z.infer<typeof keySchema>;

export const partnerSchema = z.object({
  partner_id: z.string(),
  name: z.string(),
  status: z.enum(["ACTIVE", "SUSPENDED"]),
  created_at: z.string(),
  keys: z.array(keySchema),
  links: z.array(
    z.object({
      link_id: z.string(),
      retailer_id: z.string(),
      retailer_name: z.string(),
      status: z.enum(["ACTIVE", "REVOKED"]),
    }),
  ),
  tills: z.array(
    z.object({
      till_id: z.string(),
      retailer_id: z.string(),
      retailer_name: z.string(),
      till_ref: z.string(),
      location_name: z.string(),
      area: z.string(),
    }),
  ),
});
export type Partner = z.infer<typeof partnerSchema>;

const credentialsSchema = z.object({ api_key: z.string(), signing_secret: z.string().nullable().optional() });
export type Credentials = z.infer<typeof credentialsSchema>;

const partnerCreatedSchema = z.object({ partner: partnerSchema, credentials: credentialsSchema });
const keyCreatedSchema = z.object({ key: keySchema, credentials: credentialsSchema });

export const retailerOptionSchema = z.object({
  retailer_id: z.string(),
  display_name: z.string(),
  locations: z.array(z.object({ location_id: z.string(), name: z.string(), area: z.string() })),
});
export type RetailerOption = z.infer<typeof retailerOptionSchema>;

const partnersKey = ["admin", "pos", "partners"];
const base = "/api/admin/pos/partners";

export function usePartners() {
  return useQuery({ queryKey: partnersKey, queryFn: () => apiFetch(base, z.array(partnerSchema)) });
}

export function useRetailerOptions() {
  return useQuery({
    queryKey: ["admin", "pos", "retailers"],
    queryFn: () => apiFetch("/api/admin/pos/retailers", z.array(retailerOptionSchema)),
  });
}

function usePartnerMutation<V, R>(run: (variables: V) => Promise<R>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: () => client.invalidateQueries({ queryKey: partnersKey }),
  });
}

export function useCreatePartner() {
  return usePartnerMutation((name: string) =>
    apiFetch(base, partnerCreatedSchema, { method: "POST", body: { name } }),
  );
}

export function useSetPartnerStatus() {
  return usePartnerMutation(({ partnerId, status }: { partnerId: string; status: Partner["status"] }) =>
    apiFetch(`${base}/${partnerId}/status`, partnerSchema, { method: "POST", body: { status } }),
  );
}

export function useAddKey() {
  return usePartnerMutation((partnerId: string) =>
    apiFetch(`${base}/${partnerId}/keys`, keyCreatedSchema, { method: "POST" }),
  );
}

export function useRevokeKey() {
  return usePartnerMutation(({ partnerId, keyId }: { partnerId: string; keyId: string }) =>
    apiFetch(`${base}/${partnerId}/keys/${keyId}/revoke`, keySchema, { method: "POST" }),
  );
}

export function useLinkRetailer() {
  return usePartnerMutation(({ partnerId, retailerId }: { partnerId: string; retailerId: string }) =>
    apiFetch(`${base}/${partnerId}/retailers`, partnerSchema, {
      method: "POST",
      body: { retailer_id: retailerId },
    }),
  );
}

export function useRevokeLink() {
  return usePartnerMutation(({ partnerId, linkId }: { partnerId: string; linkId: string }) =>
    apiFetch(`${base}/${partnerId}/retailers/${linkId}/revoke`, partnerSchema, { method: "POST" }),
  );
}

export function useAddTill() {
  return usePartnerMutation(
    ({ partnerId, ...body }: { partnerId: string; retailer_id: string; till_ref: string; location_id: string }) =>
      apiFetch(`${base}/${partnerId}/tills`, partnerSchema, { method: "POST", body }),
  );
}

export function useRemoveTill() {
  return usePartnerMutation(({ partnerId, tillId }: { partnerId: string; tillId: string }) =>
    apiFetch(`${base}/${partnerId}/tills/${tillId}`, partnerSchema, { method: "DELETE" }),
  );
}
