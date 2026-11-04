"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { describeError } from "@/lib/api";
import { codeFromQrText, useLinkCheck } from "@/lib/check";
import { DemoDataBanner } from "@/components/DemoDataBanner";
import { ConsumerHeader } from "@/components/ui/ConsumerHeader";
import { InlineError } from "@/components/ui/Panels";
import { buttonClass } from "@/lib/ui";
import { CheckResultView } from "./CheckResultView";
import { DemoCityPicker } from "./DemoCityPicker";

/** Header and banner of a /p screen that has no result yet (Result.dc.html order). */
export function LinkCheckShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-1 flex-col">
      <ConsumerHeader title="Check a pack" backHref="/" backLabel="Back to home" />
      <DemoDataBanner />
      <main className="mx-auto box-border flex w-full max-w-[520px] flex-1 flex-col gap-5 px-5 py-5">{children}</main>
    </div>
  );
}

/**
 * /p/{token}, opened from any phone camera. The page itself records nothing: the check is a
 * POST made from the browser after mount, so link previews and prefetching create no scan (D117).
 */
export function LinkCheck({ token }: { token: string }) {
  const code = codeFromQrText(token);
  if (!code) {
    return (
      <LinkCheckShell>
        <h1 className="m-0 font-heading text-[25px] font-bold leading-[1.25]">This link is not a FoodLens code</h1>
        <p className="m-0 text-text">Scan the QR on the pack again, or type the code printed under it.</p>
        <Link href="/check" className={buttonClass("primary", "lg")}>
          Check a pack
        </Link>
      </LinkCheckShell>
    );
  }
  return <LinkCheckResult code={code} />;
}

function LinkCheckResult({ code }: { code: string }) {
  const [city, setCity] = useState("");
  const check = useLinkCheck(code, city || null);
  const picker = <DemoCityPicker value={city} onChange={setCity} />;

  if (check.data) {
    return (
      <div className="flex flex-1 flex-col">
        <ConsumerHeader title="Check a pack" backHref="/" backLabel="Back to home" />
        <main className="flex flex-1 flex-col">
          <CheckResultView result={check.data} code={code} simulatedCity={city} checkAnotherHref="/check">
            {picker}
          </CheckResultView>
        </main>
      </div>
    );
  }

  return (
    <LinkCheckShell>
      {check.isPending && (
        <p role="status" className="py-8 text-center text-lg text-text">
          Checking this code…
        </p>
      )}
      {check.isError && <InlineError>{describeError(check.error)}</InlineError>}
      {picker}
      <Link href="/check" className={buttonClass("primary", "lg")}>
        Check another pack
      </Link>
    </LinkCheckShell>
  );
}
