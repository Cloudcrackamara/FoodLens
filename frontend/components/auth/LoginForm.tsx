"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { describeError } from "@/lib/api";
import { fieldErrors, loginFormSchema, useLogin } from "@/lib/auth";
import { FormField } from "./FormField";
import { buttonVariants } from "@/components/ui/button";

export function LoginForm() {
  const router = useRouter();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = loginFormSchema.safeParse({ email, password });
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    login.mutate(parsed.data, { onSuccess: () => router.push("/") });
  }

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      className="flex flex-col gap-4 rounded-xl border border-border bg-card p-4 sm:p-6"
    >
      <FormField
        id="email"
        label="Email"
        type="email"
        autoComplete="email"
        value={email}
        error={errors.email}
        onChange={setEmail}
      />
      <FormField
        id="password"
        label="Password"
        type="password"
        autoComplete="current-password"
        value={password}
        error={errors.password}
        onChange={setPassword}
      />
      {login.isError && (
        <p role="alert" className="text-destructive">
          {describeError(login.error)}
        </p>
      )}
      <button
        type="submit"
        disabled={login.isPending}
        className={buttonVariants()}
      >
        {login.isPending ? "Signing in…" : "Sign in"}
      </button>
      <p className="text-sm">
        No account?{" "}
        <Link href="/register" className="font-medium text-primary underline underline-offset-4 hover:no-underline">
          Create one
        </Link>
      </p>
    </form>
  );
}
