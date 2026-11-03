"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { DemoDataBanner } from "@/components/DemoDataBanner";
import type { NavItem } from "./WorkspaceShell";

type Props = {
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

function Sidebar({ nav, currentHref, onNavigate }: Pick<Props, "nav" | "currentHref"> & { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-1.5 bg-white px-6 py-[22px]">
      <Link href="/" className="flex items-center gap-2.5 pt-1 pb-8 text-ink no-underline">
        <svg width="34" height="34" viewBox="0 0 36 36" aria-hidden="true">
          <circle cx="15" cy="15" r="11" fill="none" stroke="#1B7A45" strokeWidth="3.5" />
          <path d="M23 23l9 9" stroke="#1B7A45" strokeWidth="4" strokeLinecap="round" />
          <path d="M10 15.5l3.5 3.5 6.5-7" fill="none" stroke="#1B7A45" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="whitespace-nowrap font-heading text-[22px]">
          <b>FoodLens</b> <span className="font-medium text-[#5F6472]">admin</span>
        </span>
      </Link>
      <nav aria-label="Admin navigation" className="flex flex-col gap-[3px]">
        {nav.map((item) => {
          const current = item.href === currentHref;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={current ? "page" : undefined}
              onClick={onNavigate}
              className={`flex min-h-11 items-center rounded-[6px] px-3.5 no-underline ${
                current ? "bg-brand font-semibold text-white" : "text-[#2A2F3A]"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

/**
 * The admin shell (design/README.md, component 6; Admin.dc.html): a 270px white sidebar, a 72px
 * header with a chip and the account menu, and a drawer below 1024px. The board's search box and
 * theme button are left out: nothing searches yet, and the app is light only.
 */
export function AdminShell({ accountName, nav, currentHref, pageTitle, onLogout, children }: Props) {
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
    <div className="flex min-h-screen flex-col bg-white text-sm text-text">
      <DemoDataBanner />
      <div className="flex flex-1">
        <aside aria-label="Admin sidebar" className="hidden w-[270px] flex-none border-r border-divider lg:block">
          <Sidebar nav={nav} currentHref={currentHref} />
        </aside>

        {drawerOpen && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <button
              type="button"
              aria-label="Close navigation"
              onClick={() => setDrawerOpen(false)}
              className="absolute inset-0 bg-ink/60"
            />
            <aside aria-label="Admin sidebar" className="absolute inset-y-0 left-0 w-[270px] max-w-[85%]">
              <Sidebar nav={nav} currentHref={currentHref} onNavigate={() => setDrawerOpen(false)} />
            </aside>
          </div>
        )}

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="box-border flex h-[72px] items-center gap-3.5 px-4 sm:px-6 lg:pr-14 lg:pl-5">
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
            <p className="m-0 font-heading text-lg font-semibold text-ink">{pageTitle}</p>
            <div className="flex-1" />
            <span className="box-border hidden h-10 items-center rounded-full border-2 border-brand px-4 font-heading text-[15px] font-semibold text-brand-dark sm:inline-flex">
              Demo data
            </span>
            <span ref={menuRef} className="relative inline-flex">
              <button
                type="button"
                onClick={() => setAccountOpen((open) => !open)}
                aria-label={`Account: ${accountName}`}
                aria-haspopup="true"
                aria-expanded={accountOpen}
                className="ml-1 size-10 rounded-full border-0 bg-ink font-heading font-semibold text-sun"
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
          <main className="box-border flex w-full flex-1 flex-col gap-6 px-4 py-6 sm:px-6 lg:pt-11 lg:pr-[60px] lg:pb-[30px] lg:pl-5">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
