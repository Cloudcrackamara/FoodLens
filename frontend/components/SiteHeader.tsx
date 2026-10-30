"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { canOrder, useCurrentUser, useLogout } from "@/lib/auth";
import { canUseMerchant } from "@/lib/merchant";

export function SiteHeader() {
  const router = useRouter();
  const { data: user, isPending } = useCurrentUser();
  const logout = useLogout();

  return (
    <header className="border-b border-divider bg-white">
      <nav
        aria-label="Main"
        className="mx-auto flex w-full max-w-2xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3"
      >
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <Link href="/" className="font-bold">
            FoodLens
          </Link>
          <Link href="/check" className="text-sm font-semibold text-brand-dark underline">
            Check a pack
          </Link>
          <Link href="/suppliers" className="text-sm font-semibold text-brand-dark underline">
            Partners
          </Link>
        </div>
        {isPending ? null : user ? (
          <div className="flex flex-wrap items-center gap-3 text-sm">
            {user.is_admin ? (
              <Link href="/admin" className="font-semibold text-brand-dark underline">
                Admin
              </Link>
            ) : user.membership ? (
              <>
                <Link href="/company" className="font-semibold text-brand-dark underline">
                  My company
                </Link>
                {canUseMerchant(user) && (
                  <Link href="/merchant" className="font-semibold text-brand-dark underline">
                    Record events
                  </Link>
                )}
                {canOrder(user) && (
                  <Link href="/orders" className="font-semibold text-brand-dark underline">
                    My orders
                  </Link>
                )}
              </>
            ) : (
              <Link href="/company/register" className="font-semibold text-brand-dark underline">
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
              className="font-semibold text-brand-dark underline disabled:text-text-subtle"
            >
              Sign out
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-3 text-sm">
            <Link href="/login" className="font-semibold text-brand-dark underline">
              Sign in
            </Link>
            <Link href="/register" className="font-semibold text-brand-dark underline">
              Create account
            </Link>
          </div>
        )}
      </nav>
    </header>
  );
}
