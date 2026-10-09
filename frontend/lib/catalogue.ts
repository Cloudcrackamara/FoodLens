import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch } from "./api";

// Mirrors backend/app/schemas/catalogue.py.
const reviewStatusValues = ["PENDING_REVIEW", "APPROVED", "REJECTED"] as const;

export const credentialReviewLabels: Record<(typeof reviewStatusValues)[number], string> = {
  PENDING_REVIEW: "Claimed, awaiting FoodLens review (hidden from lookups)",
  APPROVED: "Reviewed by FoodLens (shown in lookups)",
  REJECTED: "Rejected by FoodLens (hidden from lookups)",
};

export const agencySchema = z.object({ agency_id: z.string(), name: z.string(), scheme: z.string() });

const credentialSchema = z.object({
  credential_id: z.string(),
  agency: z.string(),
  scheme: z.string(),
  reference_number: z.string(),
  status: z.enum(["ACTIVE", "INACTIVE"]),
  valid_from: z.string().nullable(),
  valid_until: z.string().nullable(),
  data_mode: z.literal("DEMO"),
  review_status: z.enum(reviewStatusValues),
  reviewed_at: z.string().nullable(),
  review_note: z.string().nullable(),
});

export const productSchema = z.object({
  product_id: z.string(),
  product_code: z.string(),
  name: z.string(),
  brand: z.string(),
  category: z.string(),
  package_size: z.string().nullable(),
  manufacturer_name: z.string(),
  label_information: z.string().nullable(),
  status: z.string(),
  created_at: z.string(),
  batches: z.array(
    z.object({
      batch_id: z.string(),
      batch_number: z.string(),
      production_date: z.string().nullable(),
      expiry_date: z.string().nullable(),
      created_at: z.string(),
    }),
  ),
  credentials: z.array(credentialSchema),
});

export const adminCredentialSchema = credentialSchema.extend({
  company_id: z.string(),
  company_display_name: z.string(),
  product_code: z.string(),
  product_name: z.string(),
  submitted_by_display_name: z.string().nullable(),
  created_at: z.string(),
});

export type Product = z.infer<typeof productSchema>;
export type Agency = z.infer<typeof agencySchema>;
export type AdminCredential = z.infer<typeof adminCredentialSchema>;

const optionalDate = z.string().trim();

export const productFormSchema = z.object({
  product_code: z.string().trim().min(1, "Enter the product code").max(64),
  name: z.string().trim().min(1, "Enter the product name").max(120),
  brand: z.string().trim().min(1, "Enter the brand").max(120),
  category: z.string().trim().min(1, "Enter a category").max(80),
  package_size: z.string().trim().max(40),
  manufacturer_name: z.string().trim().min(1, "Enter the manufacturer").max(200),
});
export const batchFormSchema = z.object({
  batch_number: z.string().trim().min(1, "Enter the batch number").max(64),
  production_date: optionalDate,
  expiry_date: optionalDate,
});
export const credentialFormSchema = z.object({
  agency_id: z.string().min(1, "Choose an agency"),
  reference_number: z.string().trim().min(1, "Enter the reference number").max(64),
  valid_from: optionalDate,
  valid_until: optionalDate,
});
export type ProductForm = z.infer<typeof productFormSchema>;
export type BatchForm = z.infer<typeof batchFormSchema>;
export type CredentialForm = z.infer<typeof credentialFormSchema>;

const orNull = (value: string) => value || null;
const productsKey = (companyId: string) => ["products", companyId] as const;
const adminCredentialsKey = ["admin", "credentials"] as const;

export function useProducts(companyId: string) {
  return useQuery({
    queryKey: productsKey(companyId),
    queryFn: () => apiFetch(`/api/companies/${companyId}/products`, z.array(productSchema)),
  });
}

export function useAgencies() {
  return useQuery({
    queryKey: ["agencies"],
    queryFn: () => apiFetch("/api/agencies", z.array(agencySchema)),
  });
}

function useCatalogueMutation<T>(companyId: string, request: (form: T) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: request,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: productsKey(companyId) }),
  });
}

export function useAddProduct(companyId: string) {
  return useCatalogueMutation(companyId, (form: ProductForm) =>
    apiFetch(`/api/companies/${companyId}/products`, null, {
      method: "POST",
      body: { ...form, package_size: orNull(form.package_size) },
    }),
  );
}

export function useAddBatch(companyId: string, productId: string) {
  return useCatalogueMutation(companyId, (form: BatchForm) =>
    apiFetch(`/api/companies/${companyId}/products/${productId}/batches`, null, {
      method: "POST",
      body: {
        batch_number: form.batch_number,
        production_date: orNull(form.production_date),
        expiry_date: orNull(form.expiry_date),
      },
    }),
  );
}

export function useAddCredential(companyId: string, productId: string) {
  return useCatalogueMutation(companyId, (form: CredentialForm) =>
    apiFetch(`/api/companies/${companyId}/products/${productId}/credentials`, null, {
      method: "POST",
      body: {
        agency_id: form.agency_id,
        reference_number: form.reference_number,
        valid_from: orNull(form.valid_from),
        valid_until: orNull(form.valid_until),
      },
    }),
  );
}

export function useAdminCredentials() {
  return useQuery({
    queryKey: adminCredentialsKey,
    queryFn: () =>
      apiFetch(
        "/api/admin/credentials?review_status=PENDING_REVIEW",
        z.array(adminCredentialSchema),
      ),
  });
}

export function useCredentialDecision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (args: { credentialId: string; decision: "APPROVE" | "REJECT"; note: string }) =>
      apiFetch(`/api/admin/credentials/${args.credentialId}/decision`, adminCredentialSchema, {
        method: "POST",
        body: { decision: args.decision, note: args.note || null },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminCredentialsKey }),
  });
}
