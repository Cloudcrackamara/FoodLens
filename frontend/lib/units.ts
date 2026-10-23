import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { apiDownload, apiFetch } from "./api";

// Mirrors backend/app/schemas/units.py. Counts only: the API never returns a code or hash.
export const MAX_UNITS = 2000;
export const MIN_QR_MM = 15;

export const unitStatusLabels: Record<string, string> = {
  ISSUED: "Not released",
  RELEASED: "Released",
  IN_TRANSIT: "In transit",
  IN_STOCK: "In stock",
  SOLD: "Sold",
  RECALLED: "Recalled",
  VOIDED: "Voided",
};

const counts = z.record(z.string(), z.number());

export const batchUnitsSchema = z.object({
  product_name: z.string(),
  batch_number: z.string(),
  expiry_date: z.string().nullable(),
  released_at: z.string().nullable(),
  units: counts,
  loose_units: counts,
  cartons: z.array(z.object({ carton_ref: z.string(), status: z.string(), units: counts })),
});
export type BatchUnits = z.infer<typeof batchUnitsSchema>;

export const areaSchema = z.object({ area_id: z.string(), city: z.string(), state: z.string() });
export type Area = z.infer<typeof areaSchema>;

export const destinationSchema = z.object({
  company_id: z.string(),
  display_name: z.string(),
  is_distributor: z.boolean(),
  is_retailer: z.boolean(),
});

export const allocationSchema = z.object({
  allocation_id: z.string(),
  destination_area: areaSchema,
  destination_company: destinationSchema.nullable(),
  quantity: z.number(),
  planned_date: z.string().nullable(),
  carton_refs: z.array(z.string()),
  units_listed: z.number(),
  created_at: z.string(),
});
export type Allocation = z.infer<typeof allocationSchema>;

const changedSchema = z.object({ units: z.number() });

export const generateFormSchema = z
  .object({
    quantity: z.coerce.number().int("Whole packs only").min(1, "At least 1 pack").max(MAX_UNITS, `At most ${MAX_UNITS} packs at a time`),
    units_per_carton: z.string().trim(),
    qr_size_mm: z.coerce.number().min(10, "At least 10 mm").max(60, "At most 60 mm"),
  })
  .refine((f) => f.units_per_carton === "" || (Number.isInteger(Number(f.units_per_carton)) && Number(f.units_per_carton) >= 1 && Number(f.units_per_carton) <= f.quantity), {
    message: "Between 1 and the number of packs, or leave empty for loose packs",
    path: ["units_per_carton"],
  });
export type GenerateForm = z.input<typeof generateFormSchema>;

/** "7q2m-8kd3 xh4n" lines from a pasted CSV column or typed list -> trimmed codes. */
export function parseCodes(text: string): string[] {
  return text
    .split(/[\n,;]+/)
    .map((code) => code.trim())
    .filter(Boolean);
}

const base = (companyId: string, batchId: string) => `/api/companies/${companyId}/batches/${batchId}`;
const unitsKey = (batchId: string) => ["batch-units", batchId] as const;
const allocationsKey = (batchId: string) => ["allocations", batchId] as const;

export function useBatchUnits(companyId: string, batchId: string) {
  return useQuery({
    queryKey: unitsKey(batchId),
    queryFn: () => apiFetch(`${base(companyId, batchId)}/units`, batchUnitsSchema),
  });
}

/** Saves the one-time label zip in the browser. The codes are never kept by the page. */
function saveFile(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function useGenerateLabels(companyId: string, batchId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (form: z.output<typeof generateFormSchema>) => {
      const download = await apiDownload(`${base(companyId, batchId)}/units`, {
        quantity: form.quantity,
        units_per_carton: form.units_per_carton === "" ? null : Number(form.units_per_carton),
        qr_size_mm: form.qr_size_mm,
      });
      saveFile(download.blob, download.filename);
      return {
        filename: download.filename,
        warning: download.headers.get("X-FoodLens-Label-Warning"),
      };
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: unitsKey(batchId) }),
  });
}

function useUnitAction<T>(companyId: string, batchId: string, action: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: T) =>
      apiFetch(`${base(companyId, batchId)}/${action}`, changedSchema, { method: "POST", body }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: unitsKey(batchId) });
      queryClient.invalidateQueries({ queryKey: allocationsKey(batchId) });
    },
  });
}

export const useRelease = (companyId: string, batchId: string) =>
  useUnitAction<{ carton_ref: string | null }>(companyId, batchId, "release");

export type VoidBody = {
  reason: string;
  whole_batch: boolean;
  carton_refs: string[];
  codes: string[];
};
export const useVoid = (companyId: string, batchId: string) =>
  useUnitAction<VoidBody>(companyId, batchId, "void");

export function useAllocations(companyId: string, batchId: string) {
  return useQuery({
    queryKey: allocationsKey(batchId),
    queryFn: () => apiFetch(`${base(companyId, batchId)}/allocations`, z.array(allocationSchema)),
  });
}

export type AllocationBody = {
  destination_area_id: string;
  destination_company_id: string | null;
  quantity: number | null;
  planned_date: string | null;
  carton_refs: string[];
  unit_codes: string[];
};

export function useCreateAllocation(companyId: string, batchId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: AllocationBody) =>
      apiFetch(`${base(companyId, batchId)}/allocations`, allocationSchema, { method: "POST", body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: allocationsKey(batchId) }),
  });
}

export function useDeleteAllocation(companyId: string, batchId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (allocationId: string) =>
      apiFetch(`${base(companyId, batchId)}/allocations/${allocationId}`, null, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: allocationsKey(batchId) }),
  });
}

export function useAreas() {
  return useQuery({
    queryKey: ["areas"],
    queryFn: () => apiFetch("/api/areas", z.array(areaSchema)),
    staleTime: Infinity,
  });
}

export function useDestinations(companyId: string) {
  return useQuery({
    queryKey: ["allocation-destinations", companyId],
    queryFn: () => apiFetch(`/api/companies/${companyId}/allocation-destinations`, z.array(destinationSchema)),
  });
}
