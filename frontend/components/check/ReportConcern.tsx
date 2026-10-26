"use client";

import { useState, type FormEvent } from "react";
import { describeError } from "@/lib/api";
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
      <section aria-label="Report a concern" className="rounded-xl border border-zinc-300 p-4 dark:border-zinc-700">
        <p role="status" className="text-sm">
          {report.data.message}
        </p>
      </section>
    );
  }

  return (
    <section aria-label="Report a concern" className="rounded-xl border border-zinc-300 p-4 dark:border-zinc-700">
      {!open ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="min-h-12 w-full rounded-lg border border-zinc-900 px-4 text-base font-semibold dark:border-zinc-100"
        >
          Report a concern
        </button>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-3">
          <h3 className="font-semibold">Report a concern</h3>
          <p className="text-xs text-zinc-600 dark:text-zinc-400">
            Goes to the manufacturer and FoodLens admins. It is anonymous: don&apos;t include your name or
            phone number.
          </p>
          <label className="flex flex-col gap-1 text-sm font-medium">
            What is the concern?
            <select
              value={concern}
              onChange={(event) => setConcern(event.target.value as ConcernType)}
              className="min-h-12 rounded-lg border border-zinc-400 bg-transparent px-3 text-base"
            >
              {concernTypes.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </label>
          <div className="flex flex-col gap-1">
            <label htmlFor="concern-description" className="text-sm font-medium">
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
              className="rounded-lg border border-zinc-400 bg-transparent p-3 text-base"
            />
            <span id="concern-description-count" className="text-xs text-zinc-600 dark:text-zinc-400">
              {description.length}/{MAX_LENGTH}
            </span>
          </div>
          {report.isError && (
            <p role="alert" className="text-sm text-red-700 dark:text-red-400">
              {describeError(report.error)}
            </p>
          )}
          <button
            type="submit"
            disabled={report.isPending || !description.trim()}
            className="min-h-12 rounded-lg bg-zinc-900 px-4 text-base font-semibold text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900"
          >
            {report.isPending ? "Sending…" : "Send report"}
          </button>
        </form>
      )}
    </section>
  );
}
