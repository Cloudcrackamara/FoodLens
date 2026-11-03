"use client";

import Link from "next/link";
import { AlertsBoard } from "@/components/alerts/AlertsBoard";
import { ReportsBoard } from "@/components/reports/ReportsBoard";
import { useCurrentUser } from "@/lib/auth";
import { Announcements } from "./Announcements";
import { BatchCodes } from "./BatchCodes";
import { Catalogue } from "./Catalogue";
import { CompanyProfile } from "./CompanyDashboard";
import { CompanyShell } from "./CompanyShell";
import { PackTimeline } from "./PackTimeline";
import { Partners } from "./Partners";
import { Overview, Stats } from "./Stats";

// Client screens, so the shell can hand the company to each page (see docs/log.md, entry 136).

export function CompanyProfileScreen() {
  return (
    <CompanyShell href="/company/profile" title="Company profile">
      {({ companyId, isOwner }) => (
        <div className="mx-auto flex w-full max-w-[720px] flex-col gap-4">
          <CompanyProfile companyId={companyId} isOwner={isOwner} />
        </div>
      )}
    </CompanyShell>
  );
}

/** /company: the overview for an approved manufacturer, otherwise the company profile. */
export function CompanyHomeScreen() {
  const { data: user } = useCurrentUser();
  const membership = user?.membership;
  if (membership && !(membership.is_manufacturer && membership.company_review_status === "APPROVED")) {
    return <CompanyProfileScreen />;
  }
  return (
    <CompanyShell href="/company" title="Overview">
      {({ companyId }) => <Overview companyId={companyId} />}
    </CompanyShell>
  );
}

export function CompanyProductsScreen() {
  return (
    <CompanyShell href="/company/products" title="Products and batches" manufacturerOnly>
      {({ companyId }) => (
        <div className="mx-auto flex w-full max-w-[720px] flex-col gap-4">
          <Catalogue companyId={companyId} />
        </div>
      )}
    </CompanyShell>
  );
}

export function CompanyBatchScreen({ batchId }: { batchId: string }) {
  return (
    <CompanyShell href="/company/products" title="Products and batches" manufacturerOnly>
      {({ companyId, isOwner }) => (
        <div className="mx-auto flex w-full max-w-[720px] flex-col gap-4">
          <Link href="/company/products" className="self-start font-semibold text-brand-dark underline">
            Products and batches
          </Link>
          <BatchCodes companyId={companyId} batchId={batchId} isOwner={isOwner} />
        </div>
      )}
    </CompanyShell>
  );
}

export function CompanyTimelineScreen() {
  return (
    <CompanyShell href="/company/timeline" title="Pack timeline" manufacturerOnly>
      {({ companyId }) => <PackTimeline companyId={companyId} />}
    </CompanyShell>
  );
}

export function CompanyAlertsScreen() {
  return (
    <CompanyShell href="/company/alerts" title="Alerts" manufacturerOnly>
      {({ companyId }) => <AlertsBoard base={`/api/companies/${companyId}/alerts`} withTimeline />}
    </CompanyShell>
  );
}

export function CompanyNoticesScreen() {
  return (
    <CompanyShell href="/company/notices" title="Notices" manufacturerOnly>
      {({ companyId }) => (
        <div className="mx-auto flex w-full max-w-[720px] flex-col gap-4">
          <Announcements companyId={companyId} />
        </div>
      )}
    </CompanyShell>
  );
}

export function CompanyPartnersScreen() {
  return (
    <CompanyShell href="/company/partners" title="Partners" manufacturerOnly>
      {({ companyId }) => <Partners companyId={companyId} />}
    </CompanyShell>
  );
}

export function CompanyReportsScreen() {
  return (
    <CompanyShell href="/company/reports" title="Consumer reports" manufacturerOnly>
      {({ companyId }) => <ReportsBoard base={`/api/companies/${companyId}/reports`} />}
    </CompanyShell>
  );
}

export function CompanyStatsScreen() {
  return (
    <CompanyShell href="/company/stats" title="Stats" manufacturerOnly>
      {({ companyId }) => <Stats companyId={companyId} />}
    </CompanyShell>
  );
}
