import type { Metadata } from "next";
import { RegisterForm } from "@/components/auth/RegisterForm";

export const metadata: Metadata = { title: "Create account · FoodLens (demo)" };

export default function RegisterPage() {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-6 px-4 py-12">
      <h1 className="font-heading text-[22px] font-semibold text-ink">Create an account</h1>
      <p className="text-text">
        Accounts are for company representatives and wholesalers using this capstone demo. You do
        not need an account to check a product. Do not use a password you use anywhere else.
      </p>
      <RegisterForm />
    </main>
  );
}
