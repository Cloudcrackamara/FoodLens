"use client";

import { useState, type FormEvent } from "react";
import { FormField } from "@/components/auth/FormField";
import type { Extraction } from "@/lib/ocr/extract";
import type { LookupQuery } from "@/lib/lookup";

type Props = {
  registration: Extraction;
  batch: Extraction | null;
  onConfirm: (query: LookupQuery) => void;
  onRescan: () => void;
  onCancel: () => void;
};

function Suggestions({ items, current, label, onPick }: {
  items: string[];
  current: string;
  label: string;
  onPick: (value: string) => void;
}) {
  const others = items.filter((item) => item !== current);
  if (others.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm" aria-label={label}>
      <span>Other readings:</span>
      {others.map((item) => (
        <button key={item} type="button" onClick={() => onPick(item)} className="rounded-full border border-zinc-500 px-3 py-1 font-mono">
          {item}
        </button>
      ))}
    </div>
  );
}

/** What the scanner read, always shown for checking and editing before any lookup (D94). */
export function ConfirmScan({ registration, batch, onConfirm, onRescan, onCancel }: Props) {
  const [registrationNumber, setRegistrationNumber] = useState(registration.value ?? "");
  const [batchNumber, setBatchNumber] = useState(batch?.value ?? "");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onConfirm({ registrationNumber, batchNumber });
  }

  return (
    <form onSubmit={handleSubmit} noValidate aria-label="Check what was read" className="flex flex-col gap-4">
      <h2 className="text-xl font-bold">Check what was read</h2>
      <p className="text-sm text-zinc-700 dark:text-zinc-300">
        Scanning can misread characters. Compare with the pack and correct anything that is wrong.
      </p>
      {!registration.value && (
        <p role="status" className="text-sm font-medium">
          No registration number was found. Type it, or scan again with the number inside the box.
        </p>
      )}
      <FormField id="scan-registration" label="NAFDAC or SON number on the pack" value={registrationNumber}
        autoComplete="off" autoCapitalize="characters" spellCheck={false} onChange={setRegistrationNumber} />
      <Suggestions items={registration.candidates} current={registrationNumber} label="Other registration readings" onPick={setRegistrationNumber} />
      <FormField id="scan-batch" label="Batch number (optional)" value={batchNumber}
        autoComplete="off" autoCapitalize="characters" spellCheck={false} onChange={setBatchNumber} />
      {batch && <Suggestions items={batch.candidates} current={batchNumber} label="Other batch readings" onPick={setBatchNumber} />}
      <button type="submit" disabled={!registrationNumber.trim()} className="rounded-md bg-zinc-900 px-4 py-3 text-lg font-semibold text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900">
        Check the register
      </button>
      <div className="flex flex-wrap gap-4 text-sm">
        <button type="button" onClick={onRescan} className="underline">Scan again</button>
        <button type="button" onClick={onCancel} className="underline">Type instead</button>
      </div>
    </form>
  );
}
