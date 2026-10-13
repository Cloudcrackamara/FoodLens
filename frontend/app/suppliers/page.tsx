import type { Metadata } from "next";
import { Store } from "lucide-react";
import { SupplierDirectory } from "@/components/suppliers/SupplierDirectory";

export const metadata: Metadata = { title: "Supplier directory · FoodLens (demo)" };

export default function SuppliersPage() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-4 py-8 sm:py-10">
      <div className="flex items-start gap-4">
        <span
          aria-hidden="true"
          className="flex size-12 shrink-0 items-center justify-center rounded-full bg-secondary text-primary sm:size-14"
        >
          <Store className="size-6 sm:size-7" />
        </span>
        <div>
          <h1 className="text-3xl font-bold leading-tight text-primary">Supplier directory</h1>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Fictional companies whose profiles and locations a FoodLens admin has reviewed for this
            demonstration. A FoodLens demo review is not a NAFDAC or SON approval.
          </p>
        </div>
      </div>
      <SupplierDirectory />
    </main>
  );
}
