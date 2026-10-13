"use client";

import { useState, type FormEvent } from "react";
import { FormField } from "@/components/auth/FormField";
import { Button } from "@/components/ui/button";
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
        <button key={item} type="button" onClick={() => onPick(item)} className="min-h-9 rounded-full border border-input bg-card px-3 py-1 font-mono hover:bg-secondary">
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
      <h2 className="text-2xl font-bold">Check what was read</h2>
      <p className="text-sm text-muted-foreground">
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
      <Button type="submit" size="lg" disabled={!registrationNumber.trim()}>
        Check the register
      </Button>
      <div className="flex flex-wrap gap-4 text-sm">
        <Button type="button" variant="link" onClick={onRescan}>Scan again</Button>
        <Button type="button" variant="link" onClick={onCancel}>Type instead</Button>
      </div>
    </form>
  );
}
