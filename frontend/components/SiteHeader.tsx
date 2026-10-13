"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { canOrder, useCurrentUser, useLogout } from "@/lib/auth";
import { cn } from "@/lib/utils";

const linkClass =
  "rounded-full px-3 py-2 text-sm font-medium text-foreground hover:bg-secondary aria-[current=page]:bg-secondary aria-[current=page]:text-secondary-foreground";

/**
 * Logo plus links. On phones the links sit behind a menu button; the closed menu is hidden
 * with CSS only (max-sm:hidden), so the links stay in the page for wider screens.
 */
export function SiteHeader() {
  const router = useRouter();
  const pathname = usePathname();
  const { data: user, isPending } = useCurrentUser();
  const logout = useLogout();
  const [open, setOpen] = useState(false);

  const current = (href: string) => (pathname === href ? ("page" as const) : undefined);
  const close = () => setOpen(false);

  return (
    <header className="relative border-b border-border bg-card/80">
      <nav aria-label="Main" className="mx-auto w-full max-w-5xl px-4">
        <div className="flex min-h-14 items-center justify-between gap-4">
          <Link href="/" onClick={close} className="font-heading text-xl font-bold text-primary">
            FoodLens
          </Link>
          <Button
            variant="ghost"
            size="icon"
            className="sm:hidden"
            aria-expanded={open}
            aria-controls="site-menu"
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X /> : <Menu />}
            <span className="sr-only">Menu</span>
          </Button>
          <div
            id="site-menu"
            className={cn(
              "flex flex-1 items-center justify-between gap-2 max-sm:absolute max-sm:inset-x-0 max-sm:top-full max-sm:z-40 max-sm:flex-col max-sm:items-stretch max-sm:border-b max-sm:border-border max-sm:bg-card max-sm:p-4 max-sm:shadow-sm",
              !open && "max-sm:hidden",
            )}
          >
            <div className="flex items-center gap-1 max-sm:flex-col max-sm:items-stretch">
              <Link href="/check" onClick={close} aria-current={current("/check")} className={linkClass}>
                Check a number
              </Link>
              <Link href="/suppliers" onClick={close} aria-current={current("/suppliers")} className={linkClass}>
                Suppliers
              </Link>
            </div>
            {isPending ? null : user ? (
              <div className="flex items-center gap-1 max-sm:flex-col max-sm:items-stretch max-sm:border-t max-sm:border-border max-sm:pt-2">
                {user.is_admin ? (
                  <Link href="/admin" onClick={close} aria-current={current("/admin")} className={linkClass}>
                    Admin
                  </Link>
                ) : user.membership ? (
                  <>
                    <Link href="/company" onClick={close} aria-current={current("/company")} className={linkClass}>
                      My company
                    </Link>
                    {canOrder(user) && (
                      <Link href="/orders" onClick={close} aria-current={current("/orders")} className={linkClass}>
                        My orders
                      </Link>
                    )}
                  </>
                ) : (
                  <Link href="/company/register" onClick={close} className={linkClass}>
                    Register company
                  </Link>
                )}
                <span className="px-3 py-2 text-sm text-muted-foreground">
                  Signed in as <span className="font-medium text-foreground">{user.display_name}</span>
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    logout.mutate(undefined, {
                      onSuccess: () => {
                        close();
                        router.push("/");
                      },
                    })
                  }
                  disabled={logout.isPending}
                >
                  Sign out
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2 max-sm:flex-col max-sm:items-stretch max-sm:border-t max-sm:border-border max-sm:pt-3">
                <Link href="/login" onClick={close} className={linkClass}>
                  Sign in
                </Link>
                <Button asChild size="sm">
                  <Link href="/register" onClick={close}>
                    Create account
                  </Link>
                </Button>
              </div>
            )}
          </div>
        </div>
      </nav>
    </header>
  );
}

/** Shown while the header waits for the current path (needed for prerendering, cacheComponents). */
export function SiteHeaderFallback() {
  return (
    <header className="relative border-b border-border bg-card/80">
      <div className="mx-auto flex min-h-14 w-full max-w-5xl items-center px-4">
        <Link href="/" className="font-heading text-xl font-bold text-primary">
          FoodLens
        </Link>
      </div>
    </header>
  );
}
