"use client";

import { useState } from "react";
import { DemoDataBanner } from "@/components/DemoDataBanner";
import { Card } from "@/components/ui/Card";
import { StatusCard, type StatusTone } from "@/components/ui/StatusCard";
import type { CheckResponse, CheckResult } from "@/lib/check";
import { formatDate } from "@/lib/format";
import {
  buttonClass,
  cardTitleClass,
  detailListClass,
  detailTermClass,
  detailValueClass,
  helpTextClass,
  noteClass,
} from "@/lib/ui";
import { ReportConcern } from "./ReportConcern";

const PURCHASE_NOTE =
  "No sale recorded yet. Some shops don't record sales on FoodLens yet. This isn't a warning by itself.";

type Tone = { tone: StatusTone; label: string };

const NEUTRAL: Tone = { tone: "neutral", label: "Not found" };

// Tones follow the result mapping in design/README.md.
const TONES: Record<CheckResult, Tone> = {
  RECOGNISED_NOT_SOLD: { tone: "ok", label: "Recorded" },
  RECOGNISED_JUST_SOLD: { tone: "ok", label: "Recorded sale" },
  RECOGNISED_PREVIOUSLY_SOLD: { tone: "warn", label: "Check with the seller" },
  BATCH_OR_PRODUCT_WARNING: { tone: "alert", label: "Recall" },
  SUSPICIOUS_ACTIVITY: { tone: "bad", label: "Warning" },
  INVALID_IDENTITY: { tone: "bad", label: "Not recognised" },
  CARTON_CODE: { tone: "info", label: "Carton" },
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
  const { tone, label } = toneFor(result);
  const { product, batch } = result;

  return (
    <article aria-labelledby="check-result-title" className="flex flex-col gap-3">
      <DemoDataBanner />

      <StatusCard tone={tone} label={label} title={result.title} titleId="check-result-title">
        {result.code_last4 && (
          <p className="font-mono text-sm">
            Code ending {result.code_last4}
          </p>
        )}
        <p className="mt-1.5">{result.message}</p>
        {result.tip && <p className={`mt-3 font-semibold ${noteClass}`}>{result.tip}</p>}
        {result.advice && <p className="mt-3 text-sm">{result.advice}</p>}
      </StatusCard>

      {result.warnings.length > 0 && (
        <Card aria-label="Warnings">
          <h3 className={cardTitleClass}>Warnings</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-[15px] text-text">
            {result.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </Card>
      )}

      {result.possible_patterns.length > 0 && (
        // Takes the place of the board's compare panel, with its red border (ResultMismatch).
        <section aria-label="Possible patterns" className="rounded-[16px] border-2 border-bad-line bg-white p-5">
          <h3 className={cardTitleClass}>Possible patterns</h3>
          <p className={helpTextClass}>
            Patterns FoodLens noticed in the records. They are signals, not findings about this pack.
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-[15px] text-text">
            {result.possible_patterns.map((pattern) => (
              <li key={pattern}>{pattern}</li>
            ))}
          </ul>
        </section>
      )}

      {result.can_note_purchase && (
        <Card>
          {noted ? (
            <p role="status" className="text-sm text-text">
              {PURCHASE_NOTE}
            </p>
          ) : (
            <button type="button" onClick={() => setNoted(true)} className={`w-full ${buttonClass("secondary", "md")}`}>
              I&apos;ve bought this
            </button>
          )}
        </Card>
      )}

      {product && (
        <Card aria-label="Product">
          <h3 className={`${cardTitleClass} mb-3`}>
            {product.name}
            {product.size ? <span className="font-normal"> · {product.size}</span> : null}
          </h3>
          <dl className={detailListClass}>
            <dt className={detailTermClass}>Brand</dt>
            <dd className={detailValueClass}>{product.brand}</dd>
            <dt className={detailTermClass}>Manufacturer</dt>
            <dd className={detailValueClass}>{product.manufacturer_name}</dd>
            {batch && (
              <>
                <dt className={detailTermClass}>Batch</dt>
                <dd className={`${detailValueClass} font-mono`}>{batch.batch_number}</dd>
                <dt className={detailTermClass}>Expiry</dt>
                <dd className={`${detailValueClass}${batch.expired ? " text-warn" : ""}`}>
                  {formatDate(batch.expiry_date)}
                  {batch.expired ? " (passed)" : ""}
                </dd>
              </>
            )}
            {product.registration_number && (
              <>
                <dt className={detailTermClass}>NAFDAC number (as printed)</dt>
                <dd className={detailValueClass}>
                  <span className="font-mono">{product.registration_number}</span>
                  <span className="block text-xs font-normal text-text-subtle">
                    Information from the manufacturer. FoodLens does not check it with NAFDAC.
                  </span>
                </dd>
              </>
            )}
          </dl>
        </Card>
      )}

      {result.recorded_facts.length > 0 && (
        <Card aria-label="Recorded facts">
          <h3 className={cardTitleClass}>Recorded facts</h3>
          <p className={helpTextClass}>What companies have recorded for this code, oldest first.</p>
          <ol className="mt-3 space-y-2 border-l-2 border-line pl-4 text-[15px] text-text">
            {result.recorded_facts.map((fact, index) => (
              <li key={`${index}-${fact}`}>{fact}</li>
            ))}
          </ol>
        </Card>
      )}

      {result.notices.map((notice) =>
        notice.kind === "RECALL" ? (
          // A recall is a solid alert card, not the dashed company-message card (design/README.md).
          <section
            key={`${notice.posted_at}-${notice.title}`}
            aria-label="Recall"
            className="rounded-[16px] bg-alert-bg px-5 pt-[18px] pb-5"
          >
            <p className="text-[13px] font-semibold text-alert">{notice.label}</p>
            <h3 className="mt-1 font-heading text-base font-semibold text-ink">Recall: {notice.title}</h3>
            <p className="mt-1 whitespace-pre-line text-[15px] text-text">{notice.message}</p>
            <p className="mt-0.5 text-[13px] text-[#4B4F5C]">Posted {formatInstant(notice.posted_at)}</p>
          </section>
        ) : (
          // Company message card (Result.dc.html).
          <section
            key={`${notice.posted_at}-${notice.title}`}
            aria-label="Company notice"
            className="rounded-[16px] border border-dashed border-[#B9BCC6] bg-white px-5 pt-[18px] pb-5"
          >
            <p className="text-[13px] text-[#4B4F5C]">{notice.label}</p>
            <h3 className="mt-1 text-[15px] font-bold text-ink">{notice.title}</h3>
            <p className="mt-1 whitespace-pre-line text-[15px] text-text">{notice.message}</p>
            <p className="mt-0.5 text-[13px] text-[#4B4F5C]">Posted {formatInstant(notice.posted_at)}</p>
          </section>
        ),
      )}

      {result.can_report && (
        <ReportConcern code={code} result={result.result} simulatedCity={simulatedCity ?? null} />
      )}

      <Card aria-label="What a check shows">
        <h3 className={cardTitleClass}>What this check can and cannot show</h3>
        <p className="mt-1 text-[15px] text-text">{result.copy_help}</p>
        <p className={`mt-3 ${noteClass}`}>{result.disclaimer}</p>
      </Card>

      {onCheckAnother && (
        <button type="button" onClick={onCheckAnother} className={`w-full ${buttonClass("primary", "lg")}`}>
          Check another pack
        </button>
      )}
    </article>
  );
}
