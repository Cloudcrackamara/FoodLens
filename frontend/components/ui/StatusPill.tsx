import type { ReactNode } from "react";

export type Tone = "ok" | "warn" | "neutral" | "bad" | "pending" | "info" | "new" | "alert";

const PILL_TONES: Record<Tone, string> = {
  ok: "bg-ok-bg text-ok",
  warn: "bg-warn-bg text-warn",
  neutral: "bg-neutral-bg text-neutral",
  bad: "bg-bad-bg text-bad",
  pending: "bg-pending-bg text-pending",
  info: "bg-info-bg text-info",
  new: "bg-new-bg text-new",
  alert: "bg-alert-bg text-alert",
};

/** A state pill (design/README.md). Colour carries meaning, so it always has words. */
export function StatusPill({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-sm font-bold ${PILL_TONES[tone]}`}
    >
      {children}
    </span>
  );
}
