export const DEMO_BANNER_TEXT = "DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE";

/**
 * Shown on every page and every check result. The backend also returns
 * data_mode "DEMO" and a disclaimer, so neither layer relies on the other.
 */
export function DemoDataBanner() {
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
