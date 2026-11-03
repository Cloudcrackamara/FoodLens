import type { Metadata } from "next";
import { Suspense } from "react";
import { CompanyBatchScreen } from "@/components/company/CompanyScreens";

export const metadata: Metadata = { title: "Batch codes · FoodLens (demo)" };

type Params = Promise<{ batchId: string }>;

async function Batch({ params }: { params: Params }) {
  const { batchId } = await params;
  return <CompanyBatchScreen batchId={batchId} />;
}

export default function BatchRoute({ params }: { params: Params }) {
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <Batch params={params} />
    </Suspense>
  );
}
