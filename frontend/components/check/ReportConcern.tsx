"use client";

import { useState, type FormEvent } from "react";
import { describeError } from "@/lib/api";
import { InlineError } from "@/components/ui/Panels";
import { Spinner } from "@/components/ui/Spinner";
import { busyButtonClass, buttonClass, cardTitleClass, helpTextClass } from "@/lib/ui";
import { concernTypes, useReportConcern, type CheckResult, type ConcernType } from "@/lib/check";

const MAX_LENGTH = 1000;

function defaultConcern(result: CheckResult): ConcernType {
  if (result === "RECOGNISED_PREVIOUSLY_SOLD") return "PREVIOUSLY_SOLD";
  if (result === "SUSPICIOUS_ACTIVITY" || result === "INVALID_IDENTITY") return "SUSPICIOUS_RESULT";
  return "OTHER";
}

/** Flag icon of the board's report button (Result.dc.html). */
function FlagIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M5 21V4M5 4h11l-2 4 2 4H5" />
    </svg>
  );
}

type Props = {
  code: string | null;
  result: CheckResult;
  simulatedCity: string | null;
  /** Red outline button on a red result (ResultMismatch). */
  danger?: boolean;
};

/**
 * Anonymous report to the manufacturer and FoodLens admins (D120). No contact field.
 * Inline in the result; cards, radio cards and fields follow Report.dc.html.
 */
export function ReportConcern({ code, result, simulatedCity, danger = false }: Props) {
  const [open, setOpen] = useState(false);
  const [concern, setConcern] = useState<ConcernType>(() => defaultConcern(result));
  const [description, setDescription] = useState("");
  const report = useReportConcern();

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!description.trim()) return;
    report.mutate({ code, concern_type: concern, description: description.trim(), simulated_city: simulatedCity });
  }

  if (report.isSuccess) {
    return (
      // Confirmation card (Report.dc.html, done state).
      <section
        aria-label="Report a concern"
        className="rounded-[18px] border border-line bg-white px-5 py-[26px] text-center"
      >
        <span
          aria-hidden="true"
          className="inline-flex size-16 items-center justify-center rounded-full bg-brand-tint"
        >
          <svg
            width="32"
            height="32"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#1B7A45"
            strokeWidth="2.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M5 12.5l4.5 4.5L19 7.5" />
          </svg>
        </span>
        <p role="status" className="mt-3.5 mb-0 text-text-muted">
          {report.data.message}
        </p>
      </section>
    );
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={`w-full ${buttonClass(danger ? "danger" : "secondary", "md")}`}
      >
        <FlagIcon />
        Report a concern
      </button>
    );
  }

  return (
    // Report card (Report.dc.html: 18px padding, 16px radius).
    <section aria-label="Report a concern" className="rounded-[16px] border border-line bg-white p-[18px]">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <h3 className={`${cardTitleClass} m-0`}>Report a concern</h3>
        <div className="flex items-start gap-2.5 rounded-[12px] bg-brand-tint px-3.5 py-3">
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#1B7A45"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
            className="mt-0.5 flex-none"
          >
            <rect x="5" y="11" width="14" height="10" rx="2" />
            <path d="M8 11V8a4 4 0 0 1 8 0v3" />
          </svg>
          <p className={`${helpTextClass} m-0`}>
            Goes to the manufacturer and FoodLens admins. It is anonymous: don&apos;t include your name or
            phone number.
          </p>
        </div>
        <fieldset className="m-0 flex min-w-0 flex-col gap-2 border-0 p-0">
          <legend className="float-left mb-1.5 w-full p-0 font-semibold text-ink">What is the concern?</legend>
          {concernTypes.map((type) => {
            const selected = concern === type.value;
            return (
              <label
                key={type.value}
                className={`flex cursor-pointer items-start gap-3 rounded-[12px] px-3.5 py-3 ${
                  selected ? "border-2 border-brand bg-[#F4FAF6]" : "border border-line bg-white"
                }`}
              >
                <input
                  type="radio"
                  name="concern"
                  value={type.value}
                  checked={selected}
                  onChange={() => setConcern(type.value)}
                  className="mt-px size-[22px] flex-none accent-brand"
                />
                <span className="font-semibold">{type.label}</span>
              </label>
            );
          })}
        </fieldset>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="concern-description" className="font-semibold text-ink">
            Tell us what happened
          </label>
          <textarea
            id="concern-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            maxLength={MAX_LENGTH}
            required
            rows={5}
            aria-describedby="concern-description-count"
            className="mt-1 min-h-[120px] resize-y rounded-[12px] border border-line-input bg-white px-3.5 py-3 text-base text-ink"
          />
          <span id="concern-description-count" className="text-right text-[13px] text-[#4B4F5C]">
            {description.length}/{MAX_LENGTH}
          </span>
        </div>
        {report.isError && <InlineError className="text-sm">{describeError(report.error)}</InlineError>}
        {report.isPending ? (
          <button type="submit" disabled aria-busy="true" className={busyButtonClass}>
            <Spinner />
            Sending…
          </button>
        ) : (
          <button type="submit" disabled={!description.trim()} className={buttonClass("primary", "xl")}>
            Send report
          </button>
        )}
      </form>
    </section>
  );
}
