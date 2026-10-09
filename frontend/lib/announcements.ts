import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch } from "./api";

// Mirrors backend/app/schemas/announcement.py.
export const announcementSchema = z.object({
  announcement_id: z.string(),
  product_id: z.string(),
  product_code: z.string(),
  product_name: z.string(),
  title: z.string(),
  message: z.string(),
  status: z.enum(["LIVE", "HIDDEN"]),
  created_at: z.string(),
  hidden_at: z.string().nullable(),
});

export const adminAnnouncementSchema = announcementSchema.extend({
  company_id: z.string(),
  company_display_name: z.string(),
  created_by_display_name: z.string().nullable(),
  hidden_by_display_name: z.string().nullable(),
});

export type Announcement = z.infer<typeof announcementSchema>;
export type AdminAnnouncement = z.infer<typeof adminAnnouncementSchema>;

const companyKey = (companyId: string) => ["announcements", companyId] as const;
const adminKey = ["admin", "announcements"] as const;

export function useCompanyAnnouncements(companyId: string) {
  return useQuery({
    queryKey: companyKey(companyId),
    queryFn: () =>
      apiFetch(`/api/companies/${companyId}/announcements`, z.array(announcementSchema)),
  });
}

export function usePostAnnouncement(companyId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (args: { productId: string; title: string; message: string }) =>
      apiFetch(
        `/api/companies/${companyId}/products/${args.productId}/announcements`,
        announcementSchema,
        { method: "POST", body: { title: args.title, message: args.message } },
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: companyKey(companyId) }),
  });
}

export function useWithdrawAnnouncement(companyId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (announcementId: string) =>
      apiFetch(
        `/api/companies/${companyId}/announcements/${announcementId}/withdraw`,
        announcementSchema,
        { method: "POST" },
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: companyKey(companyId) }),
  });
}

export function useLiveAnnouncements() {
  return useQuery({
    queryKey: adminKey,
    queryFn: () =>
      apiFetch("/api/admin/announcements?status=LIVE", z.array(adminAnnouncementSchema)),
  });
}

export function useHideAnnouncement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (args: { announcementId: string; reason: string }) =>
      apiFetch(`/api/admin/announcements/${args.announcementId}/hide`, announcementSchema, {
        method: "POST",
        body: { reason: args.reason || null },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKey }),
  });
}
