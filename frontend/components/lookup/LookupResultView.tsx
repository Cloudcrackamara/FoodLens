"use client";

import { useState } from "react";
import { DemoDataBanner } from "@/components/DemoDataBanner";
import { credentialStatuses, formatDate, type LookupResponse } from "@/lib/lookup";

const mismatchLabels = {
  product_code: "Product code",
  credential: "Credential record",
} as const;

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col sm:flex-row sm:gap-2">
      <dt className="font-medium text-zinc-600 sm:w-40 sm:shrink-0 dark:text-zinc-400">{label}</dt>
      <dd className="break-words">{value}</dd>
    </div>
  );
}

type Props = {
  response: LookupResponse;
  onChooseCandidate?: (productCode: string) => void;
};

/**
 * Lookup result. Deliberately neutral styling (no green/red): a result describes a demo record,
 * never whether food is fit to eat. The demo banner is repeated inside every result.
 */
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

export function LookupResultView({ response, onChooseCandidate }: Props) {
  const { product, batch, credentials, mismatch, warnings, candidates } = response;

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

        {mismatch && (
          <p>
            <span className="font-medium">Field that differs:</span> {mismatchLabels[mismatch.field]}
          </p>
        )}

        {warnings.length > 0 && (
          <ul aria-label="Notes" className="list-disc space-y-1 pl-5">
            {warnings.map((warning) => (
              <li key={warning.code}>{warning.message}</li>
            ))}
          </ul>
        )}

        {candidates.length > 0 && (
          <div>
            <h3 className="mb-2 font-semibold">Products with this batch number</h3>
            <ul className="flex flex-col gap-2">
              {candidates.map((candidate) => (
                <li
                  key={candidate.product_code}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-zinc-200 p-3 dark:border-zinc-800"
                >
                  <span>
                    {candidate.name} ({candidate.brand}) · {candidate.product_code}
                  </span>
                  {onChooseCandidate && (
                    <button
                      type="button"
                      onClick={() => onChooseCandidate(candidate.product_code)}
                      className="rounded-md border border-zinc-500 px-3 py-1 text-sm font-medium"
                    >
                      Choose this product
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {product && (
          <div>
            <h3 className="mb-2 font-semibold">Product (demo record)</h3>
            <dl className="flex flex-col gap-1">
              <Detail label="Name" value={product.name} />
              <Detail label="Brand" value={product.brand} />
              <Detail label="Product code" value={product.product_code} />
              <Detail label="Category" value={product.category} />
              {product.package_size && <Detail label="Package size" value={product.package_size} />}
              <Detail label="Manufacturer" value={product.manufacturer_name} />
              <Detail label="Listed by" value={product.company_display_name} />
            </dl>
          </div>
        )}

        {batch && (
          <div>
            <h3 className="mb-2 font-semibold">Batch (demo record)</h3>
            <dl className="flex flex-col gap-1">
              <Detail label="Batch number" value={batch.batch_number} />
              <Detail label="Production date" value={formatDate(batch.production_date)} />
              <Detail label="Expiry date" value={formatDate(batch.expiry_date)} />
            </dl>
          </div>
        )}

        {product && (
          <div>
            <h3 className="font-semibold">Product-level credential records</h3>
            <p className="mb-2 text-sm text-zinc-700 dark:text-zinc-300">
              {response.credential_scope_note}
            </p>
            {credentials.length === 0 ? (
              <p>No credential record matches this product in the demo data.</p>
            ) : (
              <ul className="flex flex-col gap-3">
                {credentials.map((credential) => (
                  <li
                    key={`${credential.agency}-${credential.reference_number}`}
                    aria-label={`Product-level credential ${credential.reference_number}`}
                    className="rounded-md border border-zinc-200 p-3 dark:border-zinc-800"
                  >
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                      Product-level · Demo data
                    </p>
                    <dl className="flex flex-col gap-1">
                      <Detail label="Agency" value={credential.agency} />
                      <Detail label="Scheme" value={credential.scheme} />
                      <Detail label="Reference" value={credential.reference_number} />
                      <Detail label="Status" value={credentialStatuses[credential.status]} />
                      <Detail
                        label="Valid"
                        value={`${formatDate(credential.valid_from)} to ${formatDate(credential.valid_until)}`}
                      />
                      <Detail label="Provenance" value={credential.provenance} />
                      <Detail label="Last checked" value={formatDate(credential.checked_on)} />
                    </dl>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <p className="text-sm text-zinc-700 dark:text-zinc-300">{response.disclaimer}</p>
      </div>
    </section>
  );
}
