"use client";

import { useState } from "react";
import { EmptyPanel, ErrorPanel, InlineError, LoadingPanel } from "@/components/ui/Panels";
import { StatusPill } from "@/components/ui/StatusPill";
import { describeError } from "@/lib/api";
import {
  concernLabel,
  reportActions,
  reportStatusLabels,
  reportStatuses,
  reportStatusTones,
  useReports,
  useReportStatus,
  type Report,
  type ReportStatus,
} from "@/lib/dashboards";
import { formatDate } from "@/lib/format";
import { buttonClass, detailListClass, detailTermClass, detailValueClass, tabClass } from "@/lib/ui";

function pack(report: Report): string {
  return [report.product_name, report.batch_number].filter(Boolean).join(" · ") || "—";
}

function ReportRow({ base, report }: { base: string; report: Report }) {
  const change = useReportStatus(base);
  const actions = reportActions[report.status];

  return (
    <li aria-label={concernLabel(report.concern_type)} className="flex flex-col gap-3 rounded-[12px] bg-white p-5 shadow-card">
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill tone={reportStatusTones[report.status]}>{reportStatusLabels[report.status]}</StatusPill>
        {report.manufacturer_name && <span className="text-text-subtle">{report.manufacturer_name}</span>}
      </div>
      <dl className={`m-0 ${detailListClass}`}>
        <dt className={detailTermClass}>Concern</dt>
        <dd className={`m-0 ${detailValueClass}`}>{concernLabel(report.concern_type)}</dd>
        <dt className={detailTermClass}>Pack</dt>
        <dd className={`m-0 ${detailValueClass}`}>{pack(report)}</dd>
        <dt className={detailTermClass}>Place</dt>
        <dd className={`m-0 ${detailValueClass}`}>{report.area ?? "—"}</dd>
        <dt className={detailTermClass}>Received</dt>
        <dd className={`m-0 ${detailValueClass}`}>{formatDate(report.created_at.slice(0, 10))}</dd>
      </dl>
      <p className="m-0 whitespace-pre-wrap">{report.description}</p>
      {actions.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {actions.map((action) => (
            <button
              key={action.to}
              type="button"
              disabled={change.isPending}
              onClick={() => change.mutate({ reportId: report.report_id, status: action.to })}
              className={buttonClass("secondary", "sm")}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
      {change.isError && <InlineError className="m-0 text-sm">{describeError(change.error)}</InlineError>}
    </li>
  );
}

/**
 * Anonymous consumer reports (D120, D154) for a manufacturer (/api/companies/{id}/reports) or an
 * admin (/api/admin/reports). There is no contact field to show: reports are anonymous.
 */
export function ReportsBoard({ base }: { base: string }) {
  const [status, setStatus] = useState<ReportStatus>("NEW");
  const reports = useReports(base, status);

  return (
    <div className="flex flex-col gap-4">
      <div role="tablist" aria-label="Report status" className="flex flex-wrap gap-2">
        {reportStatuses.map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={status === value}
            onClick={() => setStatus(value)}
            className={tabClass(status === value)}
          >
            {reportStatusLabels[value]}
          </button>
        ))}
      </div>
      {reports.isPending && <LoadingPanel />}
      {reports.isError && <ErrorPanel onRetry={() => reports.refetch()}>{describeError(reports.error)}</ErrorPanel>}
      {reports.data?.length === 0 && <EmptyPanel title="No reports in this list." />}
      <ul className="m-0 flex list-none flex-col gap-3 p-0">
        {reports.data?.map((report) => <ReportRow key={report.report_id} base={base} report={report} />)}
      </ul>
    </div>
  );
}
