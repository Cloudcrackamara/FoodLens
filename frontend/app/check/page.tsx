import type { Metadata } from "next";
import { CheckPack } from "@/components/check/CheckPack";

export const metadata: Metadata = { title: "Check a pack · FoodLens (demo)" };

/** Free consumer check, no account: Scan QR or Type code (D141). */
export default function CheckPage() {
  return (
    <main className="mx-auto flex w-full max-w-[440px] flex-1 flex-col gap-6 px-4 py-5">
      <div>
        <h1 className="font-heading text-[25px] font-bold leading-[1.25]">Check a pack</h1>
        <p className="mt-2 text-text">
          See what has been recorded for the code on your pack: who issued it, whether it is in
          circulation or sold, and any recall. Free, with no account.
        </p>
      </div>
      <CheckPack />
      <p className="text-sm text-text-subtle">
        A copied QR carries the same code. FoodLens spots copies by whether the code was sold,
        where it is checked, how often, and where the stock was sent, not by the QR alone. No QR
        system catches every copied code.
      </p>
    </main>
  );
}
