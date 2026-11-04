import type { Metadata } from "next";
import { LoginForm } from "@/components/auth/LoginForm";

export const metadata: Metadata = { title: "Sign in · FoodLens (demo)" };

export default function LoginPage() {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-6 px-4 py-12">
      <h1 className="font-heading text-[22px] font-semibold text-ink">Sign in</h1>
      <p className="text-text">
        For company representatives, wholesalers, and FoodLens admins. You do not need an account
        to check a product.
      </p>
      <LoginForm />
    </main>
  );
}
