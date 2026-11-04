export const DEMO_BANNER_TEXT = "DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE";

/**
 * Shown on every page and every check result. The backend also returns
 * data_mode "DEMO" and a disclaimer, so neither layer relies on the other.
 * "compact" is the thin strip of the Scan and Confirm boards; the default is the Result board's.
 */
export function DemoDataBanner({ variant = "default" }: { variant?: "default" | "compact" }) {
  if (variant === "compact") {
    return (
      <div
        role="note"
        aria-label="Demo data notice"
        className="w-full bg-sun px-4 py-1.5 text-center font-heading text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-2"
      >
        {DEMO_BANNER_TEXT}
      </div>
    );
  }
  return (
    <div
      role="note"
      aria-label="Demo data notice"
      className="flex w-full items-center justify-center gap-2 bg-sun px-4 py-2.5 text-center text-sm font-bold text-ink-2"
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        aria-hidden="true"
        className="flex-none"
      >
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v5M12 7.5h.01" />
      </svg>
      {DEMO_BANNER_TEXT}
    </div>
  );
}
