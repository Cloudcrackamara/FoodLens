"use client";

import Link from "next/link";
import { useState } from "react";
import { describeError } from "@/lib/api";
import { codeFromQrText, useLinkCheck } from "@/lib/check";
import { CheckResultView } from "./CheckResultView";
import { DemoCityPicker } from "./DemoCityPicker";

/**
 * /p/{token}, opened from any phone camera. The page itself records nothing: the check is a
 * POST made from the browser after mount, so link previews and prefetching create no scan (D117).
 */
export function LinkCheck({ token }: { token: string }) {
  const code = codeFromQrText(token);
  if (!code) {
    return (
      <div className="flex flex-col gap-3">
        <h1 className="text-2xl font-bold">This link is not a FoodLens code</h1>
        <p>Scan the QR on the pack again, or type the code printed under it.</p>
        <Link href="/check" className="min-h-12 rounded-lg bg-zinc-900 px-4 py-3 text-center font-semibold text-white dark:bg-zinc-100 dark:text-zinc-900">
          Check a pack
        </Link>
      </div>
    );
  }
  return <LinkCheckResult code={code} />;
}

function LinkCheckResult({ code }: { code: string }) {
  const [city, setCity] = useState("");
  const check = useLinkCheck(code, city || null);

  return (
    <div className="flex flex-col gap-4">
      {check.isPending && (
        <p role="status" className="py-8 text-center text-lg">
          Checking this code…
        </p>
      )}
      {check.isError && (
        <p role="alert" className="text-red-700 dark:text-red-400">
          {describeError(check.error)}
        </p>
      )}
      {check.data && <CheckResultView result={check.data} code={code} simulatedCity={city} />}
      <DemoCityPicker value={city} onChange={setCity} />
      <Link href="/check" className="min-h-12 rounded-lg border border-zinc-900 px-4 py-3 text-center font-semibold dark:border-zinc-100">
        Check another pack
      </Link>
    </div>
  );
}
