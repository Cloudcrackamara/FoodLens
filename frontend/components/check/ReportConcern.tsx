"use client";

import { useState, type FormEvent } from "react";
import { describeError } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { InlineError } from "@/components/ui/Panels";
import { buttonClass, cardTitleClass, helpTextClass, inputClass, textareaClass } from "@/lib/ui";
import { concernTypes, useReportConcern, type CheckResult, type ConcernType } from "@/lib/check";

const MAX_LENGTH = 1000;

function defaultConcern(result: CheckResult): ConcernType {
  if (result === "RECOGNISED_PREVIOUSLY_SOLD") return "PREVIOUSLY_SOLD";
  if (result === "SUSPICIOUS_ACTIVITY" || result === "INVALID_IDENTITY") return "SUSPICIOUS_RESULT";
  return "OTHER";
}

type Props = { code: string | null; result: CheckResult; simulatedCity: string | null };

/** Anonymous report to the manufacturer and FoodLens admins (D120). No contact field. */
export function ReportConcern({ code, result, simulatedCity }: Props) {
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
      <Card aria-label="Report a concern">
        <p role="status" className="text-sm text-text">
          {report.data.message}
        </p>
      </Card>
    );
  }

  return (
    <Card aria-label="Report a concern">
      {!open ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className={`w-full ${buttonClass("secondary", "md")}`}
        >
          Report a concern
        </button>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-3">
          <h3 className={cardTitleClass}>Report a concern</h3>
          <p className={helpTextClass}>
            Goes to the manufacturer and FoodLens admins. It is anonymous: don&apos;t include your name or
            phone number.
          </p>
          <label className="flex flex-col gap-1 text-sm font-semibold text-ink">
            What is the concern?
            <select
              value={concern}
              onChange={(event) => setConcern(event.target.value as ConcernType)}
              className={`${inputClass} font-normal`}
            >
              {concernTypes.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </label>
          <div className="flex flex-col gap-1">
            <label htmlFor="concern-description" className="text-sm font-semibold text-ink">
              Tell us what happened
            </label>
            <textarea
              id="concern-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              maxLength={MAX_LENGTH}
              required
              rows={4}
              aria-describedby="concern-description-count"
              className={textareaClass}
            />
            <span id="concern-description-count" className="text-xs text-text-subtle">
              {description.length}/{MAX_LENGTH}
            </span>
          </div>
          {report.isError && (
            <InlineError className="text-sm">{describeError(report.error)}</InlineError>
          )}
          <button
            type="submit"
            disabled={report.isPending || !description.trim()}
            className={buttonClass("primary", "md")}
          >
            {report.isPending ? "Sending…" : "Send report"}
          </button>
        </form>
      )}
    </Card>
  );
}
