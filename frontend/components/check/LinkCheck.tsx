"use client";

import Link from "next/link";
import { useState } from "react";
import { describeError } from "@/lib/api";
import { codeFromQrText, useLinkCheck } from "@/lib/check";
import { InlineError } from "@/components/ui/Panels";
import { buttonClass } from "@/lib/ui";
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
        <h1 className="font-heading text-[25px] font-bold leading-[1.25]">This link is not a FoodLens code</h1>
        <p className="text-text">Scan the QR on the pack again, or type the code printed under it.</p>
        <Link href="/check" className={buttonClass("primary", "lg")}>
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
        <p role="status" className="py-8 text-center text-lg text-text">
          Checking this code…
        </p>
      )}
      {check.isError && (
        <InlineError>{describeError(check.error)}</InlineError>
      )}
      {check.data && <CheckResultView result={check.data} code={code} simulatedCity={city} />}
      <DemoCityPicker value={city} onChange={setCity} />
      <Link href="/check" className={buttonClass("primary", "lg")}>
        Check another pack
      </Link>
    </div>
  );
}
