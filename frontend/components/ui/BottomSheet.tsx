import type { ReactNode } from "react";

/** White bottom action sheet on the dark scan screen (Scan.dc.html). */
export function BottomSheet({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto box-border flex w-full max-w-[520px] flex-col gap-2.5 rounded-t-[24px] bg-white px-5 pt-5 pb-6 text-ink">
      {children}
    </div>
  );
}

/** The lock line under the scan buttons (Scan.dc.html). */
export function PrivacyNote({ children }: { children: ReactNode }) {
  return (
    <p className="mt-1 mb-0 flex items-center justify-center gap-2 text-center text-[13px] text-[#4B4F5C]">
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#1B7A45"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className="flex-none"
      >
        <rect x="5" y="11" width="14" height="10" rx="2" />
        <path d="M8 11V8a4 4 0 0 1 8 0v3" />
      </svg>
      {children}
    </p>
  );
}
