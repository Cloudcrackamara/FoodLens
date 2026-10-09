import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch } from "./api";

// Mirrors backend/app/schemas/catalogue.py.
export const productSchema = z.object({
  product_id: z.string(),
  product_code: z.string(),
  name: z.string(),
  brand: z.string(),
  category: z.string(),
  package_size: z.string().nullable(),
  manufacturer_name: z.string(),
  label_information: z.string().nullable(),
  registration_number: z.string().nullable(),
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
});

export type Product = z.infer<typeof productSchema>;

const optionalDate = z.string().trim();

export const productFormSchema = z.object({
  product_code: z.string().trim().min(1, "Enter the product code").max(64),
  name: z.string().trim().min(1, "Enter the product name").max(120),
  brand: z.string().trim().min(1, "Enter the brand").max(120),
  category: z.string().trim().min(1, "Enter a category").max(80),
  package_size: z.string().trim().max(40),
  manufacturer_name: z.string().trim().min(1, "Enter the manufacturer").max(200),
  registration_number: z.string().trim().max(200),
});
export const batchFormSchema = z.object({
  batch_number: z.string().trim().min(1, "Enter the batch number").max(64),
  production_date: optionalDate,
  expiry_date: optionalDate,
});
export type ProductForm = z.infer<typeof productFormSchema>;
export type BatchForm = z.infer<typeof batchFormSchema>;

const orNull = (value: string) => value || null;
const productsKey = (companyId: string) => ["products", companyId] as const;

export function useProducts(companyId: string) {
  return useQuery({
    queryKey: productsKey(companyId),
    queryFn: () => apiFetch(`/api/companies/${companyId}/products`, z.array(productSchema)),
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
      body: {
        ...form,
        package_size: orNull(form.package_size),
        registration_number: orNull(form.registration_number),
      },
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
