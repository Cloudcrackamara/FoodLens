"use client";

import { useState, type FormEvent } from "react";
import { ScanQr } from "@/components/check/ScanQr";
import { Card } from "@/components/ui/Card";
import { InlineError } from "@/components/ui/Panels";
import { StatusPill, type Tone } from "@/components/ui/StatusPill";
import { Spinner } from "@/components/ui/Spinner";
import { describeError } from "@/lib/api";
import { groupCode, normaliseCode } from "@/lib/check";
import {
  REASON_MAX,
  eventLabels,
  useDestinations,
  useLookup,
  useRecordEvent,
  type EventResult,
  type Lookup,
  type MerchantEvent,
} from "@/lib/merchant";
import type { QrDecoder } from "@/lib/qr";
import { unitStatusLabels } from "@/lib/units";
import { busyButtonClass, buttonClass, codeInputClass } from "@/lib/ui";

const STATUS_TONES: Record<string, Tone> = {
  ISSUED: "pending",
  RELEASED: "info",
  IN_TRANSIT: "new",
  IN_STOCK: "ok",
  SOLD: "neutral",
  RECALLED: "alert",
  VOIDED: "bad",
};

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

function CheckIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#1B7A45" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </svg>
  );
}

function Summary({ lookup }: { lookup: Lookup }) {
  const carton = lookup.subject === "CARTON";
  return (
    <Card variant="workspace" aria-label="Code details" className="flex flex-col gap-3">
      <div>
        <h2 className="m-0 font-heading text-lg font-semibold text-ink">{lookup.product_name}</h2>
        <p className="m-0 text-text-subtle">
          {lookup.brand}
          {lookup.size ? ` · ${lookup.size}` : ""}
        </p>
      </div>
      <dl className="m-0 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5">
        <dt className="text-text-subtle">Batch</dt>
        <dd className="m-0 font-mono">{lookup.batch_number}</dd>
        {lookup.expiry_date && (
          <>
            <dt className="text-text-subtle">Expiry</dt>
            <dd className="m-0">{lookup.expiry_date}</dd>
          </>
        )}
        <dt className="text-text-subtle">Code ending</dt>
        <dd className="m-0 font-mono">{lookup.code_last4}</dd>
        <dt className="text-text-subtle">{carton ? "Carton" : "Pack"}</dt>
        <dd className="m-0">{carton ? `Carton of ${plural(lookup.packs, "pack", "packs")}` : "Single pack"}</dd>
      </dl>
      <div className="flex flex-wrap gap-2">
        {lookup.status_counts.map(({ status, packs }) => (
          <StatusPill key={status} tone={STATUS_TONES[status] ?? "neutral"}>
            {carton ? `${packs} ${unitStatusLabels[status]}` : unitStatusLabels[status]}
          </StatusPill>
        ))}
        {lookup.recalled && <StatusPill tone="alert">Recall in force</StatusPill>}
      </div>
    </Card>
  );
}

/** Radio cards for the events this company can record on this code (Report.dc.html cards). */
function EventChoice({
  allowed,
  value,
  onChange,
}: {
  allowed: MerchantEvent[];
  value: MerchantEvent | null;
  onChange: (event: MerchantEvent) => void;
}) {
  return (
    <fieldset className="m-0 flex min-w-0 flex-col gap-2 border-0 p-0">
      <legend className="float-left mb-1.5 w-full p-0 font-semibold text-ink">What happened to it?</legend>
      {allowed.map((event) => {
        const selected = value === event;
        return (
          <label
            key={event}
            className={`flex cursor-pointer items-start gap-3 rounded-[12px] px-3.5 py-3 ${
              selected ? "border-2 border-brand bg-[#F4FAF6]" : "border border-line bg-white"
            }`}
          >
            <input
              type="radio"
              name="merchant-event"
              value={event}
              checked={selected}
              onChange={() => onChange(event)}
              className="mt-px size-[22px] flex-none accent-brand"
            />
            <span>
              <span className="block font-semibold">{eventLabels[event].title}</span>
              <span className="block text-sm text-text-subtle">{eventLabels[event].hint}</span>
            </span>
          </label>
        );
      })}
    </fieldset>
  );
}

type Step =
  | { name: "start" }
  | { name: "event"; code: string; lookup: Lookup }
  | { name: "done"; result: EventResult };

/**
 * /merchant: scan or type a pack or carton code, then record what happened to it. The server
 * decides what is allowed, the status and the area; this page only sends the code, the event, the
 * receiving company and the reason. Screen composed from the Scan (camera, bottom sheet), Confirm
 * (code field) and Report (radio cards) parts: there is no merchant board in design/.
 */
export function MerchantPage({ companyId, decoder }: { companyId: string; decoder?: QrDecoder }) {
  const [step, setStep] = useState<Step>({ name: "start" });
  const [scanning, setScanning] = useState(false);
  const [typed, setTyped] = useState("");
  const [event, setEvent] = useState<MerchantEvent | null>(null);
  const [target, setTarget] = useState("");
  const [reason, setReason] = useState("");
  const [confirming, setConfirming] = useState(false);
  const lookup = useLookup(companyId);
  const record = useRecordEvent(companyId);
  const needsTarget = event === "TRANSFERRED";
  const destinations = useDestinations(companyId, step.name === "event" && needsTarget);

  function find(code: string) {
    const normalised = normaliseCode(code);
    lookup.mutate(normalised, {
      onSuccess: (found) => {
        setStep({ name: "event", code: normalised, lookup: found });
        setEvent(found.allowed_events[0] ?? null);
        setTarget("");
        setReason("");
        setConfirming(false);
        record.reset();
      },
    });
  }

  function restart() {
    setStep({ name: "start" });
    setTyped("");
    setEvent(null);
    setConfirming(false);
    lookup.reset();
    record.reset();
  }

  function submitTyped(submitted: FormEvent) {
    submitted.preventDefault();
    if (normaliseCode(typed)) find(typed);
  }

  if (scanning) {
    return (
      <ScanQr
        decoder={decoder}
        onCancel={() => setScanning(false)}
        onTypeInstead={() => setScanning(false)}
        onCode={(code) => {
          setScanning(false);
          setTyped(code);
          find(code);
        }}
      />
    );
  }

  if (step.name === "done") {
    const { result } = step;
    return (
      <Card variant="workspace" aria-label="Recorded" className="flex flex-col items-center gap-3 text-center">
        <span aria-hidden="true" className="inline-flex size-16 items-center justify-center rounded-full bg-brand-tint">
          <CheckIcon />
        </span>
        <p role="status" className="m-0 font-heading text-lg font-semibold text-ink">
          {plural(result.packs, "pack", "packs")} {eventLabels[result.event_type].done}.
        </p>
        {result.notes.map((note) => (
          <p key={note} className="m-0 rounded-[10px] bg-neutral-bg px-3 py-2 text-sm text-neutral">
            {note}
          </p>
        ))}
        <button type="button" onClick={restart} className={buttonClass("primary", "lg")}>
          Record another
        </button>
      </Card>
    );
  }

  if (step.name === "event") {
    const { lookup: found, code } = step;
    const carton = found.subject === "CARTON";
    const reasonOk = event !== "SALE_CORRECTED" || reason.trim().length > 0;
    const targetOk = !needsTarget || target !== "";
    const ready = event !== null && reasonOk && targetOk;

    function send() {
      if (!event) return;
      record.mutate(
        {
          code,
          event_type: event,
          ...(needsTarget ? { to_company_id: target } : {}),
          ...(event === "SALE_CORRECTED" ? { reason: reason.trim() } : {}),
        },
        { onSuccess: (result) => setStep({ name: "done", result }) },
      );
    }

    return (
      <div className="flex flex-col gap-4">
        <Summary lookup={found} />
        {found.allowed_events.length === 0 ? (
          <Card variant="workspace" className="flex flex-col gap-3">
            <p role="alert" className="m-0 font-semibold text-bad">
              {found.blocked_reason ?? "Nothing can be recorded for this code right now."}
            </p>
            <button type="button" onClick={restart} className={buttonClass("secondary", "md")}>
              Look up another code
            </button>
          </Card>
        ) : confirming && event ? (
          <Card variant="workspace" aria-label="Confirm" className="flex flex-col gap-3">
            <h2 className="m-0 font-heading text-lg font-semibold text-ink">
              Record {eventLabels[event].title.toLowerCase()} for {plural(found.packs, "pack", "packs")}?
            </h2>
            <p className="m-0">
              This applies to all {found.packs} packs in the carton. If one of them can&apos;t take it,
              none are recorded.
            </p>
            {record.isError && <InlineError className="text-sm">{describeError(record.error)}</InlineError>}
            <div className="flex flex-col gap-2.5 sm:flex-row">
              {record.isPending ? (
                <button type="button" disabled aria-busy="true" className={busyButtonClass}>
                  <Spinner />
                  Recording…
                </button>
              ) : (
                <button type="button" onClick={send} className={`flex-1 ${buttonClass("primary", "lg")}`}>
                  Confirm for {plural(found.packs, "pack", "packs")}
                </button>
              )}
              <button
                type="button"
                onClick={() => setConfirming(false)}
                disabled={record.isPending}
                className={`flex-1 ${buttonClass("secondary", "lg")}`}
              >
                Go back
              </button>
            </div>
          </Card>
        ) : (
          <Card variant="workspace" className="flex flex-col gap-4">
            <EventChoice allowed={found.allowed_events} value={event} onChange={setEvent} />
            {needsTarget && (
              <div className="flex flex-col gap-1.5">
                <label htmlFor="merchant-target" className="font-semibold text-ink">
                  Send to
                </label>
                <select
                  id="merchant-target"
                  value={target}
                  onChange={(changed) => setTarget(changed.target.value)}
                  className="min-h-[46px] w-full rounded-[10px] border border-line-input bg-white px-3 text-base text-ink"
                >
                  <option value="">Choose an approved company</option>
                  {destinations.data?.map((company) => (
                    <option key={company.company_id} value={company.company_id}>
                      {company.display_name}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {event === "SALE_CORRECTED" && (
              <div className="flex flex-col gap-1.5">
                <label htmlFor="merchant-reason" className="font-semibold text-ink">
                  Reason for the correction
                </label>
                <textarea
                  id="merchant-reason"
                  value={reason}
                  onChange={(changed) => setReason(changed.target.value)}
                  maxLength={REASON_MAX}
                  rows={3}
                  className="min-h-[88px] resize-y rounded-[12px] border border-line-input bg-white px-3.5 py-3 text-base text-ink"
                />
                <span className="text-right text-[13px] text-text-subtle">
                  {reason.length}/{REASON_MAX}
                </span>
              </div>
            )}
            {record.isError && <InlineError className="text-sm">{describeError(record.error)}</InlineError>}
            <div className="flex flex-col gap-2.5 sm:flex-row">
              {record.isPending ? (
                <button type="button" disabled aria-busy="true" className={busyButtonClass}>
                  <Spinner />
                  Recording…
                </button>
              ) : (
                <button
                  type="button"
                  disabled={!ready}
                  onClick={() => (carton ? setConfirming(true) : send())}
                  className={`flex-1 ${buttonClass("primary", "lg")}`}
                >
                  Record
                </button>
              )}
              <button type="button" onClick={restart} className={`flex-1 ${buttonClass("secondary", "lg")}`}>
                Look up another code
              </button>
            </div>
          </Card>
        )}
      </div>
    );
  }

  const normalised = normaliseCode(typed);
  return (
    <Card variant="workspace" aria-label="Find a code" className="flex flex-col gap-4">
      <h2 className="m-0 font-heading text-lg font-semibold text-ink">Find a pack or carton</h2>
      <button type="button" onClick={() => setScanning(true)} disabled={lookup.isPending} className={buttonClass("primary", "xl")}>
        Open the camera
      </button>
      <form onSubmit={submitTyped} aria-label="Type code" className="flex flex-col gap-2">
        <label htmlFor="merchant-code" className="font-semibold text-ink">
          Or type the code printed under the QR
        </label>
        <input
          id="merchant-code"
          value={typed}
          onChange={(changed) => setTyped(changed.target.value)}
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          maxLength={40}
          placeholder="7Q2M 8KD3 XH4N …"
          className={`${codeInputClass("default", lookup.isPending)} uppercase`}
        />
        {normalised && (
          <p className="m-0 text-sm text-text-subtle">
            Reading: <span className="font-mono">{groupCode(normalised)}</span>
          </p>
        )}
        {lookup.isError && <InlineError className="text-sm">{describeError(lookup.error)}</InlineError>}
        {lookup.isPending ? (
          <button type="submit" disabled aria-busy="true" className={busyButtonClass}>
            <Spinner />
            Looking up…
          </button>
        ) : (
          <button type="submit" disabled={!normalised} className={buttonClass("secondary", "md")}>
            Look up code
          </button>
        )}
      </form>
    </Card>
  );
}
