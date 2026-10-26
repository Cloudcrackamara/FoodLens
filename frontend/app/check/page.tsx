import type { Metadata } from "next";
import { CheckPack } from "@/components/check/CheckPack";

export const metadata: Metadata = { title: "Check a pack · FoodLens (demo)" };

/** Free consumer check, no account: Scan QR or Type code (D141). */
export default function CheckPage() {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-6 px-4 py-6 sm:py-10">
      <div>
        <h1 className="text-3xl font-bold">Check a pack</h1>
        <p className="mt-2 text-zinc-700 dark:text-zinc-300">
          See what has been recorded for the code on your pack: who issued it, whether it is in
          circulation or sold, and any recall. Free, with no account.
        </p>
      </div>
      <CheckPack />
      <p className="text-xs text-zinc-600 dark:text-zinc-400">
        A copied QR carries the same code. FoodLens spots copies by whether the code was sold,
        where it is checked, how often, and where the stock was sent, not by the QR alone. No QR
        system catches every copied code.
      </p>
    </main>
  );
}
