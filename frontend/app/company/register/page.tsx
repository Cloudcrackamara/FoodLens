import type { Metadata } from "next";
import { CompanyRegisterForm } from "@/components/company/CompanyRegisterForm";

export const metadata: Metadata = { title: "Register your company · FoodLens (demo)" };

export default function CompanyRegisterPage() {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-6 px-4 py-8">
      <h1 className="font-heading text-[22px] font-semibold text-ink">Register your company</h1>
      <p className="text-text">
        Your company starts as pending. A FoodLens admin reviews it for the demo directory; you
        become its owner. Use fictional details only.
      </p>
      <CompanyRegisterForm />
    </main>
  );
}
