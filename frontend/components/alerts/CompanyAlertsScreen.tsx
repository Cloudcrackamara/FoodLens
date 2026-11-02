"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { DemoDataBanner } from "@/components/DemoDataBanner";
import { EmptyPanel, LoadingPanel } from "@/components/ui/Panels";
import { WorkspaceShell } from "@/components/ui/WorkspaceShell";
import { useCurrentUser, useLogout } from "@/lib/auth";
import { companyTypeLabel } from "@/lib/companies";
import { buttonClass } from "@/lib/ui";
import { AlertsBoard } from "./AlertsBoard";

function Centered({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-cream">
      <DemoDataBanner />
      <main className="mx-auto box-border flex w-full max-w-[520px] flex-1 flex-col gap-5 px-4 py-10">{children}</main>
    </div>
  );
}

/**
 * /company/alerts: the manufacturer's own alerts in the workspace shell. Owners and staff may act
 * (D106). The server returns only this company's alerts and checks membership on every call.
 */
export function CompanyAlertsScreen() {
  const router = useRouter();
  const { data: user, isPending } = useCurrentUser();
  const logout = useLogout();

  if (isPending) {
    return (
      <Centered>
        <LoadingPanel />
      </Centered>
    );
  }
  if (!user) {
    return (
      <Centered>
        <EmptyPanel
          title="Alerts"
          action={
            <Link href="/login" className={buttonClass("primary", "sm")}>
              Sign in
            </Link>
          }
        />
      </Centered>
    );
  }
  const membership = user.membership;
  if (!membership) {
    return (
      <Centered>
        <EmptyPanel title="Alerts">Your account does not belong to a company yet.</EmptyPanel>
      </Centered>
    );
  }

  return (
    <WorkspaceShell
      companyName={membership.company_display_name}
      roleLabel={companyTypeLabel(membership)}
      accountName={user.display_name}
      nav={[
        { href: "/company", label: "My company" },
        { href: "/company/alerts", label: "Alerts" },
      ]}
      currentHref="/company/alerts"
      pageTitle="Alerts"
      onLogout={() => logout.mutate(undefined, { onSuccess: () => router.push("/login") })}
    >
      <AlertsBoard base={`/api/companies/${membership.company_id}/alerts`} />
    </WorkspaceShell>
  );
}
