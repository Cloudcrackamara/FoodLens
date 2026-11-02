import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch } from "./api";
import type { Tone } from "@/components/ui/StatusPill";

// Mirrors backend/app/schemas/alerts.py. A request carries only the new status or a note; the
// server records who and when (D125, D152).

export const alertStatuses = ["OPEN", "INVESTIGATING", "RESOLVED_LEGITIMATE", "RESOLVED_SUSPECTED_COPY"] as const;
export type AlertStatus = (typeof alertStatuses)[number];
export type AlertLevel = "LOW" | "MEDIUM" | "HIGH";
export const alertFilters = ["OPEN", "INVESTIGATING", "RESOLVED", "ALL"] as const;
export type AlertFilter = (typeof alertFilters)[number];

// Approved wording (30 Oct 2026).
export const statusLabels: Record<AlertStatus, string> = {
  OPEN: "Open",
  INVESTIGATING: "Investigating",
  RESOLVED_LEGITIMATE: "Resolved: legitimate",
  RESOLVED_SUSPECTED_COPY: "Resolved: suspected copy",
};
export const filterLabels: Record<AlertFilter, string> = {
  OPEN: "Open",
  INVESTIGATING: "Investigating",
  RESOLVED: "Resolved",
  ALL: "All",
};
export const levelLabels: Record<AlertLevel, string> = { LOW: "Low", MEDIUM: "Medium", HIGH: "High" };
export const levelTones: Record<AlertLevel, Tone> = { LOW: "neutral", MEDIUM: "alert", HIGH: "bad" };
export const statusTones: Record<AlertStatus, Tone> = {
  OPEN: "new",
  INVESTIGATING: "info",
  RESOLVED_LEGITIMATE: "ok",
  RESOLVED_SUSPECTED_COPY: "bad",
};
/** The buttons shown for each status, in order. The server checks the same transitions. */
export const actions: Record<AlertStatus, { to: AlertStatus; label: string }[]> = {
  OPEN: [
    { to: "INVESTIGATING", label: "Mark investigating" },
    { to: "RESOLVED_LEGITIMATE", label: "Resolve as legitimate" },
    { to: "RESOLVED_SUSPECTED_COPY", label: "Resolve as suspected copy" },
  ],
  INVESTIGATING: [
    { to: "RESOLVED_LEGITIMATE", label: "Resolve as legitimate" },
    { to: "RESOLVED_SUSPECTED_COPY", label: "Resolve as suspected copy" },
  ],
  RESOLVED_LEGITIMATE: [{ to: "OPEN", label: "Reopen" }],
  RESOLVED_SUSPECTED_COPY: [{ to: "OPEN", label: "Reopen" }],
};
export const NOTE_MAX = 1000;

export const alertSchema = z.object({
  alert_id: z.string(),
  rule: z.string(),
  rule_name: z.string(),
  level: z.enum(["LOW", "MEDIUM", "HIGH"]),
  status: z.enum(alertStatuses),
  explanation: z.string(),
  occurrences: z.number(),
  manufacturer_name: z.string().nullable(),
  product_name: z.string().nullable(),
  batch_number: z.string().nullable(),
  carton_ref: z.string().nullable(),
  area: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  resolved_by_name: z.string().nullable(),
  resolved_at: z.string().nullable(),
});
export type Alert = z.infer<typeof alertSchema>;

export const alertDetailSchema = alertSchema.extend({
  snapshot: z.array(z.object({ at: z.string(), explanation: z.string() }).passthrough()),
  notes: z.array(z.object({ author_name: z.string(), body: z.string(), created_at: z.string() })),
});
export type AlertDetail = z.infer<typeof alertDetailSchema>;

/** `base` is /api/companies/{id}/alerts for a manufacturer, or /api/admin/alerts. */
export function useAlerts(base: string, filter: AlertFilter) {
  return useQuery({
    queryKey: ["alerts", base, filter],
    queryFn: () => apiFetch(`${base}?status=${filter}`, z.array(alertSchema)),
  });
}

export function useAlert(base: string, alertId: string | null) {
  return useQuery({
    queryKey: ["alerts", base, "detail", alertId],
    queryFn: () => apiFetch(`${base}/${alertId}`, alertDetailSchema),
    enabled: alertId !== null,
  });
}

function useAlertMutation<V>(base: string, run: (variables: V) => Promise<AlertDetail>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: (detail) => {
      client.setQueryData(["alerts", base, "detail", detail.alert_id], detail);
      client.invalidateQueries({ queryKey: ["alerts", base] });
    },
  });
}

export function useAlertStatus(base: string) {
  return useAlertMutation(base, ({ alertId, status }: { alertId: string; status: AlertStatus }) =>
    apiFetch(`${base}/${alertId}/status`, alertDetailSchema, { method: "POST", body: { status } }),
  );
}

export function useAlertNote(base: string) {
  return useAlertMutation(base, ({ alertId, body }: { alertId: string; body: string }) =>
    apiFetch(`${base}/${alertId}/notes`, alertDetailSchema, { method: "POST", body: { body } }),
  );
}
