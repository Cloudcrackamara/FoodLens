"use client";

import { useEffect, useState, type FormEvent } from "react";
import { FormField } from "@/components/auth/FormField";
import { describeError } from "@/lib/api";
import { useRegistrationLookup, type LookupQuery } from "@/lib/lookup";
import { LookupResultView } from "./LookupResultView";

const EMPTY: LookupQuery = { registrationNumber: "", batchNumber: "" };

/**
 * `initial` comes from the page URL (?reg=...&batch=...), e.g. handed over by a scanner or a
 * printed link. When a number is given, the check runs straight away.
 */
export function LookupForm({ initial = EMPTY }: { initial?: LookupQuery }) {
  const lookup = useRegistrationLookup();
  const [registrationNumber, setRegistrationNumber] = useState(initial.registrationNumber);
  const [batchNumber, setBatchNumber] = useState(initial.batchNumber);

  useEffect(() => {
    if (initial.registrationNumber) lookup.mutate(initial);
    // Run once for the values the page was opened with.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function check(query: LookupQuery) {
    lookup.mutate(query);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    check({ registrationNumber, batchNumber });
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <FormField
          id="registrationNumber"
          label="NAFDAC or SON number on the pack"
          value={registrationNumber}
          hint='Type it as printed, for example "DEMO-NAFDAC-0001". Words like "NAFDAC Reg No:" are ignored.'
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          onChange={setRegistrationNumber}
        />
        <FormField
          id="batchNumber"
          label="Batch number (optional)"
          value={batchNumber}
          hint="Often labelled LOT, Batch, or B/N. Helps spot a number copied onto another product."
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          onChange={setBatchNumber}
        />
        <button
          type="submit"
          disabled={lookup.isPending}
          className="rounded-md bg-zinc-900 px-4 py-3 text-lg font-semibold text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {lookup.isPending ? "Checking…" : "Check the register"}
        </button>
      </form>

      <div aria-live="polite">
        {lookup.isError && (
          <p role="alert" className="text-red-700 dark:text-red-400">
            {describeError(lookup.error)}
          </p>
        )}
        {lookup.isSuccess && <LookupResultView response={lookup.data} />}
      </div>
    </div>
  );
}
