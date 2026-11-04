"use client";

import { cellClass, DataTable, InlineBar, numberCellClass } from "@/components/ui/DataTable";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/Panels";
import { StatusPill } from "@/components/ui/StatusPill";
import { SummaryCard, SummaryGrid } from "@/components/ui/SummaryCard";
import { levelLabels, levelTones } from "@/lib/alerts";
import { describeError } from "@/lib/api";
import { useStats } from "@/lib/dashboards";
import { formatDate } from "@/lib/format";
import { cardTitleClass, helpTextClass } from "@/lib/ui";

// Approved wording (3 Nov 2026).
const EMPTY = "Nothing to show yet. Stats appear once packs are released and checked.";
const COVERAGE_NOTE = "Sale coverage counts only sales recorded on FoodLens. Shops that don't record sales lower it.";

function percent(value: number | null): string {
  return value === null ? "—" : `${value}%`;
}

function Heading({ id, children }: { id: string; children: string }) {
  return (
    <h2 id={id} className={`m-0 ${cardTitleClass}`}>
      {children}
    </h2>
  );
}

/** Manufacturer stats (D154): tiles and tables with one-hue bars; no chart library, no maps. */
export function Stats({ companyId }: { companyId: string }) {
  const stats = useStats(companyId);

  if (stats.isPending) return <LoadingPanel />;
  if (stats.isError) return <ErrorPanel onRetry={() => stats.refetch()}>{describeError(stats.error)}</ErrorPanel>;
  const data = stats.data;
  if (data.issued === 0 && data.checks_by_city_week.length === 0 && data.alerts.length === 0) {
    return <EmptyPanel title={EMPTY} />;
  }
  const maxChecks = Math.max(0, ...data.checks_by_city_week.map((row) => row.checks));

  return (
    <div className="flex flex-col gap-6">
      <SummaryGrid label="Stats summary">
        <SummaryCard label="Packs issued" value={data.issued} />
        <SummaryCard label="Packs released" value={data.released} tone="info" />
        <SummaryCard label="Sale coverage" value={percent(data.sale_coverage_pct)} tone="new" />
        <SummaryCard label="POS sales" value={data.pos_sales} sub={percent(data.pos_share_pct)} tone="info" />
        <SummaryCard label="Merchant page sales" value={data.merchant_sales} sub={percent(data.merchant_share_pct)} tone="info" />
        <SummaryCard label="Alerts raised" value={data.alerts_raised} tone="pending" />
        <SummaryCard label="Alerts resolved" value={data.alerts_resolved} tone="pending" />
        <SummaryCard
          label="Median time to resolve"
          value={data.median_hours_to_resolve === null ? "—" : `${data.median_hours_to_resolve} h`}
          tone="pending"
        />
      </SummaryGrid>
      <p className={`m-0 ${helpTextClass}`}>{COVERAGE_NOTE}</p>

      <section aria-labelledby="checks-heading" className="flex flex-col gap-3">
        <Heading id="checks-heading">Checks by city and week</Heading>
        {data.checks_by_city_week.length === 0 ? (
          <EmptyPanel title={EMPTY} />
        ) : (
          <DataTable label="Checks by city and week" head={["Week", "City", "Checks", ""]}>
            {data.checks_by_city_week.map((row) => (
              <tr key={`${row.week_start}-${row.city}`}>
                <td className={cellClass}>{formatDate(row.week_start)}</td>
                <td className={cellClass}>{row.city}</td>
                <td className={numberCellClass}>{row.checks}</td>
                <td className={`${cellClass} w-1/3`}>
                  <InlineBar value={row.checks} max={maxChecks} />
                </td>
              </tr>
            ))}
          </DataTable>
        )}
      </section>

      <section aria-labelledby="spots-heading" className="flex flex-col gap-3">
        <Heading id="spots-heading">Hot spots</Heading>
        {data.hot_spots.length === 0 ? (
          <EmptyPanel title="No checks from a known place yet." />
        ) : (
          <DataTable label="Hot spots" head={["City", "Open alerts", "Checks"]}>
            {data.hot_spots.map((spot) => (
              <tr key={spot.city}>
                <td className={cellClass}>{spot.city}</td>
                <td className={numberCellClass}>{spot.open_alerts}</td>
                <td className={numberCellClass}>{spot.checks}</td>
              </tr>
            ))}
          </DataTable>
        )}
      </section>

      {data.alerts.length > 0 && (
        <section aria-labelledby="alert-counts-heading" className="flex flex-col gap-3">
          <Heading id="alert-counts-heading">Alerts raised</Heading>
          <DataTable label="Alerts by rule and level" head={["Rule", "Level", "Alerts raised", "Alerts resolved"]}>
            {data.alerts.map((row) => (
              <tr key={`${row.rule}-${row.level}`}>
                <td className={cellClass}>{row.rule_name}</td>
                <td className={cellClass}>
                  <StatusPill tone={levelTones[row.level]}>{levelLabels[row.level]}</StatusPill>
                </td>
                <td className={numberCellClass}>{row.raised}</td>
                <td className={numberCellClass}>{row.resolved}</td>
              </tr>
            ))}
          </DataTable>
        </section>
      )}
    </div>
  );
}

/** /company: the headline numbers; each card opens its page. */
export function Overview({ companyId }: { companyId: string }) {
  const stats = useStats(companyId);

  if (stats.isPending) return <LoadingPanel />;
  if (stats.isError) return <ErrorPanel onRetry={() => stats.refetch()}>{describeError(stats.error)}</ErrorPanel>;
  const data = stats.data;
  return (
    <SummaryGrid label="Overview">
      <SummaryCard label="Packs issued" value={data.issued} href="/company/products" />
      <SummaryCard label="Packs released" value={data.released} href="/company/products" tone="info" />
      <SummaryCard label="Sale coverage" value={percent(data.sale_coverage_pct)} href="/company/stats" tone="new" />
      <SummaryCard label="Alerts raised" value={data.alerts_raised} href="/company/alerts" tone="pending" />
      <SummaryCard label="Alerts resolved" value={data.alerts_resolved} href="/company/alerts" tone="pending" />
    </SummaryGrid>
  );
}
