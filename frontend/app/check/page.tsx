import type { Metadata } from "next";
import { LookupForm } from "@/components/lookup/LookupForm";

export const metadata: Metadata = { title: "Check a product · FoodLens (demo)" };

export default function CheckPage() {
  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 px-4 py-8">
      <div>
        <h1 className="text-2xl font-bold">Check a product</h1>
        <p className="mt-2 text-zinc-700 dark:text-zinc-300">
          Enter the product code and batch number from the package. FoodLens looks for a matching
          record in its fictional demonstration data. No account is needed, and FoodLens does not
          store anything that identifies you.
        </p>
      </div>
      <LookupForm />
    </main>
  );
}
