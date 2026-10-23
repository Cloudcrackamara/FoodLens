import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch } from "./api";
import { currentUserKey } from "./auth";

// Mirrors backend/app/schemas/company.py.
export const companyTypeFlags = {
  is_manufacturer: "Manufacturer",
  is_distributor: "Distributor",
  is_retailer: "Retailer",
} as const;
export type CompanyTypeFlag = keyof typeof companyTypeFlags;

const typeFlags = {
  is_manufacturer: z.boolean(),
  is_distributor: z.boolean(),
  is_retailer: z.boolean(),
};

/** "Manufacturer · Retailer": what the company does (D105). */
export function companyTypeLabel(company: Record<CompanyTypeFlag, boolean>): string {
  return (Object.keys(companyTypeFlags) as CompanyTypeFlag[])
    .filter((flag) => company[flag])
    .map((flag) => companyTypeFlags[flag])
    .join(" · ");
}
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
  ...typeFlags,
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
  ...typeFlags,
  contact_email: z.string(),
  contact_phone: z.string().nullable(),
  badge: z.literal("FoodLens demo-reviewed profile"),
  badge_note: z.string(),
  reviewed_at: z.string().nullable(),
  locations: z.array(
    z.object({
      location_id: z.string(),
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

// Mirrors backend/app/schemas/order.py SupplierDetailRead (D100). The NAFDAC number is shown
// as printed, as information only (D107).

export const supplierDetailSchema = supplierSchema.extend({
  products: z.array(
    z.object({
      product_id: z.string(),
      name: z.string(),
      brand: z.string(),
      category: z.string(),
      size: z.string().nullable(),
      registration_number: z.string().nullable(),
    }),
  ),
  data_mode: z.literal("DEMO"),
  disclaimer: z.string(),
});
export type SupplierDetail = z.infer<typeof supplierDetailSchema>;

export const companyRegisterFormSchema = z
  .object({
  ...typeFlags,
  display_name: z.string().trim().min(1, "Enter the company name").max(120),
  contact_email: z.email("Enter a valid email address"),
  contact_phone: z.string().trim().max(40),
  claimed_legal_name: z.string().trim().min(1, "Enter the registered legal name").max(200),
  claimed_business_identifier: z.string().trim().max(60),
  claimed_address: z.string().trim().max(300),
})
  .refine((form) => form.is_manufacturer || form.is_distributor || form.is_retailer, {
    message: "Choose at least one: manufacturer, distributor or retailer",
    path: ["company_types"],
  });
export type CompanyRegisterForm = z.infer<typeof companyRegisterFormSchema>;

export const locationFormSchema = z.object({
  name: z.string().trim().min(1, "Enter a name for this location").max(120),
  address: z.string().trim().min(1, "Enter the address").max(300),
  area: z.string().trim().min(1, "Enter the area or city").max(120),
});
export type LocationForm = z.infer<typeof locationFormSchema>;

export const contactFormSchema = z.object({
  contact_email: z.email("Enter a valid email address"),
  contact_phone: z.string().trim().max(40),
});
export type ContactForm = z.infer<typeof contactFormSchema>;

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
          is_manufacturer: form.is_manufacturer,
          is_distributor: form.is_distributor,
          is_retailer: form.is_retailer,
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

/** Owner edits the public contact details directly; the API logs every change (D103). */
export function useUpdateContact(companyId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (form: ContactForm) =>
      apiFetch(`/api/companies/${companyId}/contact`, companySchema, {
        method: "PATCH",
        body: { contact_email: form.contact_email, contact_phone: form.contact_phone || null },
      }),
    onSuccess: (company) => queryClient.setQueryData(companyKey(companyId), company),
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

export function useSupplier(companyId: string) {
  return useQuery({
    queryKey: ["supplier", companyId],
    queryFn: () => apiFetch(`/api/suppliers/${companyId}`, supplierDetailSchema),
  });
}
