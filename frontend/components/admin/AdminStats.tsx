"use client";

import { cellClass, DataTable, numberCellClass } from "@/components/ui/DataTable";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/Panels";
import { SummaryCard, SummaryGrid } from "@/components/ui/SummaryCard";
import { describeError } from "@/lib/api";
import { usePlatformStats, useScanningPanel } from "@/lib/dashboards";
import { formatDate } from "@/lib/format";
import { helpTextClass } from "@/lib/ui";

// Approved wording (3 Nov 2026).
const SCANNING_NOTE = "Counts by area and day only. FoodLens stores no IP addresses.";

/** /admin: the headline numbers; each card opens its page. */
export function AdminOverview() {
  const stats = usePlatformStats();

  if (stats.isPending) return <LoadingPanel />;
  if (stats.isError) return <ErrorPanel onRetry={() => stats.refetch()}>{describeError(stats.error)}</ErrorPanel>;
  const data = stats.data;
  return (
    <SummaryGrid label="Overview">
      <SummaryCard label="Companies" value={data.companies} href="/admin/queues" />
      <SummaryCard label="Open alerts" value={data.open_alerts} href="/admin/alerts" tone="alert" />
      <SummaryCard label="New reports" value={data.new_reports} href="/admin/reports" tone="new" />
      <SummaryCard label="POS partners" value={data.pos_partners} href="/admin/pos" tone="info" />
      <SummaryCard label="Checks in the last 30 days" value={data.checks_last_30_days} href="/admin/stats" tone="info" />
    </SummaryGrid>
  );
}

export function PlatformStats() {
  const stats = usePlatformStats();

  if (stats.isPending) return <LoadingPanel />;
  if (stats.isError) return <ErrorPanel onRetry={() => stats.refetch()}>{describeError(stats.error)}</ErrorPanel>;
  const data = stats.data;
  return (
    <SummaryGrid label="Platform stats">
      <SummaryCard label="Companies" value={data.companies} />
      <SummaryCard label="Approved companies" value={data.approved_companies} tone="info" />
      <SummaryCard label="Packs issued" value={data.packs_issued} tone="info" />
      <SummaryCard label="Checks in the last 30 days" value={data.checks_last_30_days} tone="info" />
      <SummaryCard label="POS partners" value={data.pos_partners} tone="info" />
      <SummaryCard label="Open alerts" value={data.open_alerts} tone="alert" />
      <SummaryCard label="New reports" value={data.new_reports} tone="new" />
      <SummaryCard label="POS rate-limit hits" value={data.pos_rate_limit_hits_last_30_days} tone="pending" />
    </SummaryGrid>
  );
}

/** Rate-limit hits and invalid-code bursts per area and day (D144, D154). Counts only. */
export function ScanningPanel() {
  const rows = useScanningPanel();

  return (
    <div className="flex flex-col gap-3">
      <p className={`m-0 ${helpTextClass}`}>{SCANNING_NOTE}</p>
      {rows.isPending && <LoadingPanel />}
      {rows.isError && <ErrorPanel onRetry={() => rows.refetch()}>{describeError(rows.error)}</ErrorPanel>}
      {rows.data?.length === 0 && <EmptyPanel title="No activity in the last 30 days." />}
      {rows.data && rows.data.length > 0 && (
        <DataTable label="Automated scanning" head={["Date", "Area", "Rate-limit hits", "Invalid codes", "Burst alerts"]}>
          {rows.data.map((row) => (
            <tr key={`${row.day}-${row.area}`}>
              <td className={cellClass}>{formatDate(row.day)}</td>
              <td className={cellClass}>{row.area}</td>
              <td className={numberCellClass}>{row.rate_limit_hits}</td>
              <td className={numberCellClass}>{row.invalid_codes}</td>
              <td className={numberCellClass}>{row.burst_alerts}</td>
            </tr>
          ))}
        </DataTable>
      )}
    </div>
  );
}
