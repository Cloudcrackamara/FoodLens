"use client";

import { useState, type FormEvent } from "react";
import type { z } from "zod";
import { FormField } from "@/components/auth/FormField";
import { describeError } from "@/lib/api";
import { fieldErrors } from "@/lib/auth";
import {
  batchFormSchema,
  productFormSchema,
  useAddBatch,
  useAddProduct,
  useProducts,
  type Product,
} from "@/lib/catalogue";
import { formatDate } from "@/lib/lookup";

const buttonClass =
  "self-start rounded-md bg-zinc-900 px-4 py-2 font-semibold text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900";

/** Small form helper: holds values, validates with zod, submits, clears on success. */
function useForm<S extends z.ZodObject>(
  schema: S,
  empty: z.infer<S>,
  submit: (data: z.infer<S>, done: () => void) => void,
) {
  const [values, setValues] = useState(empty);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (key: keyof z.infer<S>) => (value: string) => setValues({ ...values, [key]: value });
  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    submit(parsed.data, () => setValues(empty));
  }
  return { values, errors, set, onSubmit };
}

function ErrorText({ error }: { error: Error | null }) {
  return error ? (
    <p role="alert" className="text-red-700 dark:text-red-400">
      {describeError(error)}
    </p>
  ) : null;
}

function AddProductForm({ companyId }: { companyId: string }) {
  const addProduct = useAddProduct(companyId);
  const form = useForm(
    productFormSchema,
    { product_code: "", name: "", brand: "", category: "", package_size: "", manufacturer_name: "", registration_number: "" },
    (data, done) => addProduct.mutate(data, { onSuccess: done }),
  );
  return (
    <form onSubmit={form.onSubmit} noValidate className="flex flex-col gap-3">
      <h3 className="font-semibold">Add a product</h3>
      <p className="text-sm text-zinc-700 dark:text-zinc-300">
        Products and batches appear in consumer lookups straight away. Later changes to a published
        product go through a change notice.
      </p>
      <FormField id="product_code" label="Product code" value={form.values.product_code} error={form.errors.product_code} autoCapitalize="characters" spellCheck={false} onChange={form.set("product_code")} />
      <FormField id="product_name" label="Product name" value={form.values.name} error={form.errors.name} onChange={form.set("name")} />
      <FormField id="brand" label="Brand" value={form.values.brand} error={form.errors.brand} onChange={form.set("brand")} />
      <FormField id="category" label="Category" value={form.values.category} error={form.errors.category} onChange={form.set("category")} />
      <FormField id="package_size" label="Package size (optional)" value={form.values.package_size} error={form.errors.package_size} onChange={form.set("package_size")} />
      <FormField id="manufacturer_name" label="Manufacturer" value={form.values.manufacturer_name} error={form.errors.manufacturer_name} onChange={form.set("manufacturer_name")} />
      <FormField id="registration_number" label="NAFDAC or SON number printed on the pack (optional)" value={form.values.registration_number} error={form.errors.registration_number} hint="Consumers check this number against the simulated register. FoodLens does not record it as approved." autoCapitalize="characters" spellCheck={false} onChange={form.set("registration_number")} />
      <ErrorText error={addProduct.error} />
      <button type="submit" disabled={addProduct.isPending} className={buttonClass}>Publish product</button>
    </form>
  );
}

function AddBatchForm({ companyId, product }: { companyId: string; product: Product }) {
  const addBatch = useAddBatch(companyId, product.product_id);
  const form = useForm(
    batchFormSchema,
    { batch_number: "", production_date: "", expiry_date: "" },
    (data, done) => addBatch.mutate(data, { onSuccess: done }),
  );
  const id = (name: string) => `${name}-${product.product_id}`;
  return (
    <form onSubmit={form.onSubmit} noValidate aria-label={`Add batch to ${product.name}`} className="flex flex-col gap-2">
      <h4 className="font-medium">Add a batch</h4>
      <FormField id={id("batch_number")} label="Batch number" value={form.values.batch_number} error={form.errors.batch_number} autoCapitalize="characters" spellCheck={false} onChange={form.set("batch_number")} />
      <FormField id={id("production_date")} label="Production date (optional)" type="date" value={form.values.production_date} onChange={form.set("production_date")} />
      <FormField id={id("expiry_date")} label="Expiry date (optional)" type="date" value={form.values.expiry_date} onChange={form.set("expiry_date")} />
      <ErrorText error={addBatch.error} />
      <button type="submit" disabled={addBatch.isPending} className={buttonClass}>Publish batch</button>
    </form>
  );
}

function ProductCard({ companyId, product }: { companyId: string; product: Product }) {
  return (
    <li aria-label={product.name} className="flex flex-col gap-3 rounded-md border border-zinc-300 p-4 dark:border-zinc-700">
      <div>
        <h3 className="font-semibold">{product.name}</h3>
        <p className="text-sm">{product.product_code} · {product.brand} · {product.category}{product.package_size && ` · ${product.package_size}`}</p>
        <p className="text-sm">Number on the pack: {product.registration_number ?? "Not given"}</p>
      </div>
      <div>
        <h4 className="font-medium">Batches</h4>
        {product.batches.length === 0 ? <p className="text-sm">No batches yet.</p> : (
          <ul className="text-sm">
            {product.batches.map((batch) => (
              <li key={batch.batch_id}>{batch.batch_number} · expires {formatDate(batch.expiry_date)}</li>
            ))}
          </ul>
        )}
      </div>
      <AddBatchForm companyId={companyId} product={product} />
    </li>
  );
}

export function Catalogue({ companyId }: { companyId: string }) {
  const products = useProducts(companyId);
  return (
    <section aria-labelledby="catalogue-heading" className="flex flex-col gap-4">
      <h2 id="catalogue-heading" className="text-lg font-semibold">Products</h2>
      {products.isError && <ErrorText error={products.error} />}
      {products.data?.length === 0 && <p>No products yet.</p>}
      <ul className="flex flex-col gap-4">
        {products.data?.map((product) => <ProductCard key={product.product_id} companyId={companyId} product={product} />)}
      </ul>
      <AddProductForm companyId={companyId} />
    </section>
  );
}
