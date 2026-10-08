"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCurrentUser, useLogout } from "@/lib/auth";

export function SiteHeader() {
  const router = useRouter();
  const { data: user, isPending } = useCurrentUser();
  const logout = useLogout();

  return (
    <header className="border-b border-zinc-200 dark:border-zinc-800">
      <nav
        aria-label="Main"
        className="mx-auto flex w-full max-w-2xl items-center justify-between gap-4 px-4 py-3"
      >
        <Link href="/" className="font-bold">
          FoodLens
        </Link>
        {isPending ? null : user ? (
          <div className="flex items-center gap-3 text-sm">
            <span>
              Signed in as <span className="font-medium">{user.display_name}</span>
            </span>
            <button
              type="button"
              onClick={() => logout.mutate(undefined, { onSuccess: () => router.push("/") })}
              disabled={logout.isPending}
              className="underline disabled:opacity-60"
            >
              Sign out
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-3 text-sm">
            <Link href="/login" className="underline">
              Sign in
            </Link>
            <Link href="/register" className="underline">
              Create account
            </Link>
          </div>
        )}
      </nav>
    </header>
  );
}
