import type { Metadata } from "next";

export const metadata: Metadata = { title: "Check a pack · FoodLens (demo)" };

/** Placeholder until the QR check (Scan QR and Type code) arrives in Phase 3 (docs/PLAN.md). */
export default function CheckPage() {
  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 px-4 py-8">
      <div>
        <h1 className="text-2xl font-bold">Check a pack</h1>
        <p className="mt-2 text-zinc-700 dark:text-zinc-300">
          Pack checks are being rebuilt around the QR code printed on each pack. Scanning a QR code
          or typing the code underneath it will open here in the next version of this demo.
        </p>
      </div>
    </main>
  );
}
