import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch, apiUpload } from "./api";

// Mirrors backend/app/schemas/change_notice.py.
const noticeStatusValues = [
  "PENDING_REVIEW",
  "CLARIFICATION_REQUESTED",
  "APPROVED",
  "REJECTED",
] as const;
export type NoticeStatus = (typeof noticeStatusValues)[number];

export const noticeStatusLabels: Record<NoticeStatus, string> = {
  PENDING_REVIEW: "Pending FoodLens review (published data unchanged)",
  CLARIFICATION_REQUESTED: "Clarification requested",
  APPROVED: "Approved and applied",
  REJECTED: "Rejected (nothing changed)",
};

export const changeTypes = {
  PACKAGING: "Packaging",
  LABEL: "Label",
  PRODUCT_DETAILS: "Product details",
  BATCH_DETAILS: "Batch details",
  OTHER: "Other",
} as const;
export type ChangeTypeValue = keyof typeof changeTypes;

/** Fields a notice may change, in display order. Codes cannot be changed (D68). */
export const productFields = {
  name: "Product name",
  brand: "Brand",
  category: "Category",
  package_size: "Package size",
  manufacturer_name: "Manufacturer",
  label_information: "Label information",
  registration_number: "Registration number on the pack",
} as const;
export const batchFields = { production_date: "Production date", expiry_date: "Expiry date" } as const;
export const fieldLabels: Record<string, string> = { ...productFields, ...batchFields };

export const ALLOWED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg"];
export const MAX_FILE_BYTES = 5 * 1024 * 1024;

/** Client-side pre-check only; the server checks type, content and size again. */
export function attachmentProblem(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!ALLOWED_EXTENSIONS.some((ext) => name.endsWith(ext))) {
    return `${file.name}: only PDF, PNG, or JPG files are accepted`;
  }
  if (file.size > MAX_FILE_BYTES) return `${file.name}: files can be at most 5 MB`;
  if (file.size === 0) return `${file.name}: the file is empty`;
  return null;
}

const attachmentSchema = z.object({
  attachment_id: z.string(),
  original_filename: z.string(),
  mime_type: z.enum(["application/pdf", "image/png", "image/jpeg"]),
  size_bytes: z.number(),
  created_at: z.string(),
});

export const noticeSchema = z.object({
  notice_id: z.string(),
  company_id: z.string(),
  target_type: z.enum(["product", "batch"]),
  product_id: z.string(),
  product_code: z.string(),
  product_name: z.string(),
  batch_id: z.string().nullable(),
  batch_number: z.string().nullable(),
  change_type: z.string(),
  reason: z.string(),
  effective_date: z.string().nullable(),
  review_status: z.enum(noticeStatusValues),
  reviewed_at: z.string().nullable(),
  review_note: z.string().nullable(),
  created_at: z.string(),
  fields: z.array(
    z.object({
      field_name: z.string(),
      current_value: z.string().nullable(),
      proposed_value: z.string().nullable(),
      applied_old_value: z.string().nullable(),
    }),
  ),
  attachments: z.array(attachmentSchema),
});

export const adminNoticeSchema = noticeSchema.extend({
  company_display_name: z.string(),
  submitted_by_display_name: z.string().nullable(),
  reviewed_by_display_name: z.string().nullable(),
});

export type Notice = z.infer<typeof noticeSchema>;
export type AdminNotice = z.infer<typeof adminNoticeSchema>;

export type NoticeSubmission = {
  target: { productId: string } | { batchId: string };
  changeType: ChangeTypeValue;
  reason: string;
  effectiveDate: string;
  changes: Record<string, string | null>;
  files: File[];
};

const companyNoticesKey = (companyId: string) => ["notices", companyId] as const;
const adminNoticesKey = ["admin", "notices"] as const;

export function useCompanyNotices(companyId: string) {
  return useQuery({
    queryKey: companyNoticesKey(companyId),
    queryFn: () => apiFetch(`/api/companies/${companyId}/change-notices`, z.array(noticeSchema)),
  });
}

export function useSubmitNotice(companyId: string) {
  const queryClient = useQueryClient();
  const base = `/api/companies/${companyId}/change-notices`;
  return useMutation({
    mutationFn: async (submission: NoticeSubmission) => {
      const notice = await apiFetch(base, noticeSchema, {
        method: "POST",
        body: {
          ...("productId" in submission.target
            ? { product_id: submission.target.productId }
            : { batch_id: submission.target.batchId }),
          change_type: submission.changeType,
          reason: submission.reason,
          effective_date: submission.effectiveDate || null,
          proposed_changes: submission.changes,
        },
      });
      for (const file of submission.files) {
        await apiUpload(`${base}/${notice.notice_id}/attachments`, attachmentSchema, file);
      }
      return notice;
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: companyNoticesKey(companyId) }),
  });
}

export function useRespondToClarification(companyId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (args: { noticeId: string; message: string }) =>
      apiFetch(`/api/companies/${companyId}/change-notices/${args.noticeId}/respond`, noticeSchema, {
        method: "POST",
        body: { message: args.message },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: companyNoticesKey(companyId) }),
  });
}

export function useAdminNotices() {
  return useQuery({
    queryKey: adminNoticesKey,
    queryFn: () => apiFetch("/api/admin/change-notices", z.array(adminNoticeSchema)),
  });
}

export type NoticeDecision = "APPROVE" | "REJECT" | "REQUEST_CLARIFICATION";

export function useNoticeDecision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (args: { noticeId: string; decision: NoticeDecision; note: string }) =>
      apiFetch(`/api/admin/change-notices/${args.noticeId}/decision`, adminNoticeSchema, {
        method: "POST",
        body: { decision: args.decision, note: args.note || null },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminNoticesKey }),
  });
}
