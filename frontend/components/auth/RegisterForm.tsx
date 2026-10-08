"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { describeError } from "@/lib/api";
import { fieldErrors, MIN_PASSWORD_LENGTH, registerFormSchema, useRegister } from "@/lib/auth";
import { FormField } from "./FormField";

export function RegisterForm() {
  const router = useRouter();
  const registerUser = useRegister();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = registerFormSchema.safeParse({ displayName, email, password });
    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }
    setErrors({});
    registerUser.mutate(parsed.data, { onSuccess: () => router.push("/") });
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
      <FormField
        id="displayName"
        label="Your name"
        autoComplete="name"
        value={displayName}
        error={errors.displayName}
        onChange={setDisplayName}
      />
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
        autoComplete="new-password"
        value={password}
        error={errors.password}
        hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
        onChange={setPassword}
      />
      {registerUser.isError && (
        <p role="alert" className="text-red-700 dark:text-red-400">
          {describeError(registerUser.error)}
        </p>
      )}
      <button
        type="submit"
        disabled={registerUser.isPending}
        className="rounded-md bg-zinc-900 px-4 py-2 font-semibold text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900"
      >
        {registerUser.isPending ? "Creating account…" : "Create account"}
      </button>
      <p className="text-sm">
        Already have an account?{" "}
        <Link href="/login" className="underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}
