"use client";

import { useState } from "react";
import {
  ArrowLeftRight,
  CalendarX2,
  CircleHelp,
  Megaphone,
  ScrollText,
  SearchX,
  X,
  type LucideIcon,
} from "lucide-react";
import { DemoDataBanner } from "@/components/DemoDataBanner";
import { Button } from "@/components/ui/button";
import { formatDate, registerStatusLabels, type LookupResponse } from "@/lib/lookup";
import { cn } from "@/lib/utils";

const mismatchExplanations = {
  different_registration_number:
    "FoodLens lists this batch under a different registration number.",
  registered_names_differ:
    "The register record names a different product or company than the one this batch belongs to.",
} as const;

/**
 * Result tones (D104): ink for a register match, amber for anything to look at again, grey when
 * the input was not enough. Never green or red, and never colour alone: each has an icon and
 * the title says what happened.
 */
const tones: Record<LookupResponse["result"], { icon: LucideIcon; stripe: string; badge: string }> = {
  REGISTERED_ACTIVE: { icon: ScrollText, stripe: "bg-primary", badge: "bg-secondary text-primary" },
  REGISTRATION_NOT_FOUND: { icon: SearchX, stripe: "bg-notice", badge: "bg-notice-soft text-notice" },
  REGISTRATION_EXPIRED_OR_INACTIVE: {
    icon: CalendarX2,
    stripe: "bg-notice",
    badge: "bg-notice-soft text-notice",
  },
  REGISTRATION_MISMATCH: { icon: ArrowLeftRight, stripe: "bg-notice", badge: "bg-notice-soft text-notice" },
  INSUFFICIENT_OR_AMBIGUOUS: { icon: CircleHelp, stripe: "bg-muted-foreground", badge: "bg-muted text-muted-foreground" },
};

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col py-1.5 sm:flex-row sm:gap-3">
      <dt className="text-sm text-muted-foreground sm:w-44 sm:shrink-0">{label}</dt>
      <dd className="break-words font-medium">{value}</dd>
    </div>
  );
}

function CompanyMessages({ announcements }: { announcements: LookupResponse["announcements"] }) {
  const [open, setOpen] = useState(true);
  if (!open || announcements.length === 0) return null;
  return (
    <aside
      aria-label="Messages from the company"
      className="flex flex-col gap-3 rounded-xl border-2 border-dashed border-input bg-muted p-4"
    >
      {announcements.map((item) => (
        <div key={`${item.posted_at}-${item.title}`} className="flex gap-3">
          <Megaphone aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{item.label}</p>
            <p className="font-semibold">{item.title}</p>
            <p>{item.message}</p>
            <p className="text-xs text-muted-foreground">Posted {formatDate(item.posted_at.slice(0, 10))}</p>
          </div>
        </div>
      ))}
      <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)} className="self-end">
        <X aria-hidden="true" />
        Close
      </Button>
    </aside>
  );
}

/**
 * Lookup result. A result describes a record in a simulated, fictional register, never whether
 * food is fit to eat or whether the pack is the original. The demo banner is repeated inside
 * every result.
 */
export function LookupResultView({ response }: { response: LookupResponse }) {
  const { register_record: record, product, batch, mismatch, warnings } = response;
  const tone = tones[response.result];
  const Icon = tone.icon;

  return (
    <section
      aria-labelledby="lookup-result-title"
      className="relative flex flex-col overflow-hidden rounded-xl border border-border bg-card"
    >
      <DemoDataBanner />
      <div aria-hidden="true" className={cn("h-1.5 w-full", tone.stripe)} />
      <div className="flex flex-col gap-5 p-4 sm:p-5">
        <div className="flex items-start gap-3">
          <span
            aria-hidden="true"
            className={cn("flex size-11 shrink-0 items-center justify-center rounded-full", tone.badge)}
          >
            <Icon className="size-6" />
          </span>
          <div>
            <h2 id="lookup-result-title" className="text-xl font-bold leading-tight sm:text-2xl">
              {response.title}
            </h2>
            <p className="mt-1.5 text-foreground/90">{response.message}</p>
          </div>
        </div>

        <CompanyMessages announcements={response.announcements} />

        {mismatch && (
          <p className="rounded-lg bg-notice-soft px-3 py-2 font-medium text-notice-strong">
            {mismatchExplanations[mismatch.reason]}
          </p>
        )}

        {warnings.length > 0 && (
          <ul aria-label="Notes" className="list-disc space-y-1 pl-5 marker:text-notice">
            {warnings.map((warning) => (
              <li key={warning.code}>{warning.message}</li>
            ))}
          </ul>
        )}

        {record && (
          <div aria-label="Simulated register record" className="rounded-lg bg-muted p-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Simulated register record · Demo data
            </p>
            <dl className="flex flex-col divide-y divide-border">
              <Detail label="Agency" value={record.agency} />
              <Detail label="Scheme" value={record.scheme} />
              <Detail label="Registration number" value={record.registration_number} />
              <Detail label="Registered product" value={record.registered_product_name} />
              <Detail label="Registered company" value={record.registered_company_name} />
              <Detail label="Status" value={registerStatusLabels[record.status]} />
              <Detail label="Expires" value={formatDate(record.expires_on)} />
              <Detail label="Source" value={record.provenance} />
              <Detail label="Last checked" value={formatDate(record.last_checked_on)} />
            </dl>
            <p className="mt-3 text-sm text-muted-foreground">
              Compare the registered product and company with what is printed on the pack.
            </p>
          </div>
        )}

        {product && (
          <div>
            <h3 className="mb-1 font-semibold">Product this batch belongs to (FoodLens catalogue)</h3>
            <dl className="flex flex-col divide-y divide-border">
              <Detail label="Name" value={product.name} />
              <Detail label="Brand" value={product.brand} />
              <Detail label="Listed by" value={product.company_display_name} />
              <Detail label="Number on its pack" value={product.registration_number ?? "Not given"} />
              {product.package_size && <Detail label="Package size" value={product.package_size} />}
              {batch && <Detail label="Batch number" value={batch.batch_number} />}
              {batch && <Detail label="Expiry date" value={formatDate(batch.expiry_date)} />}
            </dl>
          </div>
        )}

        <p className="border-t border-border pt-4 text-sm text-muted-foreground">{response.disclaimer}</p>
      </div>
    </section>
  );
}
