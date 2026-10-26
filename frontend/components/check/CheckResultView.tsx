"use client";

import { useState } from "react";
import { DemoDataBanner } from "@/components/DemoDataBanner";
import type { CheckResponse, CheckResult } from "@/lib/check";
import { formatDate } from "@/lib/format";
import { ReportConcern } from "./ReportConcern";

const PURCHASE_NOTE =
  "No sale recorded yet. Some shops don't record sales on FoodLens yet. This isn't a warning by itself.";

type Tone = { band: string; badge: string; label: string };

const NEUTRAL: Tone = {
  band: "border-zinc-400 bg-zinc-50 dark:bg-zinc-900",
  badge: "bg-zinc-700 text-white",
  label: "Not found",
};

const TONES: Record<CheckResult, Tone> = {
  RECOGNISED_NOT_SOLD: {
    band: "border-teal-600 bg-teal-50 dark:bg-teal-950/40",
    badge: "bg-teal-700 text-white",
    label: "Recorded",
  },
  RECOGNISED_JUST_SOLD: {
    band: "border-teal-600 bg-teal-50 dark:bg-teal-950/40",
    badge: "bg-teal-700 text-white",
    label: "Recorded sale",
  },
  RECOGNISED_PREVIOUSLY_SOLD: {
    band: "border-amber-500 bg-amber-50 dark:bg-amber-950/40",
    badge: "bg-amber-400 text-black",
    label: "Check with the seller",
  },
  BATCH_OR_PRODUCT_WARNING: {
    band: "border-orange-600 bg-orange-50 dark:bg-orange-950/40",
    badge: "bg-orange-600 text-white",
    label: "Recall",
  },
  SUSPICIOUS_ACTIVITY: {
    band: "border-red-600 bg-red-50 dark:bg-red-950/40",
    badge: "bg-red-700 text-white",
    label: "Warning",
  },
  INVALID_IDENTITY: {
    band: "border-red-600 bg-red-50 dark:bg-red-950/40",
    badge: "bg-red-700 text-white",
    label: "Not recognised",
  },
  CARTON_CODE: {
    band: "border-zinc-500 bg-zinc-50 dark:bg-zinc-900",
    badge: "bg-zinc-700 text-white",
    label: "Carton",
  },
};

function toneFor(result: CheckResponse): Tone {
  // A typed code that is not found is most often a typing slip: neutral, not alarming (D138).
  if (result.result === "INVALID_IDENTITY" && result.identifier_type === "TYPED") return NEUTRAL;
  return TONES[result.result];
}

function formatInstant(value: string): string {
  return new Date(value).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Africa/Lagos",
  });
}

type Props = {
  result: CheckResponse;
  /** The code that was checked, kept in memory only so a report can name it. */
  code: string | null;
  simulatedCity?: string | null;
  onCheckAnother?: () => void;
};

/**
 * One check result (D115, D141). Recorded facts and possible patterns are labelled apart, the
 * demo banner is on every result, and only the last 4 characters of the code are shown.
 */
export function CheckResultView({ result, code, simulatedCity, onCheckAnother }: Props) {
  const [noted, setNoted] = useState(false);
  const tone = toneFor(result);
  const { product, batch } = result;

  return (
    <article aria-labelledby="check-result-title" className="flex flex-col gap-4">
      <DemoDataBanner />

      <section className={`rounded-xl border-l-8 p-4 ${tone.band}`}>
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold uppercase tracking-wide ${tone.badge}`}>
            {tone.label}
          </span>
          {result.code_last4 && (
            <span className="font-mono text-sm text-zinc-700 dark:text-zinc-300">
              Code ending {result.code_last4}
            </span>
          )}
        </div>
        <h2 id="check-result-title" className="mt-2 text-2xl font-bold leading-tight">
          {result.title}
        </h2>
        <p className="mt-2 text-base">{result.message}</p>
        {result.tip && <p className="mt-3 rounded-md bg-white/70 p-3 text-sm font-medium dark:bg-black/30">{result.tip}</p>}
        {result.advice && <p className="mt-3 text-sm">{result.advice}</p>}
      </section>

      {result.warnings.length > 0 && (
        <section aria-label="Warnings" className="rounded-xl border border-orange-500 p-4">
          <h3 className="font-semibold">Warnings</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            {result.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </section>
      )}

      {result.possible_patterns.length > 0 && (
        <section aria-label="Possible patterns" className="rounded-xl border border-red-500 p-4">
          <h3 className="font-semibold">Possible patterns</h3>
          <p className="text-xs text-zinc-600 dark:text-zinc-400">
            Patterns FoodLens noticed in the records. They are signals, not findings about this pack.
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            {result.possible_patterns.map((pattern) => (
              <li key={pattern}>{pattern}</li>
            ))}
          </ul>
        </section>
      )}

      {result.can_note_purchase && (
        <section className="rounded-xl border border-zinc-300 p-4 dark:border-zinc-700">
          {noted ? (
            <p role="status" className="text-sm">
              {PURCHASE_NOTE}
            </p>
          ) : (
            <button
              type="button"
              onClick={() => setNoted(true)}
              className="min-h-12 w-full rounded-lg border border-zinc-900 px-4 text-base font-semibold dark:border-zinc-100"
            >
              I&apos;ve bought this
            </button>
          )}
        </section>
      )}

      {product && (
        <section aria-label="Product" className="rounded-xl border border-zinc-300 p-4 dark:border-zinc-700">
          <h3 className="text-lg font-semibold">
            {product.name}
            {product.size ? <span className="font-normal"> · {product.size}</span> : null}
          </h3>
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            <dt className="text-zinc-600 dark:text-zinc-400">Brand</dt>
            <dd>{product.brand}</dd>
            <dt className="text-zinc-600 dark:text-zinc-400">Manufacturer</dt>
            <dd>{product.manufacturer_name}</dd>
            {batch && (
              <>
                <dt className="text-zinc-600 dark:text-zinc-400">Batch</dt>
                <dd>{batch.batch_number}</dd>
                <dt className="text-zinc-600 dark:text-zinc-400">Expiry</dt>
                <dd className={batch.expired ? "font-semibold text-orange-700 dark:text-orange-400" : ""}>
                  {formatDate(batch.expiry_date)}
                  {batch.expired ? " (passed)" : ""}
                </dd>
              </>
            )}
            {product.registration_number && (
              <>
                <dt className="text-zinc-600 dark:text-zinc-400">NAFDAC number (as printed)</dt>
                <dd>
                  {product.registration_number}
                  <span className="block text-xs text-zinc-600 dark:text-zinc-400">
                    Information from the manufacturer. FoodLens does not check it with NAFDAC.
                  </span>
                </dd>
              </>
            )}
          </dl>
        </section>
      )}

      {result.recorded_facts.length > 0 && (
        <section aria-label="Recorded facts" className="rounded-xl border border-zinc-300 p-4 dark:border-zinc-700">
          <h3 className="font-semibold">Recorded facts</h3>
          <p className="text-xs text-zinc-600 dark:text-zinc-400">
            What companies have recorded for this code, oldest first.
          </p>
          <ol className="mt-2 space-y-2 border-l-2 border-zinc-300 pl-4 text-sm dark:border-zinc-700">
            {result.recorded_facts.map((fact, index) => (
              <li key={`${index}-${fact}`}>{fact}</li>
            ))}
          </ol>
        </section>
      )}

      {result.notices.map((notice) => (
        <section
          key={`${notice.posted_at}-${notice.title}`}
          aria-label={notice.kind === "RECALL" ? "Recall" : "Company notice"}
          className="rounded-xl border border-zinc-300 p-4 dark:border-zinc-700"
        >
          <p className="text-xs font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
            {notice.label}
          </p>
          <h3 className="mt-1 font-semibold">
            {notice.kind === "RECALL" ? "Recall: " : ""}
            {notice.title}
          </h3>
          <p className="mt-1 whitespace-pre-line text-sm">{notice.message}</p>
          <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">Posted {formatInstant(notice.posted_at)}</p>
        </section>
      ))}

      {result.can_report && (
        <ReportConcern code={code} result={result.result} simulatedCity={simulatedCity ?? null} />
      )}

      <section aria-label="What a check shows" className="rounded-xl bg-zinc-100 p-4 text-sm dark:bg-zinc-900">
        <h3 className="font-semibold">What this check can and cannot show</h3>
        <p className="mt-1">{result.copy_help}</p>
        <p className="mt-2 text-xs text-zinc-700 dark:text-zinc-300">{result.disclaimer}</p>
      </section>

      {onCheckAnother && (
        <button
          type="button"
          onClick={onCheckAnother}
          className="min-h-12 w-full rounded-lg bg-zinc-900 px-4 text-base font-semibold text-white dark:bg-zinc-100 dark:text-zinc-900"
        >
          Check another pack
        </button>
      )}
    </article>
  );
}
