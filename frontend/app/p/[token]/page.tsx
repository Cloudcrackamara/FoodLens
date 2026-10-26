import type { Metadata } from "next";
import { Suspense } from "react";
import { LinkCheck } from "@/components/check/LinkCheck";

// Generic on purpose: a link preview learns nothing about the code and creates no scan (D117).
export const metadata: Metadata = {
  title: "Check a pack · FoodLens (demo)",
  robots: { index: false, follow: false },
};

type Params = Promise<{ token: string }>;

async function Token({ params }: { params: Params }) {
  const { token } = await params;
  return <LinkCheck token={token} />;
}

export default function PackLinkPage({ params }: { params: Params }) {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-6 px-4 py-6 sm:py-10">
      <Suspense fallback={<p className="py-8 text-center text-lg">Checking this code…</p>}>
        <Token params={params} />
      </Suspense>
    </main>
  );
}
