"use client";

import { useState } from "react";
import { DemoDataBanner } from "@/components/DemoDataBanner";
import { formatDate, registerStatusLabels, type LookupResponse } from "@/lib/lookup";

const mismatchExplanations = {
  different_registration_number:
    "FoodLens lists this batch under a different registration number.",
  registered_names_differ:
    "The register record names a different product or company than the one this batch belongs to.",
} as const;

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col sm:flex-row sm:gap-2">
      <dt className="font-medium text-zinc-600 sm:w-44 sm:shrink-0 dark:text-zinc-400">{label}</dt>
      <dd className="break-words">{value}</dd>
    </div>
  );
}

function CompanyMessages({ announcements }: { announcements: LookupResponse["announcements"] }) {
  const [open, setOpen] = useState(true);
  if (!open || announcements.length === 0) return null;
  return (
    <aside
      aria-label="Messages from the company"
      className="flex flex-col gap-2 rounded-md border-2 border-zinc-500 bg-zinc-50 p-3 dark:bg-zinc-900"
    >
      {announcements.map((item) => (
        <div key={`${item.posted_at}-${item.title}`}>
          <p className="text-xs font-semibold uppercase tracking-wide">{item.label}</p>
          <p className="font-semibold">{item.title}</p>
          <p>{item.message}</p>
          <p className="text-xs text-zinc-600 dark:text-zinc-400">
            Posted {formatDate(item.posted_at.slice(0, 10))}
          </p>
        </div>
      ))}
      <button type="button" onClick={() => setOpen(false)} className="self-end text-sm underline">
        Close
      </button>
    </aside>
  );
}

/**
 * Lookup result. Neutral styling (no green/red): a result describes a record in a simulated,
 * fictional register, never whether food is fit to eat or whether the pack is the original.
 * The demo banner is repeated inside every result.
 */
export function LookupResultView({ response }: { response: LookupResponse }) {
  const { register_record: record, product, batch, mismatch, warnings } = response;

  return (
    <section
      aria-labelledby="lookup-result-title"
      className="flex flex-col gap-4 overflow-hidden rounded-md border border-zinc-300 dark:border-zinc-700"
    >
      <DemoDataBanner />
      <div className="flex flex-col gap-4 px-4 pb-4">
        <div>
          <h2 id="lookup-result-title" className="text-xl font-bold">
            {response.title}
          </h2>
          <p className="mt-1">{response.message}</p>
        </div>

        <CompanyMessages announcements={response.announcements} />

        {mismatch && <p className="font-medium">{mismatchExplanations[mismatch.reason]}</p>}

        {warnings.length > 0 && (
          <ul aria-label="Notes" className="list-disc space-y-1 pl-5">
            {warnings.map((warning) => (
              <li key={warning.code}>{warning.message}</li>
            ))}
          </ul>
        )}

        {record && (
          <div aria-label="Simulated register record" className="rounded-md border border-zinc-200 p-3 dark:border-zinc-800">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
              Simulated register record · Demo data
            </p>
            <dl className="flex flex-col gap-1">
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
            <p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">
              Compare the registered product and company with what is printed on the pack.
            </p>
          </div>
        )}

        {product && (
          <div>
            <h3 className="mb-2 font-semibold">Product this batch belongs to (FoodLens catalogue)</h3>
            <dl className="flex flex-col gap-1">
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

        <p className="text-sm text-zinc-700 dark:text-zinc-300">{response.disclaimer}</p>
      </div>
    </section>
  );
}
