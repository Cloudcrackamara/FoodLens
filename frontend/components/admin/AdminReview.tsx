"use client";

import { useState } from "react";
import { describeError } from "@/lib/api";
import { useCurrentUser } from "@/lib/auth";
import {
  companyStatusLabels,
  companyTypes,
  locationStatusLabels,
  useAdminCompanies,
  useAdminLocations,
  useCompanyDecision,
  useLocationDecision,
  type AdminCompany,
  type AdminLocation,
  type CompanyDecision,
  type CompanyStatus,
} from "@/lib/companies";
import { formatDate } from "@/lib/lookup";

const companyActions: Record<CompanyStatus, CompanyDecision[]> = {
  PENDING_REVIEW: ["APPROVE", "REJECT"],
  APPROVED: ["SUSPEND"],
  SUSPENDED: ["APPROVE"],
  REJECTED: [],
};

const actionLabels: Record<CompanyDecision, string> = {
  APPROVE: "Approve",
  REJECT: "Reject",
  SUSPEND: "Suspend",
};

function reviewedLine(item: { reviewed_at: string | null; reviewed_by_display_name?: string | null }) {
  if (!item.reviewed_at) return null;
  const who = item.reviewed_by_display_name ? ` by ${item.reviewed_by_display_name}` : "";
  return `Reviewed${who} on ${formatDate(item.reviewed_at.slice(0, 10))}`;
}

function CompanyRow({ company }: { company: AdminCompany }) {
  const decide = useCompanyDecision();
  const [note, setNote] = useState("");
  const actions = companyActions[company.review_status];

  return (
    <li aria-label={company.display_name} className="flex flex-col gap-2 rounded-md border border-zinc-300 p-4 dark:border-zinc-700">
      <div>
        <h3 className="font-semibold">{company.display_name}</h3>
        <p className="text-sm">{companyTypes[company.company_type]} · {companyStatusLabels[company.review_status]}</p>
      </div>
      <dl className="grid grid-cols-1 gap-1 text-sm sm:grid-cols-2">
        <div><dt className="inline font-medium">Owner: </dt><dd className="inline">{company.owner_display_name ?? "None"} {company.owner_email && `(${company.owner_email})`}</dd></div>
        <div><dt className="inline font-medium">Contact: </dt><dd className="inline">{company.contact_email}</dd></div>
        <div><dt className="inline font-medium">Claimed legal name: </dt><dd className="inline">{company.claimed_legal_name}</dd></div>
        <div><dt className="inline font-medium">Claimed registration no.: </dt><dd className="inline">{company.claimed_business_identifier ?? "Not given"}</dd></div>
        <div><dt className="inline font-medium">Claimed address: </dt><dd className="inline">{company.claimed_address ?? "Not given"}</dd></div>
        <div><dt className="inline font-medium">Registered: </dt><dd className="inline">{formatDate(company.created_at.slice(0, 10))}</dd></div>
      </dl>
      {reviewedLine(company) && <p className="text-sm">{reviewedLine(company)}{company.review_note && `: ${company.review_note}`}</p>}
      {actions.length > 0 && (
        <div className="flex flex-col gap-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium">Review note (optional)</span>
            <input value={note} onChange={(event) => setNote(event.target.value)} className="rounded-md border border-zinc-400 px-3 py-2 dark:border-zinc-600 dark:bg-zinc-900" />
          </label>
          <div className="flex flex-wrap gap-2">
            {actions.map((action) => (
              <button
                key={action}
                type="button"
                disabled={decide.isPending}
                onClick={() => decide.mutate({ companyId: company.company_id, decision: action, note })}
                className="rounded-md border border-zinc-600 px-3 py-1 font-medium disabled:opacity-60"
              >
                {actionLabels[action]}
              </button>
            ))}
          </div>
        </div>
      )}
      {decide.isError && <p role="alert" className="text-red-700 dark:text-red-400">{describeError(decide.error)}</p>}
    </li>
  );
}

function LocationRow({ location }: { location: AdminLocation }) {
  const decide = useLocationDecision();
  const [note, setNote] = useState("");
  const pending = location.review_status === "PENDING_REVIEW";

  return (
    <li aria-label={location.name} className="flex flex-col gap-2 rounded-md border border-zinc-300 p-4 dark:border-zinc-700">
      <div>
        <h3 className="font-semibold">{location.name}</h3>
        <p className="text-sm">{location.company_display_name} ({companyStatusLabels[location.company_review_status]}) · {locationStatusLabels[location.review_status]}</p>
        <p>{location.address}, {location.area}</p>
      </div>
      {reviewedLine(location) && <p className="text-sm">{reviewedLine(location)}</p>}
      {pending && (
        <div className="flex flex-col gap-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium">Review note (optional)</span>
            <input value={note} onChange={(event) => setNote(event.target.value)} className="rounded-md border border-zinc-400 px-3 py-2 dark:border-zinc-600 dark:bg-zinc-900" />
          </label>
          <div className="flex flex-wrap gap-2">
            <button type="button" disabled={decide.isPending} onClick={() => decide.mutate({ locationId: location.location_id, decision: "APPROVE", note })} className="rounded-md border border-zinc-600 px-3 py-1 font-medium disabled:opacity-60">
              Mark demo-reviewed
            </button>
            <button type="button" disabled={decide.isPending} onClick={() => decide.mutate({ locationId: location.location_id, decision: "REJECT", note })} className="rounded-md border border-zinc-600 px-3 py-1 font-medium disabled:opacity-60">
              Reject
            </button>
          </div>
        </div>
      )}
      {decide.isError && <p role="alert" className="text-red-700 dark:text-red-400">{describeError(decide.error)}</p>}
    </li>
  );
}

const companyFilters: (CompanyStatus | "ALL")[] = ["PENDING_REVIEW", "APPROVED", "SUSPENDED", "REJECTED", "ALL"];

export function AdminReview() {
  const { data: user, isPending } = useCurrentUser();
  const [companyFilter, setCompanyFilter] = useState<CompanyStatus | "ALL">("PENDING_REVIEW");
  const companies = useAdminCompanies(companyFilter);
  const locations = useAdminLocations("PENDING_REVIEW");

  if (isPending) return <p>Loading…</p>;
  if (!user?.is_admin) return <p role="alert">Admin access required.</p>;

  return (
    <div className="flex flex-col gap-8">
      <section aria-labelledby="companies-heading" className="flex flex-col gap-3">
        <h2 id="companies-heading" className="text-xl font-bold">Companies</h2>
        <label className="flex flex-col gap-1 text-sm sm:w-64">
          <span className="font-medium">Show</span>
          <select value={companyFilter} onChange={(event) => setCompanyFilter(event.target.value as CompanyStatus | "ALL")} className="rounded-md border border-zinc-400 px-3 py-2 dark:border-zinc-600 dark:bg-zinc-900">
            {companyFilters.map((value) => (
              <option key={value} value={value}>{value === "ALL" ? "All companies" : companyStatusLabels[value]}</option>
            ))}
          </select>
        </label>
        {companies.isError && <p role="alert">{describeError(companies.error)}</p>}
        {companies.data?.length === 0 && <p>No companies in this list.</p>}
        <ul className="flex flex-col gap-3">
          {companies.data?.map((company) => <CompanyRow key={company.company_id} company={company} />)}
        </ul>
      </section>

      <section aria-labelledby="locations-heading" className="flex flex-col gap-3">
        <h2 id="locations-heading" className="text-xl font-bold">Supplier locations awaiting review</h2>
        {locations.isError && <p role="alert">{describeError(locations.error)}</p>}
        {locations.data?.length === 0 && <p>No locations awaiting review.</p>}
        <ul className="flex flex-col gap-3">
          {locations.data?.map((location) => <LocationRow key={location.location_id} location={location} />)}
        </ul>
      </section>
    </div>
  );
}
