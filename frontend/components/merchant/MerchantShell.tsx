"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { DemoDataBanner } from "@/components/DemoDataBanner";
import { EmptyPanel, LoadingPanel } from "@/components/ui/Panels";
import { WorkspaceShell, type NavItem } from "@/components/ui/WorkspaceShell";
import { useCurrentUser, useLogout } from "@/lib/auth";
import { canUseMerchant } from "@/lib/merchant";
import { buttonClass } from "@/lib/ui";
import { MerchantPage } from "./MerchantPage";
import { TeamPage } from "./TeamPage";

type Role = "OWNER" | "STAFF";

type Props = {
  /** The page being shown, for the active nav item. */
  href: "/merchant" | "/merchant/team";
  title: string;
  /** Pages only the owner can use (staff management, D106). */
  ownerOnly?: boolean;
  children: (access: { companyId: string; role: Role }) => ReactNode;
};

function Centered({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-cream">
      <DemoDataBanner />
      <main className="mx-auto box-border flex w-full max-w-[520px] flex-1 flex-col gap-5 px-4 py-10">{children}</main>
    </div>
  );
}

/**
 * Sign-in and company gate for the merchant pages, then the workspace shell. Hiding a page here
 * is only a convenience: every merchant and staff route checks the role and the company again on
 * the server (CLAUDE.md rule 8).
 */
export function MerchantShell({ href, title, ownerOnly = false, children }: Props) {
  const router = useRouter();
  const { data: user, isPending } = useCurrentUser();
  const logout = useLogout();

  if (isPending) {
    return (
      <Centered>
        <LoadingPanel label="Loading your account" />
      </Centered>
    );
  }
  if (!user) {
    return (
      <Centered>
        <EmptyPanel
          title="Sign in to record stock events"
          action={
            <Link href="/login" className={buttonClass("primary", "sm")}>
              Sign in
            </Link>
          }
        >
          The merchant page is for distributor and retailer accounts.
        </EmptyPanel>
      </Centered>
    );
  }
  const membership = user.membership;
  if (!membership || !canUseMerchant(user)) {
    return (
      <Centered>
        <EmptyPanel title="This page is for approved distributors and retailers">
          {membership
            ? "Your company must be an approved distributor or retailer to record stock events."
            : "Your account does not belong to a company yet."}
        </EmptyPanel>
      </Centered>
    );
  }
  if (ownerOnly && membership.role !== "OWNER") {
    return (
      <Centered>
        <EmptyPanel
          title="Only the owner can manage the team"
          action={
            <Link href="/merchant" className={buttonClass("secondary", "sm")}>
              Back to recording events
            </Link>
          }
        />
      </Centered>
    );
  }

  const nav: NavItem[] = [{ href: "/merchant", label: "Record events" }];
  if (membership.role === "OWNER") nav.push({ href: "/merchant/team", label: "Team" });

  return (
    <WorkspaceShell
      companyName={membership.company_display_name}
      roleLabel={membership.is_distributor && membership.is_retailer ? "Distributor and retailer" : membership.is_distributor ? "Distributor" : "Retailer"}
      accountName={user.display_name}
      nav={nav}
      currentHref={href}
      pageTitle={title}
      onLogout={() => logout.mutate(undefined, { onSuccess: () => router.push("/login") })}
    >
      {children({ companyId: membership.company_id, role: membership.role })}
    </WorkspaceShell>
  );
}

/** /merchant inside the shell. Client side, so the shell can hand the company to the page. */
export function MerchantRecordScreen() {
  return (
    <MerchantShell href="/merchant" title="Record stock events">
      {({ companyId }) => (
        <div className="mx-auto flex w-full max-w-[560px] flex-col gap-4">
          <MerchantPage companyId={companyId} />
        </div>
      )}
    </MerchantShell>
  );
}

/** /merchant/team inside the shell (owner only). */
export function MerchantTeamScreen() {
  return (
    <MerchantShell href="/merchant/team" title="Team" ownerOnly>
      {({ companyId }) => (
        <div className="mx-auto flex w-full max-w-[560px] flex-col gap-4">
          <TeamPage companyId={companyId} />
        </div>
      )}
    </MerchantShell>
  );
}
