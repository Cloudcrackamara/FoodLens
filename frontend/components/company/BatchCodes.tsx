"use client";

import { useState, type FormEvent, type ReactNode } from "react";
import { FormField } from "@/components/auth/FormField";
import { describeError } from "@/lib/api";
import { fieldErrors, useCurrentUser } from "@/lib/auth";
import { formatDate } from "@/lib/format";
import {
  MIN_QR_MM,
  generateFormSchema,
  parseCodes,
  unitStatusLabels,
  useAllocations,
  useAreas,
  useBatchUnits,
  useCreateAllocation,
  useDeleteAllocation,
  useDestinations,
  useGenerateLabels,
  useRelease,
  useVoid,
  type BatchUnits,
  type GenerateForm,
} from "@/lib/units";

const buttonClass =
  "self-start rounded-md bg-zinc-900 px-4 py-2 font-semibold text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900";
const inputClass = "rounded-md border border-zinc-400 px-3 py-2 dark:border-zinc-600 dark:bg-zinc-900";
const sectionClass = "flex flex-col gap-3 rounded-md border border-zinc-300 p-4 dark:border-zinc-700";

function ErrorText({ error }: { error: Error | null }) {
  return error ? <p role="alert" className="text-red-700 dark:text-red-400">{describeError(error)}</p> : null;
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className={sectionClass}>
      <h2 id={id} className="text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function countsText(counts: Record<string, number>): string {
  const parts = Object.entries(counts)
    .filter(([, n]) => n > 0)
    .map(([status, n]) => `${unitStatusLabels[status] ?? status}: ${n}`);
  return parts.length ? parts.join(" · ") : "No packs";
}

// --- Generate -------------------------------------------------------------------------------------

function GenerateLabels({ companyId, batchId }: { companyId: string; batchId: string }) {
  const generate = useGenerateLabels(companyId, batchId);
  const [form, setForm] = useState<GenerateForm>({ quantity: "", units_per_carton: "", qr_size_mm: "20" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (key: keyof GenerateForm) => (value: string) => setForm({ ...form, [key]: value });
  const small = Number(form.qr_size_mm) > 0 && Number(form.qr_size_mm) < MIN_QR_MM;

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = generateFormSchema.safeParse(form);
    if (!parsed.success) return setErrors(fieldErrors(parsed.error));
    setErrors({});
    generate.mutate(parsed.data);
  }

  return (
    <form onSubmit={onSubmit} noValidate aria-label="Generate codes and labels" className="flex flex-col gap-3">
      <div role="note" className="rounded-md border-2 border-amber-600 p-3 text-sm">
        <p className="font-semibold">The label file holds every raw code.</p>
        <p>
          FoodLens keeps only a fingerprint of each code and cannot download this file again. Keep
          it secure, send it only to your printer, and delete every copy after printing. If it is
          lost or leaked before release, void the unreleased packs and generate new codes.
        </p>
      </div>
      <FormField id="quantity" label="Packs to generate" value={String(form.quantity)} error={errors.quantity} hint="Up to 2,000 at a time." onChange={set("quantity")} />
      <FormField id="units_per_carton" label="Packs per carton (optional)" value={form.units_per_carton} error={errors.units_per_carton} hint="Leave empty for loose packs. Each carton gets its own code." onChange={set("units_per_carton")} />
      <FormField id="qr_size_mm" label="QR size in mm" value={String(form.qr_size_mm)} error={errors.qr_size_mm} hint={`${MIN_QR_MM} mm or more scans best on most phones.`} onChange={set("qr_size_mm")} />
      {small && (
        <p role="status" className="text-sm text-amber-800 dark:text-amber-300">
          QR codes smaller than {MIN_QR_MM} mm may not scan reliably on every phone.
        </p>
      )}
      <ErrorText error={generate.error} />
      {generate.isSuccess && (
        <p role="status" className="text-sm">
          Downloaded {generate.data.filename}. Print the labels, then delete the file.
          {generate.data.warning && ` ${generate.data.warning}`}
        </p>
      )}
      <button type="submit" disabled={generate.isPending} className={buttonClass}>
        {generate.isPending ? "Making codes and labels… (up to a minute for 2,000 packs)" : "Generate and download labels"}
      </button>
    </form>
  );
}

// --- Release and cartons --------------------------------------------------------------------------

function ReleaseUnits({ companyId, batchId, data }: { companyId: string; batchId: string; data: BatchUnits }) {
  const release = useRelease(companyId, batchId);
  const [cartonRef, setCartonRef] = useState("");
  const unreleased = data.cartons.filter((c) => c.status === "ISSUED");
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm">Release packs once they leave your factory. Released packs cannot be voided; use a recall instead.</p>
      <div className="flex flex-wrap gap-3">
        <button type="button" disabled={release.isPending || !data.units.ISSUED} className={buttonClass} onClick={() => release.mutate({ carton_ref: null })}>
          Release all unreleased packs
        </button>
        {unreleased.length > 0 && (
          <span className="flex flex-wrap items-center gap-2">
            <label htmlFor="release-carton" className="text-sm font-medium">Carton</label>
            <select id="release-carton" value={cartonRef} onChange={(e) => setCartonRef(e.target.value)} className={inputClass}>
              <option value="">Choose…</option>
              {unreleased.map((c) => <option key={c.carton_ref} value={c.carton_ref}>{c.carton_ref}</option>)}
            </select>
            <button type="button" disabled={!cartonRef || release.isPending} className={buttonClass} onClick={() => release.mutate({ carton_ref: cartonRef }, { onSuccess: () => setCartonRef("") })}>
              Release carton
            </button>
          </span>
        )}
      </div>
      <ErrorText error={release.error} />
      {release.isSuccess && <p role="status" className="text-sm">Released {release.data.units} packs.</p>}
    </div>
  );
}

function CartonList({ data }: { data: BatchUnits }) {
  if (data.cartons.length === 0) return null;
  return (
    <table className="text-left text-sm">
      <caption className="text-left font-medium">Cartons</caption>
      <thead><tr><th className="pr-4">Carton</th><th className="pr-4">Status</th><th>Packs</th></tr></thead>
      <tbody>
        {data.cartons.map((c) => (
          <tr key={c.carton_ref}>
            <td className="pr-4">{c.carton_ref}</td>
            <td className="pr-4">{unitStatusLabels[c.status] ?? c.status}</td>
            <td>{countsText(c.units)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// --- Void -------------------------------------------------------------------------------------------

type VoidScope = "whole_batch" | "cartons" | "codes";

function VoidUnits({ companyId, batchId }: { companyId: string; batchId: string }) {
  const voidUnits = useVoid(companyId, batchId);
  const [scope, setScope] = useState<VoidScope>("whole_batch");
  const [reason, setReason] = useState("");
  const [targets, setTargets] = useState("");
  const [problem, setProblem] = useState<string | null>(null);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reason.trim()) return setProblem("Give a reason for voiding.");
    const list = parseCodes(targets);
    if (scope !== "whole_batch" && list.length === 0) return setProblem("List at least one carton or code.");
    setProblem(null);
    voidUnits.mutate(
      {
        reason: reason.trim(),
        whole_batch: scope === "whole_batch",
        carton_refs: scope === "cartons" ? list : [],
        codes: scope === "codes" ? list : [],
      },
      { onSuccess: () => { setReason(""); setTargets(""); } },
    );
  }

  return (
    <form onSubmit={onSubmit} noValidate aria-label="Void unreleased packs" className="flex flex-col gap-3">
      <p className="text-sm">Void codes that were never released, for example when a label file is lost. Voided codes stop working; generate new ones to replace them.</p>
      <fieldset className="flex flex-col gap-1">
        <legend className="font-medium">What to void</legend>
        {([["whole_batch", "Every unreleased pack in this batch"], ["cartons", "Cartons (for example C001, C002)"], ["codes", "Single codes from the label file"]] as const).map(([value, label]) => (
          <label key={value} className="flex items-center gap-2">
            <input type="radio" name="void-scope" checked={scope === value} onChange={() => setScope(value)} />
            {label}
          </label>
        ))}
      </fieldset>
      {scope !== "whole_batch" && (
        <label className="flex flex-col gap-1">
          <span className="font-medium">{scope === "cartons" ? "Carton references" : "Codes, one per line"}</span>
          <textarea value={targets} onChange={(e) => setTargets(e.target.value)} rows={3} className={inputClass} autoCapitalize="characters" spellCheck={false} />
        </label>
      )}
      <FormField id="void-reason" label="Reason" value={reason} onChange={setReason} />
      {problem && <p role="alert" className="text-red-700 dark:text-red-400">{problem}</p>}
      <ErrorText error={voidUnits.error} />
      {voidUnits.isSuccess && <p role="status" className="text-sm">Voided {voidUnits.data.units} packs.</p>}
      <button type="submit" disabled={voidUnits.isPending} className={buttonClass}>Void packs</button>
    </form>
  );
}

// --- Allocations ------------------------------------------------------------------------------------

type AllocationMode = "quantity" | "cartons" | "codes";

function Allocations({ companyId, batchId }: { companyId: string; batchId: string }) {
  const allocations = useAllocations(companyId, batchId);
  const areas = useAreas();
  const destinations = useDestinations(companyId);
  const create = useCreateAllocation(companyId, batchId);
  const remove = useDeleteAllocation(companyId, batchId);
  const [areaId, setAreaId] = useState("");
  const [destinationId, setDestinationId] = useState("");
  const [plannedDate, setPlannedDate] = useState("");
  const [mode, setMode] = useState<AllocationMode>("quantity");
  const [quantity, setQuantity] = useState("");
  const [list, setList] = useState("");
  const [problem, setProblem] = useState<string | null>(null);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!areaId) return setProblem("Choose the destination area.");
    const items = parseCodes(list);
    if (mode === "quantity" && !(Number.isInteger(Number(quantity)) && Number(quantity) >= 1)) return setProblem("Enter how many packs.");
    if (mode !== "quantity" && items.length === 0) return setProblem("List at least one carton or code.");
    setProblem(null);
    create.mutate(
      {
        destination_area_id: areaId,
        destination_company_id: destinationId || null,
        quantity: mode === "quantity" ? Number(quantity) : null,
        planned_date: plannedDate || null,
        carton_refs: mode === "cartons" ? items : [],
        unit_codes: mode === "codes" ? items : [],
      },
      { onSuccess: () => { setQuantity(""); setList(""); } },
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm">Plan where this batch should go. Allocations are a plan: packs found outside them are noted in the timeline, never alerted one by one.</p>
      <ErrorText error={allocations.error} />
      {allocations.data?.length === 0 && <p className="text-sm">No allocations yet.</p>}
      <ul className="flex flex-col gap-2">
        {allocations.data?.map((a) => (
          <li key={a.allocation_id} aria-label={`Allocation to ${a.destination_area.city}`} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-zinc-200 p-3 text-sm dark:border-zinc-800">
            <span>
              {a.quantity} packs to {a.destination_company ? `${a.destination_company.display_name}, ` : ""}
              {a.destination_area.city}, {a.destination_area.state}
              {a.planned_date && ` · planned ${formatDate(a.planned_date)}`}
              {a.carton_refs.length > 0 && ` · cartons ${a.carton_refs.join(", ")}`}
              {a.units_listed > 0 && ` · ${a.units_listed} single packs`}
            </span>
            <button type="button" className="underline" disabled={remove.isPending} onClick={() => remove.mutate(a.allocation_id)}>Remove</button>
          </li>
        ))}
      </ul>
      <form onSubmit={onSubmit} noValidate aria-label="Add an allocation" className="flex flex-col gap-3">
        <h3 className="font-semibold">Add an allocation</h3>
        <label className="flex flex-col gap-1">
          <span className="font-medium">Destination area</span>
          <select value={areaId} onChange={(e) => setAreaId(e.target.value)} className={inputClass}>
            <option value="">Choose…</option>
            {areas.data?.map((a) => <option key={a.area_id} value={a.area_id}>{a.city}, {a.state}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="font-medium">Destination company (optional)</span>
          <select value={destinationId} onChange={(e) => setDestinationId(e.target.value)} className={inputClass}>
            <option value="">Any company in that area</option>
            {destinations.data?.map((d) => <option key={d.company_id} value={d.company_id}>{d.display_name}</option>)}
          </select>
        </label>
        <FormField id="planned_date" label="Planned dispatch date (optional)" type="date" value={plannedDate} onChange={setPlannedDate} />
        <fieldset className="flex flex-col gap-1">
          <legend className="font-medium">Allocate by</legend>
          {([["quantity", "Number of packs"], ["cartons", "Cartons"], ["codes", "Single codes from the label file"]] as const).map(([value, label]) => (
            <label key={value} className="flex items-center gap-2">
              <input type="radio" name="allocation-mode" checked={mode === value} onChange={() => setMode(value)} />
              {label}
            </label>
          ))}
        </fieldset>
        {mode === "quantity" ? (
          <FormField id="allocation-quantity" label="Number of packs" value={quantity} onChange={setQuantity} />
        ) : (
          <label className="flex flex-col gap-1">
            <span className="font-medium">{mode === "cartons" ? "Carton references" : "Codes, one per line"}</span>
            <textarea value={list} onChange={(e) => setList(e.target.value)} rows={3} className={inputClass} autoCapitalize="characters" spellCheck={false} />
          </label>
        )}
        {problem && <p role="alert" className="text-red-700 dark:text-red-400">{problem}</p>}
        <ErrorText error={create.error} />
        <button type="submit" disabled={create.isPending} className={buttonClass}>Add allocation</button>
      </form>
    </div>
  );
}

// --- Page ------------------------------------------------------------------------------------------

export function BatchCodes({ companyId, batchId, isOwner }: { companyId: string; batchId: string; isOwner: boolean }) {
  const units = useBatchUnits(companyId, batchId);
  if (units.isPending) return <p>Loading…</p>;
  if (units.isError) return <ErrorText error={units.error} />;
  const data = units.data;
  const total = Object.values(data.units).reduce((sum, n) => sum + n, 0);

  return (
    <div className="flex flex-col gap-6">
      <section aria-labelledby="batch-heading">
        <h1 id="batch-heading" className="text-2xl font-bold">{data.product_name} · batch {data.batch_number}</h1>
        <p className="text-sm">Expires {formatDate(data.expiry_date)}</p>
        <p className="mt-2">{total} packs: {countsText(data.units)}</p>
        {data.released_at && <p className="text-sm">Every pack in this batch has been released.</p>}
      </section>

      <Section id="generate-heading" title="Codes and labels">
        {isOwner ? <GenerateLabels companyId={companyId} batchId={batchId} /> : (
          <p className="text-sm">Only the company owner can generate codes and download labels.</p>
        )}
      </Section>

      {total > 0 && (
        <Section id="release-heading" title="Release">
          <ReleaseUnits companyId={companyId} batchId={batchId} data={data} />
          <CartonList data={data} />
        </Section>
      )}

      {total > 0 && isOwner && (
        <Section id="void-heading" title="Void unreleased packs">
          <VoidUnits companyId={companyId} batchId={batchId} />
        </Section>
      )}

      {total > 0 && (
        <Section id="allocations-heading" title="Allocations">
          <Allocations companyId={companyId} batchId={batchId} />
        </Section>
      )}
    </div>
  );
}

/** The signed-in member's view of one batch. Owner-only parts are hidden for staff; the server
 *  enforces the same rules (D106). */
export function MemberBatchCodes({ batchId }: { batchId: string }) {
  const { data: user, isPending } = useCurrentUser();
  if (isPending) return <p>Loading…</p>;
  const membership = user?.membership;
  if (!membership) return <p>Sign in as a member of the manufacturer to manage this batch.</p>;
  return (
    <BatchCodes
      companyId={membership.company_id}
      batchId={batchId}
      isOwner={membership.role === "OWNER"}
    />
  );
}
