import type { Metadata } from "next";
import { SupplierDirectory } from "@/components/suppliers/SupplierDirectory";

export const metadata: Metadata = { title: "Supplier directory · FoodLens (demo)" };

export default function SuppliersPage() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-4 py-8">
      <div>
        <h1 className="text-2xl font-bold">Supplier directory</h1>
        <p className="mt-2 text-zinc-700 dark:text-zinc-300">
          Fictional companies whose profiles and locations a FoodLens admin has reviewed for this
          demonstration. A FoodLens demo review is not a NAFDAC or SON approval.
        </p>
      </div>
      <SupplierDirectory />
    </main>
  );
}
