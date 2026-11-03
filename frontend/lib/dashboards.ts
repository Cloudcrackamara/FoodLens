import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch } from "./api";
import { concernTypes } from "./check";
import type { Tone } from "@/components/ui/StatusPill";

// Mirrors backend/app/schemas/dashboard.py. No response holds a unit or carton id, a token, or
// anything about a consumer. Reports and alerts are the only rows with an id, to act on them.

const statusSchema = z.enum(["ISSUED", "RELEASED", "IN_TRANSIT", "IN_STOCK", "SOLD", "VOIDED"]);

export const inventoryRowSchema = z.object({
  company_name: z.string().nullable(),
  area: z.string().nullable(),
  not_allocated: z.boolean(),
  allocated: z.number(),
  received: z.number(),
  in_stock: z.number(),
  sold: z.number(),
  returned: z.number(),
});
export type InventoryRow = z.infer<typeof inventoryRowSchema>;

export const timelineSchema = z.object({
  subject: z.enum(["PACK", "CARTON"]),
  code_last4: z.string().nullable(),
  product_name: z.string(),
  size: z.string().nullable(),
  batch_number: z.string(),
  expiry_date: z.string().nullable(),
  status: statusSchema,
  entries: z.array(
    z.object({ at: z.string(), event_type: z.string(), text: z.string(), note: z.string().nullable() }),
  ),
  open_alerts: z.array(
    z.object({ alert_id: z.string(), rule_name: z.string(), level: z.enum(["LOW", "MEDIUM", "HIGH"]) }),
  ),
});
export type Timeline = z.infer<typeof timelineSchema>;

export const partnerSchema = z.object({
  display_name: z.string(),
  is_manufacturer: z.boolean(),
  is_distributor: z.boolean(),
  is_retailer: z.boolean(),
  places: z.array(z.string()),
  received: z.number(),
  sold: z.number(),
  pos_partners: z.array(z.string()),
});
export type Partner = z.infer<typeof partnerSchema>;

export const reportStatuses = ["NEW", "REVIEWED", "CLOSED"] as const;
export type ReportStatus = (typeof reportStatuses)[number];
// Approved wording (3 Nov 2026).
export const reportStatusLabels: Record<ReportStatus, string> = {
  NEW: "New",
  REVIEWED: "Reviewed",
  CLOSED: "Closed",
};
export const reportStatusTones: Record<ReportStatus, Tone> = { NEW: "new", REVIEWED: "info", CLOSED: "neutral" };
/** The buttons for each status. The server checks the same transitions. */
export const reportActions: Record<ReportStatus, { to: ReportStatus; label: string }[]> = {
  NEW: [
    { to: "REVIEWED", label: "Mark reviewed" },
    { to: "CLOSED", label: "Close" },
  ],
  REVIEWED: [{ to: "CLOSED", label: "Close" }],
  CLOSED: [],
};
export function concernLabel(value: string): string {
  return concernTypes.find((type) => type.value === value)?.label ?? value;
}

export const reportSchema = z.object({
  report_id: z.string(),
  concern_type: z.string(),
  description: z.string(),
  status: z.enum(reportStatuses),
  manufacturer_name: z.string().nullable(),
  product_name: z.string().nullable(),
  batch_number: z.string().nullable(),
  area: z.string().nullable(),
  created_at: z.string(),
});
export type Report = z.infer<typeof reportSchema>;

export const statsSchema = z.object({
  issued: z.number(),
  released: z.number(),
  sale_coverage_pct: z.number().nullable(),
  pos_sales: z.number(),
  merchant_sales: z.number(),
  pos_share_pct: z.number().nullable(),
  merchant_share_pct: z.number().nullable(),
  checks_by_city_week: z.array(z.object({ week_start: z.string(), city: z.string(), checks: z.number() })),
  hot_spots: z.array(z.object({ city: z.string(), open_alerts: z.number(), checks: z.number() })),
  alerts: z.array(
    z.object({
      rule: z.string(),
      rule_name: z.string(),
      level: z.enum(["LOW", "MEDIUM", "HIGH"]),
      raised: z.number(),
      resolved: z.number(),
    }),
  ),
  alerts_raised: z.number(),
  alerts_resolved: z.number(),
  median_hours_to_resolve: z.number().nullable(),
});
export type Stats = z.infer<typeof statsSchema>;

export const platformStatsSchema = z.object({
  companies: z.number(),
  approved_companies: z.number(),
  packs_issued: z.number(),
  checks_last_30_days: z.number(),
  pos_partners: z.number(),
  open_alerts: z.number(),
  new_reports: z.number(),
  pos_rate_limit_hits_last_30_days: z.number(),
});
export type PlatformStats = z.infer<typeof platformStatsSchema>;

export const scanningRowSchema = z.object({
  day: z.string(),
  area: z.string(),
  rate_limit_hits: z.number(),
  invalid_codes: z.number(),
  burst_alerts: z.number(),
});
export type ScanningRow = z.infer<typeof scanningRowSchema>;

const company = (companyId: string) => `/api/companies/${companyId}`;

export function useInventory(companyId: string, batchId: string) {
  return useQuery({
    queryKey: ["inventory", companyId, batchId],
    queryFn: () => apiFetch(`${company(companyId)}/batches/${batchId}/inventory`, z.array(inventoryRowSchema)),
  });
}

/** A mutation, not a query: the code travels in the body, never in a URL or cache key. */
export function useTimelineLookup(companyId: string) {
  return useMutation({
    mutationFn: (code: string) =>
      apiFetch(`${company(companyId)}/units/timeline`, timelineSchema, { method: "POST", body: { code } }),
  });
}

export function useAlertTimeline(base: string, alertId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["alerts", base, "timeline", alertId],
    queryFn: () => apiFetch(`${base}/${alertId}/timeline`, timelineSchema),
    enabled,
  });
}

export function usePartners(companyId: string) {
  return useQuery({
    queryKey: ["partners", companyId],
    queryFn: () => apiFetch(`${company(companyId)}/partners`, z.array(partnerSchema)),
  });
}

export function useStats(companyId: string, enabled = true) {
  return useQuery({
    queryKey: ["stats", companyId],
    queryFn: () => apiFetch(`${company(companyId)}/stats`, statsSchema),
    enabled,
  });
}

/** `base` is /api/companies/{id}/reports for a manufacturer, or /api/admin/reports. */
export function useReports(base: string, status: ReportStatus) {
  return useQuery({
    queryKey: ["reports", base, status],
    queryFn: () => apiFetch(`${base}?status=${status}`, z.array(reportSchema)),
  });
}

export function useReportStatus(base: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ reportId, status }: { reportId: string; status: ReportStatus }) =>
      apiFetch(`${base}/${reportId}/status`, reportSchema, { method: "POST", body: { status } }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["reports", base] }),
  });
}

export function usePlatformStats() {
  return useQuery({
    queryKey: ["admin", "stats"],
    queryFn: () => apiFetch("/api/admin/stats", platformStatsSchema),
  });
}

export function useScanningPanel() {
  return useQuery({
    queryKey: ["admin", "scanning"],
    queryFn: () => apiFetch("/api/admin/scanning", z.array(scanningRowSchema)),
  });
}
