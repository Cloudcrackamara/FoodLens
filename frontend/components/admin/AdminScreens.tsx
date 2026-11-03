"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { AlertsBoard } from "@/components/alerts/AlertsBoard";
import { DemoDataBanner } from "@/components/DemoDataBanner";
import { ReportsBoard } from "@/components/reports/ReportsBoard";
import { AdminShell } from "@/components/ui/AdminShell";
import { LoadingPanel } from "@/components/ui/Panels";
import type { NavItem } from "@/components/ui/WorkspaceShell";
import { useCurrentUser, useLogout } from "@/lib/auth";
import { AdminReview } from "./AdminReview";
import { AdminOverview, PlatformStats, ScanningPanel } from "./AdminStats";
import { PosPartners } from "./PosPartners";

// Approved wording (3 Nov 2026).
const NAV: NavItem[] = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/queues", label: "Review queues" },
  { href: "/admin/pos", label: "POS partners" },
  { href: "/admin/alerts", label: "Alerts" },
  { href: "/admin/reports", label: "Consumer reports" },
  { href: "/admin/stats", label: "Platform stats" },
  { href: "/admin/scanning", label: "Automated scanning" },
];

function titleFor(href: string): string {
  return NAV.find((item) => item.href === href)?.label ?? "";
}

/** Admin gate, then the admin shell. Every admin route checks the role again on the server. */
export function AdminScreen({ href, children }: { href: string; children: ReactNode }) {
  const router = useRouter();
  const { data: user, isPending } = useCurrentUser();
  const logout = useLogout();

  if (isPending || !user?.is_admin) {
    return (
      <div className="flex min-h-screen flex-col bg-white">
        <DemoDataBanner />
        <main className="mx-auto box-border flex w-full max-w-[520px] flex-1 flex-col gap-3 px-4 py-10">
          {isPending ? (
            <LoadingPanel />
          ) : (
            <>
              <p role="alert" className="m-0">Admin access required.</p>
              {!user && (
                <Link href="/login" className="font-semibold text-brand-dark underline">
                  Sign in
                </Link>
              )}
            </>
          )}
        </main>
      </div>
    );
  }

  return (
    <AdminShell
      accountName={user.display_name}
      nav={NAV}
      currentHref={href}
      pageTitle={titleFor(href)}
      onLogout={() => logout.mutate(undefined, { onSuccess: () => router.push("/login") })}
    >
      {children}
    </AdminShell>
  );
}

export function AdminOverviewScreen() {
  return (
    <AdminScreen href="/admin">
      <AdminOverview />
    </AdminScreen>
  );
}

export function AdminQueuesScreen() {
  return (
    <AdminScreen href="/admin/queues">
      <p className="m-0 text-text">
        Decisions are FoodLens demo reviews only, never NAFDAC or SON approvals. Each decision
        records you as the reviewer, with the time.
      </p>
      <AdminReview />
    </AdminScreen>
  );
}

export function AdminPosScreen() {
  return (
    <AdminScreen href="/admin/pos">
      <PosPartners />
    </AdminScreen>
  );
}

export function AdminAlertsScreen() {
  return (
    <AdminScreen href="/admin/alerts">
      <AlertsBoard base="/api/admin/alerts" />
    </AdminScreen>
  );
}

export function AdminReportsScreen() {
  return (
    <AdminScreen href="/admin/reports">
      <ReportsBoard base="/api/admin/reports" />
    </AdminScreen>
  );
}

export function AdminStatsScreen() {
  return (
    <AdminScreen href="/admin/stats">
      <PlatformStats />
    </AdminScreen>
  );
}

export function AdminScanningScreen() {
  return (
    <AdminScreen href="/admin/scanning">
      <ScanningPanel />
    </AdminScreen>
  );
}
