"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { DemoDataBanner } from "@/components/DemoDataBanner";
import { EmptyPanel, LoadingPanel } from "@/components/ui/Panels";
import { WorkspaceShell, type NavItem } from "@/components/ui/WorkspaceShell";
import { useCurrentUser, useLogout } from "@/lib/auth";
import { companyTypeLabel } from "@/lib/companies";
import { canUseMerchant } from "@/lib/merchant";
import { buttonClass } from "@/lib/ui";

// Approved wording (3 Nov 2026).
const PROFILE: NavItem = { href: "/company/profile", label: "Company profile" };
const MANUFACTURER_NAV: NavItem[] = [
  { href: "/company", label: "Overview" },
  { href: "/company/products", label: "Products and batches" },
  { href: "/company/timeline", label: "Pack timeline" },
  { href: "/company/alerts", label: "Alerts" },
  { href: "/company/notices", label: "Notices" },
  { href: "/company/partners", label: "Partners" },
  { href: "/company/reports", label: "Consumer reports" },
  { href: "/company/stats", label: "Stats" },
  PROFILE,
];

export type CompanyAccess = { companyId: string; isOwner: boolean; manufacturerReady: boolean };

function Centered({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-cream">
      <DemoDataBanner />
      <main className="mx-auto box-border flex w-full max-w-[520px] flex-1 flex-col gap-5 px-4 py-10">{children}</main>
    </div>
  );
}

type Props = {
  href: string;
  title: string;
  /** Manufacturer pages. Hiding them is a convenience: every route checks again on the server. */
  manufacturerOnly?: boolean;
  children: (access: CompanyAccess) => ReactNode;
};

/**
 * Sign-in and company gate, then the workspace shell (design/README.md, component 5). Approved
 * manufacturers get the full navigation; other companies get their profile and the merchant page.
 */
export function CompanyShell({ href, title, manufacturerOnly = false, children }: Props) {
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
        <p className="m-0">
          <Link href="/login" className="font-semibold text-brand-dark underline">Sign in</Link> to manage your company.
        </p>
      </Centered>
    );
  }
  const membership = user.membership;
  if (!membership) {
    return (
      <Centered>
        <p className="m-0">
          Your account is not linked to a company yet.{" "}
          <Link href="/company/register" className="font-semibold text-brand-dark underline">Register your company</Link>.
        </p>
      </Centered>
    );
  }

  const approved = membership.company_review_status === "APPROVED";
  const manufacturerReady = approved && membership.is_manufacturer;
  const nav: NavItem[] = manufacturerReady ? [...MANUFACTURER_NAV] : [PROFILE];
  if (canUseMerchant(user)) nav.push({ href: "/merchant", label: "Record events" });

  let blocked: string | null = null;
  if (manufacturerOnly && !membership.is_manufacturer) blocked = "Only manufacturer companies manage pack codes";
  else if (manufacturerOnly && !approved) blocked = "Pack codes can be managed after FoodLens approves your company profile";

  return (
    <WorkspaceShell
      companyName={membership.company_display_name}
      roleLabel={companyTypeLabel(membership)}
      accountName={user.display_name}
      nav={nav}
      currentHref={href}
      pageTitle={title}
      sectionLabel="COMPANY"
      onLogout={() => logout.mutate(undefined, { onSuccess: () => router.push("/login") })}
    >
      {blocked ? (
        <EmptyPanel
          title={blocked}
          action={
            <Link href={PROFILE.href} className={buttonClass("secondary", "sm")}>
              {PROFILE.label}
            </Link>
          }
        />
      ) : (
        children({ companyId: membership.company_id, isOwner: membership.role === "OWNER", manufacturerReady })
      )}
    </WorkspaceShell>
  );
}
