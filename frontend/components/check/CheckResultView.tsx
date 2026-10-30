"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
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

const CHECK_ANOTHER = "Check another pack";
const CHECK_ANOTHER_CLASS = `flex-[1_1_260px] ${buttonClass("primary", "lg")}`;

type Props = {
  result: CheckResponse;
  /** The code that was checked, kept in memory only so a report can name it. */
  code: string | null;
  simulatedCity?: string | null;
  /** "Check another pack" in the bottom bar: a button (in /check) or a link (from /p). */
  onCheckAnother?: () => void;
  checkAnotherHref?: string;
  /** Extra content at the end of the details column, such as the demo city picker. */
  children?: ReactNode;
};

/**
 * One check result (D115, D141). Recorded facts and possible patterns are labelled apart, the
 * demo banner is on every result, and only the last 4 characters of the code are shown.
 * Layout: Result.dc.html (status column, details column, sticky bottom bar).
 */
export function CheckResultView({ result, code, simulatedCity, onCheckAnother, checkAnotherHref, children }: Props) {
  const [noted, setNoted] = useState(false);
  const { tone, label } = toneFor(result);
  const { product, batch } = result;
  const recalls = result.notices.filter((notice) => notice.kind === "RECALL");
  const messages = result.notices.filter((notice) => notice.kind !== "RECALL");

  return (
    <article aria-labelledby="check-result-title" className="flex flex-1 flex-col">
      <DemoDataBanner />

      <div className="mx-auto box-border flex w-full max-w-[1040px] flex-1 flex-wrap items-start gap-4 px-4 py-5">
        {/* Status column */}
        <div className="flex min-w-0 flex-[1_1_340px] flex-col gap-3">
          <StatusCard tone={tone} label={label} title={result.title} titleId="check-result-title">
            {result.code_last4 && <p className="m-0 font-mono text-sm">Code ending {result.code_last4}</p>}
            <p className="mt-1.5 mb-0">{result.message}</p>
            {result.tip && <p className={`mt-3 mb-0 font-semibold ${noteClass}`}>{result.tip}</p>}
            {result.advice && <p className="mt-3 mb-0 text-sm">{result.advice}</p>}
          </StatusCard>

          {recalls.map((notice) => (
            // A recall is a solid alert card directly under the status card (design/README.md).
            <section
              key={`${notice.posted_at}-${notice.title}`}
              aria-label="Recall"
              className="rounded-[16px] bg-alert-bg px-5 pt-[18px] pb-5"
            >
              <p className="m-0 text-[13px] font-semibold text-alert">{notice.label}</p>
              <h3 className="mt-1 mb-0 font-heading text-base font-semibold text-ink">Recall: {notice.title}</h3>
              <p className="mt-1 mb-0.5 whitespace-pre-line text-[15px] text-text">{notice.message}</p>
              <p className="m-0 text-[13px] text-[#4B4F5C]">Posted {formatInstant(notice.posted_at)}</p>
            </section>
          ))}

          {result.can_note_purchase &&
            (noted ? (
              // Note row under the status card (Result.dc.html "Batch note").
              <p
                role="status"
                className="m-0 rounded-[12px] border border-line bg-white px-3.5 py-3 text-sm text-text"
              >
                {PURCHASE_NOTE}
              </p>
            ) : (
              <button type="button" onClick={() => setNoted(true)} className={`w-full ${buttonClass("secondary", "md")}`}>
                I&apos;ve bought this
              </button>
            ))}

          {result.warnings.length > 0 && (
            <Card aria-label="Warnings">
              <h3 className={`${cardTitleClass} mt-0 mb-2`}>Warnings</h3>
              <ul className="m-0 flex list-disc flex-col gap-2 pl-5 text-[15px] text-text">
                {result.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </Card>
          )}
        </div>

        {/* Details column */}
        <div className="flex min-w-0 flex-[1.3_1_380px] flex-col gap-3">
          {result.possible_patterns.length > 0 && (
            // Takes the place of the board's compare panel, with its red border (ResultMismatch).
            <section aria-label="Possible patterns" className="rounded-[16px] border-2 border-bad-line bg-white p-5">
              <h3 className={`${cardTitleClass} mt-0 mb-1`}>Possible patterns</h3>
              <p className="mt-0 mb-3.5 text-[13px] text-[#4B4F5C]">
                Patterns FoodLens noticed in the records. They are signals, not findings about this pack.
              </p>
              <ul className="m-0 flex list-disc flex-col gap-2 pl-5 text-[15px] text-text">
                {result.possible_patterns.map((pattern) => (
                  <li key={pattern}>{pattern}</li>
                ))}
              </ul>
            </section>
          )}

          {product && (
            <Card aria-label="Product">
              <h3 className={`${cardTitleClass} mt-0 mb-3`}>
                {product.name}
                {product.size ? <span className="font-normal"> · {product.size}</span> : null}
              </h3>
              <dl className={`${detailListClass} m-0`}>
                <dt className={detailTermClass}>Brand</dt>
                <dd className={`${detailValueClass} m-0`}>{product.brand}</dd>
                <dt className={detailTermClass}>Manufacturer</dt>
                <dd className={`${detailValueClass} m-0`}>{product.manufacturer_name}</dd>
                {batch && (
                  <>
                    <dt className={detailTermClass}>Batch</dt>
                    <dd className={`${detailValueClass} m-0 font-mono`}>{batch.batch_number}</dd>
                    <dt className={detailTermClass}>Expiry</dt>
                    <dd className={`${detailValueClass} m-0${batch.expired ? " text-warn" : ""}`}>
                      {formatDate(batch.expiry_date)}
                      {batch.expired ? " (passed)" : ""}
                    </dd>
                  </>
                )}
                {product.registration_number && (
                  <>
                    <dt className={detailTermClass}>NAFDAC number (as printed)</dt>
                    <dd className={`${detailValueClass} m-0`}>
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
              <h3 className={`${cardTitleClass} mt-0 mb-1`}>Recorded facts</h3>
              <p className={`${helpTextClass} m-0`}>What companies have recorded for this code, oldest first.</p>
              <ol className="mt-3 mb-0 flex flex-col gap-2 border-l-2 border-line pl-4 text-[15px] text-text">
                {result.recorded_facts.map((fact, index) => (
                  <li key={`${index}-${fact}`}>{fact}</li>
                ))}
              </ol>
            </Card>
          )}

          {messages.map((notice) => (
            // Company message card (Result.dc.html).
            <section
              key={`${notice.posted_at}-${notice.title}`}
              aria-label="Company notice"
              className="rounded-[16px] border border-dashed border-[#B9BCC6] bg-white px-5 pt-[18px] pb-5"
            >
              <p className="m-0 text-[13px] text-[#4B4F5C]">{notice.label}</p>
              <h3 className="mt-3 mb-0 border-t border-divider pt-3 text-[15px] font-bold text-ink">{notice.title}</h3>
              <p className="mt-1 mb-0.5 whitespace-pre-line text-[15px] text-text">{notice.message}</p>
              <p className="m-0 text-[13px] text-[#4B4F5C]">Posted {formatInstant(notice.posted_at)}</p>
            </section>
          ))}

          {result.can_report && (
            <ReportConcern
              code={code}
              result={result.result}
              simulatedCity={simulatedCity ?? null}
              danger={tone === "bad"}
            />
          )}

          <Card aria-label="What a check shows">
            <h3 className={`${cardTitleClass} mt-0 mb-1`}>What this check can and cannot show</h3>
            <p className="m-0 text-[15px] text-text">{result.copy_help}</p>
            <p className={`mt-3 mb-0 ${noteClass}`}>{result.disclaimer}</p>
          </Card>

          {children}
        </div>
      </div>

      {(onCheckAnother || checkAnotherHref) && (
        // Sticky bottom bar (Result.dc.html).
        <div className="sticky bottom-0 border-t border-line bg-white">
          <div className="mx-auto box-border flex max-w-[1040px] flex-wrap items-center gap-2.5 px-4 pt-3 pb-5">
            {checkAnotherHref ? (
              <Link href={checkAnotherHref} className={CHECK_ANOTHER_CLASS}>
                {CHECK_ANOTHER}
              </Link>
            ) : (
              <button type="button" onClick={onCheckAnother} className={CHECK_ANOTHER_CLASS}>
                {CHECK_ANOTHER}
              </button>
            )}
          </div>
        </div>
      )}
    </article>
  );
}
