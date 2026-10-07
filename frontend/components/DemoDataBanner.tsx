export const DEMO_BANNER_TEXT = "DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE";

/**
 * Shown on every page and every lookup result. The backend also returns
 * data_mode "DEMO" and a disclaimer, so neither layer relies on the other.
 */
export function DemoDataBanner() {
  return (
    <div
      role="note"
      aria-label="Demo data notice"
      className="w-full bg-amber-300 px-4 py-2 text-center text-sm font-bold tracking-wide text-black"
    >
      {DEMO_BANNER_TEXT}
    </div>
  );
}
