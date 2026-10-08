"use client";

import { useState, type FormEvent } from "react";
import { FormField } from "@/components/auth/FormField";
import { describeError } from "@/lib/api";
import { useBatchLookup } from "@/lib/lookup";
import { LookupResultView } from "./LookupResultView";

const codeInputHint = "As printed on the package. Letters, numbers, spaces and - . / _ only.";

export function LookupForm() {
  const lookup = useBatchLookup();
  const [productCode, setProductCode] = useState("");
  const [batchNumber, setBatchNumber] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    lookup.mutate({ productCode, batchNumber });
  }

  function chooseCandidate(code: string) {
    setProductCode(code);
    lookup.mutate({ productCode: code, batchNumber });
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <FormField
          id="productCode"
          label="Product code"
          value={productCode}
          hint={codeInputHint}
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          onChange={setProductCode}
        />
        <FormField
          id="batchNumber"
          label="Batch number"
          value={batchNumber}
          hint="Often labelled LOT, Batch, or B/N."
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
          {lookup.isPending ? "Checking…" : "Check demo records"}
        </button>
      </form>

      <div aria-live="polite">
        {lookup.isError && (
          <p role="alert" className="text-red-700 dark:text-red-400">
            {describeError(lookup.error)}
          </p>
        )}
        {lookup.isSuccess && (
          <LookupResultView response={lookup.data} onChooseCandidate={chooseCandidate} />
        )}
      </div>
    </div>
  );
}
