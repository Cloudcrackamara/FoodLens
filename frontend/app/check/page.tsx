import type { Metadata } from "next";
import { Suspense } from "react";
import { LookupForm } from "@/components/lookup/LookupForm";
import { lookupQueryFromUrl } from "@/lib/lookup";

export const metadata: Metadata = { title: "Check a registration number · FoodLens (demo)" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

/** Reads ?reg=...&batch=... so a scanner or link can open the form already filled in. */
async function PrefilledLookupForm({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (typeof value === "string") query.set(key, value);
  }
  return <LookupForm initial={lookupQueryFromUrl(`?${query.toString()}`)} />;
}

export default function CheckPage({ searchParams }: { searchParams: SearchParams }) {
  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 px-4 py-8">
      <div>
        <h1 className="text-2xl font-bold">Check a registration number</h1>
        <p className="mt-2 text-zinc-700 dark:text-zinc-300">
          Enter the NAFDAC or SON number printed on the pack, and the batch number if you have it.
          FoodLens compares them with a simulated, fictional register (demo data), not NAFDAC&apos;s
          or SON&apos;s own system. No account is needed, and FoodLens does not store anything that
          identifies you.
        </p>
      </div>
      <Suspense fallback={<LookupForm />}>
        <PrefilledLookupForm searchParams={searchParams} />
      </Suspense>
    </main>
  );
}
