import type { Metadata } from "next";
import { LoginForm } from "@/components/auth/LoginForm";

export const metadata: Metadata = { title: "Sign in · FoodLens (demo)" };

export default function LoginPage() {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-6 px-4 py-12">
      <h1 className="text-2xl font-bold">Sign in</h1>
      <p className="text-zinc-700 dark:text-zinc-300">
        For company representatives, wholesalers, and FoodLens admins. You do not need an account
        to check a product.
      </p>
      <LoginForm />
    </main>
  );
}
