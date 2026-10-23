import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { MemberBatchCodes } from "@/components/company/BatchCodes";

export const metadata: Metadata = { title: "Batch codes · FoodLens (demo)" };

type Params = Promise<{ batchId: string }>;

async function Batch({ params }: { params: Params }) {
  const { batchId } = await params;
  return <MemberBatchCodes batchId={batchId} />;
}

export default function BatchRoute({ params }: { params: Params }) {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-4 py-8">
      <Link href="/company" className="text-sm underline">
        Back to my company
      </Link>
      <Suspense fallback={<p>Loading…</p>}>
        <Batch params={params} />
      </Suspense>
    </main>
  );
}
