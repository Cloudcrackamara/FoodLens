import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch } from "./api";
import { currentUserKey } from "./auth";

// Mirrors backend/app/schemas/company.py.
export const companyTypes = {
  MANUFACTURER: "Manufacturer",
  WHOLESALER: "Wholesaler",
  BOTH: "Manufacturer and wholesaler",
} as const;
const companyTypeValues = ["MANUFACTURER", "WHOLESALER", "BOTH"] as const;
const companyStatusValues = ["PENDING_REVIEW", "APPROVED", "REJECTED", "SUSPENDED"] as const;
const reviewStatusValues = ["PENDING_REVIEW", "APPROVED", "REJECTED"] as const;

export type CompanyStatus = (typeof companyStatusValues)[number];
export type ReviewStatus = (typeof reviewStatusValues)[number];

export const companyStatusLabels: Record<CompanyStatus, string> = {
  PENDING_REVIEW: "Pending FoodLens review",
  APPROVED: "Approved (FoodLens demo review)",
  REJECTED: "Rejected",
  SUSPENDED: "Suspended",
};

export const locationStatusLabels: Record<ReviewStatus, string> = {
  PENDING_REVIEW: "Pending FoodLens review",
  APPROVED: "Demo-reviewed",
  REJECTED: "Rejected",
};

const review = {
  reviewed_at: z.string().nullable(),
  review_note: z.string().nullable(),
};

export const locationSchema = z.object({
  ...review,
  location_id: z.string(),
  name: z.string(),
  address: z.string(),
  area: z.string(),
  contact_member_id: z.string().nullable(),
  review_status: z.enum(reviewStatusValues),
  created_at: z.string(),
});

export const companySchema = z.object({
  ...review,
  company_id: z.string(),
  company_type: z.enum(companyTypeValues),
  display_name: z.string(),
  contact_email: z.string(),
  contact_phone: z.string().nullable(),
  claimed_legal_name: z.string(),
  claimed_business_identifier: z.string().nullable(),
  claimed_address: z.string().nullable(),
  review_status: z.enum(companyStatusValues),
  created_at: z.string(),
  locations: z.array(locationSchema),
});

export const adminCompanySchema = companySchema.extend({
  owner_display_name: z.string().nullable(),
  owner_email: z.string().nullable(),
  reviewed_by_display_name: z.string().nullable(),
});

export const adminLocationSchema = locationSchema.extend({
  company_id: z.string(),
  company_display_name: z.string(),
  company_review_status: z.enum(companyStatusValues),
});

export const supplierSchema = z.object({
  company_id: z.string(),
  display_name: z.string(),
  company_type: z.enum(companyTypeValues),
  contact_email: z.string(),
  contact_phone: z.string().nullable(),
  badge: z.literal("FoodLens demo-reviewed profile"),
  badge_note: z.string(),
  reviewed_at: z.string().nullable(),
  locations: z.array(
    z.object({
      name: z.string(),
      address: z.string(),
      area: z.string(),
      reviewed_at: z.string().nullable(),
    }),
  ),
  contacts: z.array(
    z.object({
      display_name: z.string(),
      title: z.string().nullable(),
      phone: z.string().nullable(),
      email: z.string().nullable(),
    }),
  ),
});

export type Company = z.infer<typeof companySchema>;
export type AdminCompany = z.infer<typeof adminCompanySchema>;
export type AdminLocation = z.infer<typeof adminLocationSchema>;
export type Supplier = z.infer<typeof supplierSchema>;

export const companyRegisterFormSchema = z.object({
  company_type: z.enum(companyTypeValues, "Choose a company type"),
  display_name: z.string().trim().min(1, "Enter the company name").max(120),
  contact_email: z.email("Enter a valid email address"),
  contact_phone: z.string().trim().max(40),
  claimed_legal_name: z.string().trim().min(1, "Enter the registered legal name").max(200),
  claimed_business_identifier: z.string().trim().max(60),
  claimed_address: z.string().trim().max(300),
});
export type CompanyRegisterForm = z.infer<typeof companyRegisterFormSchema>;

export const locationFormSchema = z.object({
  name: z.string().trim().min(1, "Enter a name for this location").max(120),
  address: z.string().trim().min(1, "Enter the address").max(300),
  area: z.string().trim().min(1, "Enter the area or city").max(120),
});
export type LocationForm = z.infer<typeof locationFormSchema>;

const companyKey = (id: string) => ["company", id] as const;
const adminCompaniesKey = ["admin", "companies"] as const;
const adminLocationsKey = ["admin", "locations"] as const;

export function useRegisterCompany() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (form: CompanyRegisterForm) =>
      apiFetch("/api/companies", companySchema, {
        method: "POST",
        body: {
          company_type: form.company_type,
          display_name: form.display_name,
          contact_email: form.contact_email,
          contact_phone: form.contact_phone || null,
          claimed_legal_name: form.claimed_legal_name,
          claimed_business_identifier: form.claimed_business_identifier || null,
          claimed_address: form.claimed_address || null,
        },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: currentUserKey }),
  });
}

export function useMyCompany(companyId: string | undefined) {
  return useQuery({
    queryKey: companyKey(companyId ?? ""),
    queryFn: () => apiFetch(`/api/companies/${companyId}`, companySchema),
    enabled: Boolean(companyId),
  });
}

export function useAddLocation(companyId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (form: LocationForm) =>
      apiFetch(`/api/companies/${companyId}/locations`, locationSchema, {
        method: "POST",
        body: form,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: companyKey(companyId) }),
  });
}

export function useAdminCompanies(status: CompanyStatus | "ALL") {
  const query = status === "ALL" ? "" : `?review_status=${status}`;
  return useQuery({
    queryKey: [...adminCompaniesKey, status],
    queryFn: () => apiFetch(`/api/admin/companies${query}`, z.array(adminCompanySchema)),
  });
}

export function useAdminLocations(status: ReviewStatus | "ALL") {
  const query = status === "ALL" ? "" : `?review_status=${status}`;
  return useQuery({
    queryKey: [...adminLocationsKey, status],
    queryFn: () => apiFetch(`/api/admin/locations${query}`, z.array(adminLocationSchema)),
  });
}

export type CompanyDecision = "APPROVE" | "REJECT" | "SUSPEND";
export type LocationDecision = "APPROVE" | "REJECT";

export function useCompanyDecision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (args: { companyId: string; decision: CompanyDecision; note: string }) =>
      apiFetch(`/api/admin/companies/${args.companyId}/decision`, adminCompanySchema, {
        method: "POST",
        body: { decision: args.decision, note: args.note || null },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminCompaniesKey });
      queryClient.invalidateQueries({ queryKey: adminLocationsKey });
    },
  });
}

export function useLocationDecision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (args: { locationId: string; decision: LocationDecision; note: string }) =>
      apiFetch(`/api/admin/locations/${args.locationId}/decision`, adminLocationSchema, {
        method: "POST",
        body: { decision: args.decision, note: args.note || null },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminLocationsKey }),
  });
}

export function useSuppliers(search: string) {
  const query = search.trim() ? `?q=${encodeURIComponent(search.trim())}` : "";
  return useQuery({
    queryKey: ["suppliers", search.trim()],
    queryFn: () => apiFetch(`/api/suppliers${query}`, z.array(supplierSchema)),
  });
}
