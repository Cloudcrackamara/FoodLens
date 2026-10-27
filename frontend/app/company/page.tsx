import type { Metadata } from "next";
import { CompanyDashboard } from "@/components/company/CompanyDashboard";

export const metadata: Metadata = { title: "My company · FoodLens (demo)" };

export default function CompanyPage() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-4 py-8">
      <h1 className="font-heading text-[22px] font-semibold text-ink">My company</h1>
      <CompanyDashboard />
    </main>
  );
}
