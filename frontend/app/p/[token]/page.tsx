import type { Metadata } from "next";
import { Suspense } from "react";
import { LinkCheck, LinkCheckShell } from "@/components/check/LinkCheck";

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
    <Suspense
      fallback={
        <LinkCheckShell>
          <p className="py-8 text-center text-lg text-text">Checking this code…</p>
        </LinkCheckShell>
      }
    >
      <Token params={params} />
    </Suspense>
  );
}
