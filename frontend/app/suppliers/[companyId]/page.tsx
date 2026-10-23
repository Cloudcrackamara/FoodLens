import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { SupplierPage } from "@/components/suppliers/SupplierPage";

export const metadata: Metadata = { title: "Supplier · FoodLens (demo)" };

type Params = Promise<{ companyId: string }>;

async function Supplier({ params }: { params: Params }) {
  const { companyId } = await params;
  return <SupplierPage companyId={companyId} />;
}

export default function SupplierRoute({ params }: { params: Params }) {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-4 py-8">
      <Link href="/suppliers" className="text-sm underline">
        Back to the partner directory
      </Link>
      <Suspense fallback={<p>Loading…</p>}>
        <Supplier params={params} />
      </Suspense>
    </main>
  );
}
