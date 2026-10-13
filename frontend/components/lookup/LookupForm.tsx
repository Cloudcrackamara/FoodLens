"use client";

import { useEffect, useState, type FormEvent } from "react";
import { FormField } from "@/components/auth/FormField";
import { Camera } from "lucide-react";
import { ScanPack, type ScanReader } from "@/components/scan/ScanPack";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { describeError } from "@/lib/api";
import { useRegistrationLookup, type LookupQuery } from "@/lib/lookup";
import { LookupResultView } from "./LookupResultView";

const EMPTY: LookupQuery = { registrationNumber: "", batchNumber: "" };

/**
 * `initial` comes from the page URL (?reg=...&batch=...), e.g. handed over by a scanner or a
 * printed link. When a number is given, the check runs straight away.
 */
export function LookupForm({
  initial = EMPTY,
  scanReader,
}: {
  initial?: LookupQuery;
  /** Tests only: replaces the in-browser OCR reader. */
  scanReader?: ScanReader;
}) {
  const lookup = useRegistrationLookup();
  const [scanning, setScanning] = useState(false);
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

  function confirmScan(query: LookupQuery) {
    setScanning(false);
    setRegistrationNumber(query.registrationNumber);
    setBatchNumber(query.batchNumber);
    check(query);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    check({ registrationNumber, batchNumber });
  }

  return (
    <div className="flex flex-col gap-6" aria-busy={lookup.isPending}>
      <Card className="gap-0">
        <CardContent className="flex flex-col gap-5 pt-4 sm:pt-5">
          <Button type="button" variant="outline" size="lg" onClick={() => setScanning(true)} className="w-full">
            <Camera aria-hidden="true" />
            Scan pack
          </Button>
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <span aria-hidden="true" className="h-px flex-1 bg-border" />
            <span>or type the numbers</span>
            <span aria-hidden="true" className="h-px flex-1 bg-border" />
          </div>
          {scanning && (
            <ScanPack reader={scanReader} onConfirm={confirmScan} onCancel={() => setScanning(false)} />
          )}
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
            <Button type="submit" size="lg" disabled={lookup.isPending} className="w-full">
              {lookup.isPending ? "Checking…" : "Check the register"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <div aria-live="polite">
        {lookup.isError && (
          <Alert variant="destructive" role="alert">
            <AlertDescription>{describeError(lookup.error)}</AlertDescription>
          </Alert>
        )}
        {lookup.isSuccess && <LookupResultView response={lookup.data} />}
      </div>
    </div>
  );
}
