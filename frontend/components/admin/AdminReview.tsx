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
import {
  useAdminCredentials,
  useCredentialDecision,
  type AdminCredential,
} from "@/lib/catalogue";
import {
  changeTypes,
  noticeStatusLabels,
  useAdminNotices,
  useNoticeDecision,
  type AdminNotice,
  type ChangeTypeValue,
  type NoticeDecision,
} from "@/lib/changeNotices";
import { Changes } from "@/components/company/ChangeNotices";
import {
  useHideAnnouncement,
  useLiveAnnouncements,
  type AdminAnnouncement,
} from "@/lib/announcements";
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

function CredentialRow({ credential }: { credential: AdminCredential }) {
  const decide = useCredentialDecision();
  const [note, setNote] = useState("");
  const send = (decision: "APPROVE" | "REJECT") =>
    decide.mutate({ credentialId: credential.credential_id, decision, note });

  return (
    <li aria-label={credential.reference_number} className="flex flex-col gap-2 rounded-md border border-zinc-300 p-4 dark:border-zinc-700">
      <div>
        <h3 className="font-semibold">{credential.agency} · {credential.reference_number}</h3>
        <p className="text-sm">{credential.scheme}</p>
        <p className="text-sm">
          {credential.product_name} ({credential.product_code}) · {credential.company_display_name}
          {credential.submitted_by_display_name && ` · claimed by ${credential.submitted_by_display_name}`}
        </p>
        <p className="text-sm">Valid {formatDate(credential.valid_from)} to {formatDate(credential.valid_until)}</p>
      </div>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Review note (optional)</span>
        <input value={note} onChange={(event) => setNote(event.target.value)} className="rounded-md border border-zinc-400 px-3 py-2 dark:border-zinc-600 dark:bg-zinc-900" />
      </label>
      <div className="flex flex-wrap gap-2">
        <button type="button" disabled={decide.isPending} onClick={() => send("APPROVE")} className="rounded-md border border-zinc-600 px-3 py-1 font-medium disabled:opacity-60">Approve for lookups</button>
        <button type="button" disabled={decide.isPending} onClick={() => send("REJECT")} className="rounded-md border border-zinc-600 px-3 py-1 font-medium disabled:opacity-60">Reject</button>
      </div>
      {decide.isError && <p role="alert" className="text-red-700 dark:text-red-400">{describeError(decide.error)}</p>}
    </li>
  );
}

const noticeActions: Record<AdminNotice["review_status"], [NoticeDecision, string][]> = {
  PENDING_REVIEW: [["APPROVE", "Approve and apply"], ["REQUEST_CLARIFICATION", "Request clarification"], ["REJECT", "Reject"]],
  CLARIFICATION_REQUESTED: [["REJECT", "Reject"]],
  APPROVED: [],
  REJECTED: [],
};

function NoticeRow({ notice }: { notice: AdminNotice }) {
  const decide = useNoticeDecision();
  const [note, setNote] = useState("");
  const target = notice.batch_number ? `${notice.product_name} · batch ${notice.batch_number}` : notice.product_name;
  const actions = noticeActions[notice.review_status];

  return (
    <li aria-label={`Notice for ${target}`} className="flex flex-col gap-2 rounded-md border border-zinc-300 p-4 dark:border-zinc-700">
      <div>
        <h3 className="font-semibold">{target} ({notice.product_code})</h3>
        <p className="text-sm">
          {notice.company_display_name} · {changeTypes[notice.change_type as ChangeTypeValue] ?? notice.change_type} · {noticeStatusLabels[notice.review_status]}
          {notice.submitted_by_display_name && ` · by ${notice.submitted_by_display_name}`}
          {notice.effective_date && ` · effective ${formatDate(notice.effective_date)}`}
        </p>
      </div>
      <Changes notice={notice} />
      <p className="whitespace-pre-line text-sm">{notice.reason}</p>
      {notice.attachments.length > 0 && (
        <ul className="text-sm">
          {notice.attachments.map((a) => (
            <li key={a.attachment_id}><a className="underline" href={`/api/admin/attachments/${a.attachment_id}`}>{a.original_filename}</a></li>
          ))}
        </ul>
      )}
      {notice.review_note && <p className="text-sm">Note: {notice.review_note}</p>}
      {actions.length > 0 && (
        <div className="flex flex-col gap-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium">Review note (required to request clarification)</span>
            <input value={note} onChange={(event) => setNote(event.target.value)} className="rounded-md border border-zinc-400 px-3 py-2 dark:border-zinc-600 dark:bg-zinc-900" />
          </label>
          <div className="flex flex-wrap gap-2">
            {actions.map(([decision, label]) => (
              <button key={decision} type="button" disabled={decide.isPending} onClick={() => decide.mutate({ noticeId: notice.notice_id, decision, note })} className="rounded-md border border-zinc-600 px-3 py-1 font-medium disabled:opacity-60">
                {label}
              </button>
            ))}
          </div>
        </div>
      )}
      {decide.isError && <p role="alert" className="text-red-700 dark:text-red-400">{describeError(decide.error)}</p>}
    </li>
  );
}

function AnnouncementRow({ item }: { item: AdminAnnouncement }) {
  const hide = useHideAnnouncement();
  const [reason, setReason] = useState("");
  return (
    <li aria-label={item.title} className="flex flex-col gap-2 rounded-md border border-zinc-300 p-4 dark:border-zinc-700">
      <div>
        <h3 className="font-semibold">{item.title}</h3>
        <p>{item.message}</p>
        <p className="text-sm">
          {item.product_name} ({item.product_code}) · {item.company_display_name}
          {item.created_by_display_name && ` · posted by ${item.created_by_display_name}`} · {formatDate(item.created_at.slice(0, 10))}
        </p>
      </div>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Reason (optional)</span>
        <input value={reason} onChange={(event) => setReason(event.target.value)} className="rounded-md border border-zinc-400 px-3 py-2 dark:border-zinc-600 dark:bg-zinc-900" />
      </label>
      <button type="button" disabled={hide.isPending} onClick={() => hide.mutate({ announcementId: item.announcement_id, reason })} className="self-start rounded-md border border-zinc-600 px-3 py-1 font-medium disabled:opacity-60">
        Hide announcement
      </button>
      {hide.isError && <p role="alert" className="text-red-700 dark:text-red-400">{describeError(hide.error)}</p>}
    </li>
  );
}

const companyFilters: (CompanyStatus | "ALL")[] = ["PENDING_REVIEW", "APPROVED", "SUSPENDED", "REJECTED", "ALL"];

export function AdminReview() {
  const { data: user, isPending } = useCurrentUser();
  const [companyFilter, setCompanyFilter] = useState<CompanyStatus | "ALL">("PENDING_REVIEW");
  const companies = useAdminCompanies(companyFilter);
  const locations = useAdminLocations("PENDING_REVIEW");
  const credentials = useAdminCredentials();
  const notices = useAdminNotices();
  const announcements = useLiveAnnouncements();
  const openNotices = notices.data?.filter((n) => n.review_status === "PENDING_REVIEW" || n.review_status === "CLARIFICATION_REQUESTED");

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

      <section aria-labelledby="credentials-heading" className="flex flex-col gap-3">
        <h2 id="credentials-heading" className="text-xl font-bold">Credential claims awaiting review</h2>
        <p className="text-sm text-zinc-700 dark:text-zinc-300">Approved claims appear in consumer lookups as product-level demo records.</p>
        {credentials.isError && <p role="alert">{describeError(credentials.error)}</p>}
        {credentials.data?.length === 0 && <p>No credential claims awaiting review.</p>}
        <ul className="flex flex-col gap-3">
          {credentials.data?.map((credential) => <CredentialRow key={credential.credential_id} credential={credential} />)}
        </ul>
      </section>

      <section aria-labelledby="notices-heading" className="flex flex-col gap-3">
        <h2 id="notices-heading" className="text-xl font-bold">Change notices</h2>
        <p className="text-sm text-zinc-700 dark:text-zinc-300">Approving applies every change at once and keeps the previous values for audit.</p>
        {notices.isError && <p role="alert">{describeError(notices.error)}</p>}
        {openNotices?.length === 0 && <p>No open change notices.</p>}
        <ul className="flex flex-col gap-3">
          {openNotices?.map((notice) => <NoticeRow key={notice.notice_id} notice={notice} />)}
        </ul>
      </section>

      <section aria-labelledby="announcements-heading" className="flex flex-col gap-3">
        <h2 id="announcements-heading" className="text-xl font-bold">Live announcements</h2>
        <p className="text-sm text-zinc-700 dark:text-zinc-300">Company messages go live without review. Hide any that are misleading.</p>
        {announcements.isError && <p role="alert">{describeError(announcements.error)}</p>}
        {announcements.data?.length === 0 && <p>No live announcements.</p>}
        <ul className="flex flex-col gap-3">
          {announcements.data?.map((item) => <AnnouncementRow key={item.announcement_id} item={item} />)}
        </ul>
      </section>
    </div>
  );
}
