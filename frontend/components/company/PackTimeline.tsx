"use client";

import { useState, type FormEvent } from "react";
import { Card } from "@/components/ui/Card";
import { InlineError } from "@/components/ui/Panels";
import { Spinner } from "@/components/ui/Spinner";
import { StatusPill, type Tone } from "@/components/ui/StatusPill";
import { levelLabels, levelTones } from "@/lib/alerts";
import { describeError } from "@/lib/api";
import { groupCode, normaliseCode } from "@/lib/check";
import { useTimelineLookup, type Timeline } from "@/lib/dashboards";
import { formatDate } from "@/lib/format";
import { unitStatusLabels } from "@/lib/units";
import {
  busyButtonClass,
  buttonClass,
  cardTitleClass,
  codeInputClass,
  helpTextClass,
} from "@/lib/ui";

const STATUS_TONES: Record<string, Tone> = {
  ISSUED: "pending",
  RELEASED: "info",
  IN_TRANSIT: "new",
  IN_STOCK: "ok",
  SOLD: "neutral",
  VOIDED: "bad",
};

/** A pack's or carton's history in plain words (design/README.md, component 13). */
export function TimelineView({ timeline }: { timeline: Timeline }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill tone={STATUS_TONES[timeline.status] ?? "neutral"}>{unitStatusLabels[timeline.status]}</StatusPill>
        <span className="font-semibold text-ink">
          {timeline.product_name}
          {timeline.size ? ` · ${timeline.size}` : ""}
        </span>
      </div>
      <p className={`m-0 ${helpTextClass}`}>
        Batch <span className="font-mono">{timeline.batch_number}</span>
        {timeline.expiry_date ? ` · Expiry ${formatDate(timeline.expiry_date)}` : ""}
        {timeline.code_last4 ? ` · Code ending ${timeline.code_last4}` : ""}
      </p>
      {timeline.entries.length === 0 ? (
        <p className="m-0">No events recorded yet.</p>
      ) : (
        <ol className="m-0 flex list-none flex-col gap-2 border-l-2 border-line pl-3.5">
          {timeline.entries.map((entry, index) => (
            <li key={`${entry.at}-${index}`} className="flex flex-col">
              <span>{entry.text}</span>
              {entry.note && <span className={helpTextClass}>{entry.note}</span>}
            </li>
          ))}
        </ol>
      )}
      {timeline.open_alerts.length > 0 && (
        <section aria-labelledby="timeline-alerts" className="flex flex-col gap-1.5">
          <h3 id="timeline-alerts" className={`m-0 ${cardTitleClass}`}>Open alerts on this pack</h3>
          <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
            {timeline.open_alerts.map((alert) => (
              <li key={alert.alert_id} className="flex flex-wrap items-center gap-2">
                <StatusPill tone={levelTones[alert.level]}>{levelLabels[alert.level]}</StatusPill>
                {alert.rule_name}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

/** /company/timeline: type a code to read its history. Only the manufacturer's own codes answer. */
export function PackTimeline({ companyId }: { companyId: string }) {
  const [typed, setTyped] = useState("");
  const lookup = useTimelineLookup(companyId);
  const normalised = normaliseCode(typed);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (normalised) lookup.mutate(normalised);
  }

  return (
    <div className="mx-auto flex w-full max-w-[640px] flex-col gap-4">
      <Card variant="workspace" aria-label="Find a pack" className="flex flex-col gap-3">
        <h2 className={`m-0 ${cardTitleClass}`}>Find a pack</h2>
        <form onSubmit={submit} className="flex flex-col gap-2">
          <label htmlFor="timeline-code" className="font-semibold text-ink">
            The code printed under the QR
          </label>
          <input
            id="timeline-code"
            value={typed}
            onChange={(changed) => setTyped(changed.target.value)}
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            maxLength={40}
            className={`${codeInputClass("default", lookup.isPending)} uppercase`}
          />
          {normalised && <p className={`m-0 font-mono ${helpTextClass}`}>{groupCode(normalised)}</p>}
          {lookup.isError && <InlineError className="m-0 text-sm">{describeError(lookup.error)}</InlineError>}
          {lookup.isPending ? (
            <button type="submit" disabled aria-busy="true" className={busyButtonClass}>
              <Spinner />
              Look up
            </button>
          ) : (
            <button type="submit" disabled={!normalised} className={`self-start ${buttonClass("primary", "sm")}`}>
              Look up
            </button>
          )}
        </form>
      </Card>
      {lookup.data && (
        <Card variant="workspace" aria-label="Pack timeline">
          <TimelineView timeline={lookup.data} />
        </Card>
      )}
    </div>
  );
}
