import type { Metadata } from "next";
import { AdminReview } from "@/components/admin/AdminReview";

export const metadata: Metadata = { title: "Admin review · FoodLens (demo)" };

export default function AdminPage() {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-4 py-8 sm:py-10">
      <div>
        <h1 className="text-3xl font-bold leading-tight text-primary">Admin review</h1>
        <p className="mt-2 text-muted-foreground">
          Decisions are FoodLens demo reviews only, never NAFDAC or SON approvals. Each decision
          records you as the reviewer, with the time.
        </p>
      </div>
      <AdminReview />
    </main>
  );
}
