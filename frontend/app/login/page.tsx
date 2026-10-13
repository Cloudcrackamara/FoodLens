import type { Metadata } from "next";
import { LoginForm } from "@/components/auth/LoginForm";

export const metadata: Metadata = { title: "Sign in · FoodLens (demo)" };

export default function LoginPage() {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-5 px-4 py-10 sm:py-14">
      <h1 className="text-3xl font-bold leading-tight text-primary">Sign in</h1>
      <p className="text-muted-foreground">
        For company representatives, wholesalers, and FoodLens admins. You do not need an account
        to check a product.
      </p>
      <LoginForm />
    </main>
  );
}
