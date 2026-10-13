import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SupplierPage, SupplierPageSkeleton } from "@/components/suppliers/SupplierPage";

export const metadata: Metadata = { title: "Supplier · FoodLens (demo)" };

type Params = Promise<{ companyId: string }>;

async function Supplier({ params }: { params: Params }) {
  const { companyId } = await params;
  return <SupplierPage companyId={companyId} />;
}

export default function SupplierRoute({ params }: { params: Params }) {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-8 sm:py-10">
      <Button asChild variant="ghost" size="sm" className="-ml-2 self-start">
        <Link href="/suppliers">
          <ArrowLeft aria-hidden="true" className="size-4" />
          Back to the supplier directory
        </Link>
      </Button>
      <Suspense fallback={<SupplierPageSkeleton />}>
        <Supplier params={params} />
      </Suspense>
    </main>
  );
}
