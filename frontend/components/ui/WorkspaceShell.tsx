"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { DemoDataBanner } from "@/components/DemoDataBanner";

export type NavItem = { href: string; label: string };

type Props = {
  companyName: string;
  /** Chip in the header, such as "Retailer". */
  roleLabel: string;
  accountName: string;
  nav: NavItem[];
  currentHref: string;
  pageTitle: string;
  onLogout: () => void;
  children: ReactNode;
};

function initials(name: string): string {
  const letters = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? "");
  return letters.join("") || "?";
}

function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2.5 px-1.5 pt-0.5 pb-[18px] text-white no-underline">
      <svg width="30" height="30" viewBox="0 0 36 36" aria-hidden="true">
        <circle cx="15" cy="15" r="11" fill="none" stroke="#F6B93B" strokeWidth="3.5" />
        <path d="M23 23l9 9" stroke="#F6B93B" strokeWidth="4" strokeLinecap="round" />
        <path d="M10 15.5l3.5 3.5 6.5-7" fill="none" stroke="#3CC37A" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="font-heading text-xl">
        <b>FoodLens</b> <span className="font-medium text-sun">business</span>
      </span>
    </Link>
  );
}

/** The 256px indigo sidebar of the workspace shell (Supplier.dc.html). */
function Sidebar({
  companyName,
  nav,
  currentHref,
  onNavigate,
  onLogout,
}: Pick<Props, "companyName" | "nav" | "currentHref" | "onLogout"> & { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-1.5 bg-ink px-4 py-[22px] text-[#DCDAF0]">
      <Logo />
      <div className="mb-2 flex items-center gap-2.5 rounded-[12px] bg-white/[0.07] p-3">
        <span
          aria-hidden="true"
          className="inline-flex size-10 flex-none items-center justify-center rounded-[10px] bg-brand font-heading font-bold text-white"
        >
          {initials(companyName)}
        </span>
        <span className="min-w-0">
          <b className="block text-sm leading-[1.3] text-white">{companyName}</b>
          <span className="mt-[3px] inline-block rounded-full bg-[rgba(60,195,122,0.2)] px-2 text-[11px] font-bold text-[#A6E9C4]">
            Reviewed · demo
          </span>
        </span>
      </div>
      <p className="mx-2 mt-2 mb-1 text-[11px] font-bold tracking-[0.08em] text-[#9C9AC4]">STOCK</p>
      <nav aria-label="Business navigation" className="flex flex-col gap-[3px]">
        {nav.map((item) => {
          const current = item.href === currentHref;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={current ? "page" : undefined}
              onClick={onNavigate}
              className={`flex min-h-11 items-center rounded-[8px] px-3 no-underline ${
                current ? "bg-brand font-bold text-white" : "font-medium text-[#DCDAF0]"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      <button
        type="button"
        onClick={onLogout}
        className="mt-auto flex min-h-11 items-center rounded-[8px] border-0 bg-transparent px-3 text-left font-semibold text-[#DCDAF0]"
      >
        Log out
      </button>
    </div>
  );
}

/**
 * The business workspace shell (design/README.md, component 5): a 256px indigo sidebar, a 68px
 * white header with a role chip, a demo chip and an account menu, and a drawer below 1024px.
 * The demo banner stays above everything.
 */
export function WorkspaceShell({
  companyName,
  roleLabel,
  accountName,
  nav,
  currentHref,
  pageTitle,
  onLogout,
  children,
}: Props) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const menuRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!accountOpen) return;
    const close = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setAccountOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [accountOpen]);

  return (
    <div className="flex min-h-screen flex-col bg-cream text-sm text-text">
      <DemoDataBanner />
      <div className="flex flex-1">
        <aside aria-label="Business sidebar" className="hidden w-64 flex-none lg:block">
          <Sidebar companyName={companyName} nav={nav} currentHref={currentHref} onLogout={onLogout} />
        </aside>

        {drawerOpen && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <button
              type="button"
              aria-label="Close navigation"
              onClick={() => setDrawerOpen(false)}
              className="absolute inset-0 bg-ink/60"
            />
            <aside aria-label="Business sidebar" className="absolute inset-y-0 left-0 w-64 max-w-[85%]">
              <Sidebar
                companyName={companyName}
                nav={nav}
                currentHref={currentHref}
                onNavigate={() => setDrawerOpen(false)}
                onLogout={onLogout}
              />
            </aside>
          </div>
        )}

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="box-border flex h-[68px] items-center gap-3 border-b border-divider bg-white px-3.5 sm:px-5 lg:pr-12 lg:pl-8">
            <button
              type="button"
              onClick={() => setDrawerOpen(true)}
              aria-label="Open navigation"
              aria-expanded={drawerOpen}
              className="inline-flex size-11 items-center justify-center rounded-[8px] border border-line bg-white lg:hidden"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2A2F3A" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                <path d="M4 7h16M4 12h16M4 17h16" />
              </svg>
            </button>
            <p className="m-0 font-heading text-base font-semibold text-ink">{pageTitle}</p>
            <div className="flex-1" />
            <span className="hidden h-8 items-center rounded-full bg-ok-bg px-3 text-xs font-bold text-ok sm:inline-flex">
              {roleLabel}
            </span>
            <span className="hidden h-8 items-center rounded-full bg-pending-bg px-3 text-xs font-bold text-pending sm:inline-flex">
              Demo data
            </span>
            <span ref={menuRef} className="relative inline-flex">
              <button
                type="button"
                onClick={() => setAccountOpen((open) => !open)}
                aria-label={`Account: ${accountName}`}
                aria-haspopup="true"
                aria-expanded={accountOpen}
                className="size-10 rounded-full border-0 bg-brand font-heading font-semibold text-white"
              >
                {initials(accountName)}
              </button>
              {accountOpen && (
                <div
                  role="menu"
                  aria-label="Account"
                  className="absolute top-12 right-0 z-20 w-[260px] rounded-[10px] border border-divider bg-white p-2 shadow-menu"
                >
                  <p className="m-0 border-b border-divider px-2.5 pt-2 pb-2.5">
                    <b className="block text-ink">{accountName}</b>
                    <span className="text-xs text-text-subtle">{companyName}</span>
                  </p>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={onLogout}
                    className="flex min-h-11 w-full items-center rounded-[6px] border-0 bg-transparent px-2.5 text-left text-text"
                  >
                    Log out
                  </button>
                </div>
              )}
            </span>
          </header>
          <main className="box-border flex w-full flex-1 flex-col gap-5 px-3.5 py-6 sm:px-5 lg:pr-12 lg:pl-8">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
