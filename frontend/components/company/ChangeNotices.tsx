"use client";

import { useState, type FormEvent } from "react";
import { describeError } from "@/lib/api";
import { useProducts } from "@/lib/catalogue";
import {
  ALLOWED_EXTENSIONS,
  attachmentProblem,
  batchFields,
  changeTypes,
  fieldLabels,
  noticeStatusLabels,
  productFields,
  useCompanyNotices,
  useRespondToClarification,
  useSubmitNotice,
  type ChangeTypeValue,
  type Notice,
} from "@/lib/changeNotices";
import { formatDate } from "@/lib/lookup";

const inputClass = "rounded-md border border-zinc-400 px-3 py-2 dark:border-zinc-600 dark:bg-zinc-900";
const buttonClass =
  "self-start rounded-md bg-zinc-900 px-4 py-2 font-semibold text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900";

export function Changes({ notice }: { notice: Notice }) {
  return (
    <table className="w-full text-left text-sm">
      <thead>
        <tr><th className="pr-2">Field</th><th className="pr-2">Before</th><th>Proposed</th></tr>
      </thead>
      <tbody>
        {notice.fields.map((field) => (
          <tr key={field.field_name}>
            <td className="pr-2">{fieldLabels[field.field_name] ?? field.field_name}</td>
            <td className="pr-2">{field.applied_old_value ?? field.current_value ?? "(empty)"}</td>
            <td>{field.proposed_value ?? "(empty)"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function RespondForm({ companyId, notice }: { companyId: string; notice: Notice }) {
  const respond = useRespondToClarification(companyId);
  const [message, setMessage] = useState("");
  return (
    <form
      aria-label="Answer clarification"
      onSubmit={(event) => {
        event.preventDefault();
        if (message.trim()) respond.mutate({ noticeId: notice.notice_id, message: message.trim() });
      }}
      className="flex flex-col gap-2"
    >
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Your answer</span>
        <textarea value={message} onChange={(event) => setMessage(event.target.value)} className={inputClass} />
      </label>
      {respond.isError && <p role="alert" className="text-red-700 dark:text-red-400">{describeError(respond.error)}</p>}
      <button type="submit" disabled={respond.isPending} className={buttonClass}>Send answer</button>
    </form>
  );
}

function NoticeCard({ companyId, notice }: { companyId: string; notice: Notice }) {
  const target = notice.batch_number ? `${notice.product_name} · batch ${notice.batch_number}` : notice.product_name;
  return (
    <li aria-label={`Notice for ${target}`} className="flex flex-col gap-2 rounded-md border border-zinc-300 p-4 dark:border-zinc-700">
      <div>
        <p className="font-semibold">{target}</p>
        <p className="text-sm">
          {changeTypes[notice.change_type as ChangeTypeValue] ?? notice.change_type} · {noticeStatusLabels[notice.review_status]}
          {notice.effective_date && ` · effective ${formatDate(notice.effective_date)}`}
        </p>
      </div>
      <Changes notice={notice} />
      <p className="whitespace-pre-line text-sm">{notice.reason}</p>
      {notice.review_note && <p className="text-sm">Reviewer note: {notice.review_note}</p>}
      {notice.attachments.length > 0 && (
        <ul className="text-sm">
          {notice.attachments.map((a) => (
            <li key={a.attachment_id}>
              <a className="underline" href={`/api/companies/${companyId}/attachments/${a.attachment_id}`}>{a.original_filename}</a>
            </li>
          ))}
        </ul>
      )}
      {notice.review_status === "CLARIFICATION_REQUESTED" && <RespondForm companyId={companyId} notice={notice} />}
    </li>
  );
}

function SubmitNoticeForm({ companyId }: { companyId: string }) {
  const products = useProducts(companyId);
  const submit = useSubmitNotice(companyId);
  const [target, setTarget] = useState("");
  const [changeType, setChangeType] = useState<ChangeTypeValue>("PRODUCT_DETAILS");
  const [reason, setReason] = useState("");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [files, setFiles] = useState<File[]>([]);
  const [problem, setProblem] = useState<string | null>(null);

  const isBatch = target.startsWith("batch:");
  const fields = isBatch ? batchFields : productFields;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const changes = Object.fromEntries(
      Object.entries(values).filter(([key, value]) => key in fields && value.trim() !== "").map(([k, v]) => [k, v.trim()]),
    );
    const fileProblem = files.map(attachmentProblem).find(Boolean);
    if (!target) return setProblem("Choose the product or batch to change");
    if (Object.keys(changes).length === 0) return setProblem("Enter at least one new value");
    if (!reason.trim()) return setProblem("Explain the reason for the change");
    if (fileProblem) return setProblem(fileProblem);
    setProblem(null);
    const [kind, id] = target.split(":");
    submit.mutate(
      {
        target: kind === "batch" ? { batchId: id } : { productId: id },
        changeType,
        reason: reason.trim(),
        effectiveDate,
        changes,
        files,
      },
      {
        onSuccess: () => {
          setValues({});
          setReason("");
          setEffectiveDate("");
          setFiles([]);
        },
      },
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate aria-label="Submit a change notice" className="flex flex-col gap-3">
      <h3 className="font-semibold">Submit a change notice</h3>
      <p className="text-sm text-zinc-700 dark:text-zinc-300">
        Published data stays as it is until a FoodLens admin approves the notice. Product codes and batch numbers cannot be changed.
      </p>
      <label className="flex flex-col gap-1">
        <span className="font-medium">What to change</span>
        <select value={target} onChange={(event) => { setTarget(event.target.value); setValues({}); }} className={inputClass}>
          <option value="">Choose…</option>
          {products.data?.map((product) => [
            <option key={product.product_id} value={`product:${product.product_id}`}>{product.name} ({product.product_code})</option>,
            ...product.batches.map((batch) => (
              <option key={batch.batch_id} value={`batch:${batch.batch_id}`}>{product.name} · batch {batch.batch_number}</option>
            )),
          ])}
        </select>
      </label>
      <label className="flex flex-col gap-1">
        <span className="font-medium">Type of change</span>
        <select value={changeType} onChange={(event) => setChangeType(event.target.value as ChangeTypeValue)} className={inputClass}>
          {Object.entries(changeTypes).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </label>
      {target && (
        <fieldset className="flex flex-col gap-2 rounded-md border border-zinc-300 p-3 dark:border-zinc-700">
          <legend className="px-1 font-medium">New values (leave blank to keep)</legend>
          {Object.entries(fields).map(([key, label]) => (
            <label key={key} className="flex flex-col gap-1">
              <span>{label}</span>
              <input
                type={isBatch ? "date" : "text"}
                value={values[key] ?? ""}
                onChange={(event) => setValues({ ...values, [key]: event.target.value })}
                className={inputClass}
              />
            </label>
          ))}
        </fieldset>
      )}
      <label className="flex flex-col gap-1">
        <span className="font-medium">Reason</span>
        <textarea value={reason} onChange={(event) => setReason(event.target.value)} className={inputClass} />
      </label>
      <label className="flex flex-col gap-1">
        <span className="font-medium">Effective date (optional)</span>
        <input type="date" value={effectiveDate} onChange={(event) => setEffectiveDate(event.target.value)} className={inputClass} />
      </label>
      <label className="flex flex-col gap-1">
        <span className="font-medium">Supporting files (optional, PDF/PNG/JPG, max 5 MB each)</span>
        <input type="file" multiple accept={ALLOWED_EXTENSIONS.join(",")} onChange={(event) => setFiles(Array.from(event.target.files ?? []))} />
      </label>
      {problem && <p role="alert" className="text-red-700 dark:text-red-400">{problem}</p>}
      {submit.isError && <p role="alert" className="text-red-700 dark:text-red-400">{describeError(submit.error)}</p>}
      <button type="submit" disabled={submit.isPending} className={buttonClass}>Submit for review</button>
    </form>
  );
}

export function ChangeNotices({ companyId }: { companyId: string }) {
  const notices = useCompanyNotices(companyId);
  return (
    <section aria-labelledby="notices-heading" className="flex flex-col gap-4">
      <h2 id="notices-heading" className="text-lg font-semibold">Change notices</h2>
      {notices.isError && <p role="alert">{describeError(notices.error)}</p>}
      {notices.data?.length === 0 && <p>No change notices yet.</p>}
      <ul className="flex flex-col gap-3">
        {notices.data?.map((notice) => <NoticeCard key={notice.notice_id} companyId={companyId} notice={notice} />)}
      </ul>
      <SubmitNoticeForm companyId={companyId} />
    </section>
  );
}
