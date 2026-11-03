"use client";

import { useState, type FormEvent } from "react";
import { TimelineView } from "@/components/company/PackTimeline";
import { Card } from "@/components/ui/Card";
import { EmptyPanel, ErrorPanel, InlineError, LoadingPanel } from "@/components/ui/Panels";
import { StatusPill } from "@/components/ui/StatusPill";
import { describeError } from "@/lib/api";
import {
  NOTE_MAX,
  actions,
  alertFilters,
  filterLabels,
  levelLabels,
  levelTones,
  statusLabels,
  statusTones,
  useAlert,
  useAlertNote,
  useAlertStatus,
  useAlerts,
  type Alert,
  type AlertFilter,
} from "@/lib/alerts";
import { useAlertTimeline } from "@/lib/dashboards";
import { formatDate } from "@/lib/format";
import { buttonClass, cardTitleClass, helpTextClass, tabClass, textareaClass } from "@/lib/ui";

// Approved wording (30 Oct 2026).
const INTRO = "Alerts are signals to review, not verdicts. Low alerts show only here, never to buyers.";
const ADMIN_ONLY = "Admin only (no pack)";

function day(iso: string): string {
  return formatDate(iso.slice(0, 10));
}

function subject(alert: Alert): string {
  const parts = [alert.product_name, alert.batch_number, alert.carton_ref, alert.area].filter(Boolean);
  return parts.join(" · ");
}

function Pills({ alert }: { alert: Alert }) {
  return (
    <span className="flex flex-wrap gap-1.5">
      <StatusPill tone={levelTones[alert.level]}>{levelLabels[alert.level]}</StatusPill>
      <StatusPill tone={statusTones[alert.status]}>{statusLabels[alert.status]}</StatusPill>
    </span>
  );
}

// Rule 4 and rule 9 alerts have no pack, so they have no timeline.
const NO_PACK = ["R4_INVALID_BURST", "R9_MORE_OBSERVED_THAN_ALLOCATED"];

function AlertTimeline({ base, alertId }: { base: string; alertId: string }) {
  const timeline = useAlertTimeline(base, alertId, true);

  return (
    <section aria-labelledby="alert-timeline-heading" className="flex flex-col gap-2">
      <h3 id="alert-timeline-heading" className={`m-0 ${cardTitleClass}`}>Pack timeline</h3>
      {timeline.isPending && <LoadingPanel />}
      {timeline.isError && <ErrorPanel onRetry={() => timeline.refetch()}>{describeError(timeline.error)}</ErrorPanel>}
      {timeline.data && <TimelineView timeline={timeline.data} />}
    </section>
  );
}

function Detail({ base, alertId, withTimeline }: { base: string; alertId: string; withTimeline: boolean }) {
  const detail = useAlert(base, alertId);
  const status = useAlertStatus(base);
  const note = useAlertNote(base);
  const [body, setBody] = useState("");

  if (detail.isPending) return <LoadingPanel />;
  if (detail.isError) return <ErrorPanel onRetry={() => detail.refetch()}>{describeError(detail.error)}</ErrorPanel>;
  const alert = detail.data;

  function addNote(submitted: FormEvent) {
    submitted.preventDefault();
    note.mutate({ alertId, body: body.trim() }, { onSuccess: () => setBody("") });
  }

  return (
    <Card variant="workspace" aria-label={alert.rule_name} className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <Pills alert={alert} />
        <h2 className="m-0 font-heading text-lg font-semibold text-ink">{alert.rule_name}</h2>
        <p className="m-0">{alert.explanation}</p>
        <p className={`m-0 ${helpTextClass}`}>
          {subject(alert) || ADMIN_ONLY}
          {alert.manufacturer_name ? ` · ${alert.manufacturer_name}` : ""}
        </p>
        <p className={`m-0 ${helpTextClass}`}>
          Raised {day(alert.created_at)}
          {alert.resolved_at && alert.resolved_by_name
            ? ` · Resolved by ${alert.resolved_by_name} on ${day(alert.resolved_at)}`
            : ""}
        </p>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        {actions[alert.status].map((action) => (
          <button
            key={action.to}
            type="button"
            disabled={status.isPending}
            onClick={() => status.mutate({ alertId, status: action.to })}
            className={buttonClass(action.to === "RESOLVED_SUSPECTED_COPY" ? "danger" : "secondary", "sm")}
          >
            {action.label}
          </button>
        ))}
      </div>
      {status.isError && <InlineError className="m-0 text-sm">{describeError(status.error)}</InlineError>}

      <section aria-labelledby="evidence-heading" className="flex flex-col gap-2">
        <h3 id="evidence-heading" className={`m-0 ${cardTitleClass}`}>Evidence</h3>
        <ol className="m-0 flex list-none flex-col gap-2 border-l-2 border-line pl-3.5">
          {alert.snapshot.map((entry, index) => (
            <li key={`${entry.at}-${index}`} className="flex flex-col">
              <span className={helpTextClass}>{day(entry.at)}</span>
              <span>{entry.explanation}</span>
            </li>
          ))}
        </ol>
      </section>

      {withTimeline && !NO_PACK.includes(alert.rule) && <AlertTimeline base={base} alertId={alertId} />}

      <section aria-labelledby="notes-heading" className="flex flex-col gap-2">
        <h3 id="notes-heading" className={`m-0 ${cardTitleClass}`}>Notes</h3>
        {alert.notes.length > 0 && (
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {alert.notes.map((item, index) => (
              <li key={`${item.created_at}-${index}`} className="rounded-[10px] bg-paper px-3 py-2">
                <span className={`block ${helpTextClass}`}>
                  {item.author_name} · {day(item.created_at)}
                </span>
                <span className="whitespace-pre-wrap">{item.body}</span>
              </li>
            ))}
          </ul>
        )}
        <form onSubmit={addNote} aria-label="Add note" className="flex flex-col gap-1.5">
          <label htmlFor={`note-${alertId}`} className="font-semibold text-ink">
            Note
          </label>
          <textarea
            id={`note-${alertId}`}
            value={body}
            onChange={(changed) => setBody(changed.target.value)}
            maxLength={NOTE_MAX}
            rows={3}
            className={textareaClass}
          />
          {note.isError && <InlineError className="m-0 text-sm">{describeError(note.error)}</InlineError>}
          <button type="submit" disabled={!body.trim() || note.isPending} className={`self-start ${buttonClass("secondary", "sm")}`}>
            Add note
          </button>
        </form>
      </section>
    </Card>
  );
}

/**
 * Alert list and detail for a manufacturer (base /api/companies/{id}/alerts) or an admin
 * (/api/admin/alerts). Built from the workspace parts: filter tabs, list rows with pills, a
 * detail card with a timeline (no board in design/).
 */
export function AlertsBoard({ base, withTimeline = false }: { base: string; withTimeline?: boolean }) {
  const [filter, setFilter] = useState<AlertFilter>("OPEN");
  const [selected, setSelected] = useState<string | null>(null);
  const list = useAlerts(base, filter);

  return (
    <div className="flex flex-col gap-4">
      <p className="m-0 text-text-subtle">{INTRO}</p>
      <div role="tablist" aria-label="Alert status" className="flex flex-wrap gap-2">
        {alertFilters.map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={filter === value}
            onClick={() => {
              setFilter(value);
              setSelected(null);
            }}
            className={tabClass(filter === value)}
          >
            {filterLabels[value]}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <div className="flex min-w-0 flex-col gap-2">
          {list.isPending && <LoadingPanel />}
          {list.isError && <ErrorPanel onRetry={() => list.refetch()}>{describeError(list.error)}</ErrorPanel>}
          {list.data?.length === 0 && <EmptyPanel title="No alerts in this list." />}
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {list.data?.map((alert) => (
              <li key={alert.alert_id}>
                <button
                  type="button"
                  aria-current={selected === alert.alert_id ? "true" : undefined}
                  onClick={() => setSelected(alert.alert_id)}
                  className={`flex w-full flex-col gap-1.5 rounded-[12px] bg-white p-4 text-left shadow-card ${
                    selected === alert.alert_id ? "outline-2 outline-brand" : ""
                  }`}
                >
                  <Pills alert={alert} />
                  <span className="font-semibold text-ink">{alert.rule_name}</span>
                  <span className={helpTextClass}>
                    {subject(alert) || ADMIN_ONLY} · Raised {day(alert.created_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="min-w-0">{selected && <Detail base={base} alertId={selected} withTimeline={withTimeline} />}</div>
      </div>
    </div>
  );
}
