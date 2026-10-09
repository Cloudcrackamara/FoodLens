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
        className="mx-auto flex w-full max-w-2xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3"
      >
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <Link href="/" className="font-bold">
            FoodLens
          </Link>
          <Link href="/check" className="text-sm underline">
            Check a number
          </Link>
          <Link href="/suppliers" className="text-sm underline">
            Suppliers
          </Link>
        </div>
        {isPending ? null : user ? (
          <div className="flex flex-wrap items-center gap-3 text-sm">
            {user.is_admin ? (
              <Link href="/admin" className="underline">
                Admin
              </Link>
            ) : user.membership ? (
              <Link href="/company" className="underline">
                My company
              </Link>
            ) : (
              <Link href="/company/register" className="underline">
                Register company
              </Link>
            )}
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
