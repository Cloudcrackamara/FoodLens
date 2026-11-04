import type { ReactNode } from "react";
import { buttonClass } from "@/lib/ui";

/** Empty list: dashed border and a next step (Supplier.dc.html). */
export function EmptyPanel({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <section className="rounded-[12px] border border-dashed border-line-input bg-white px-6 py-12 text-center">
      <p className="m-0 font-heading text-lg font-semibold text-ink">{title}</p>
      {children && <div className="mx-auto mt-1.5 max-w-[420px] text-text-subtle">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </section>
  );
}

const SKELETON_WIDTHS = ["70%", "55%", "80%"];

/** Loading skeleton; the pulse stops under reduced motion (Supplier.dc.html). */
export function LoadingPanel({ label = "Loading…" }: { label?: string }) {
  return (
    <section
      aria-busy="true"
      aria-label="Loading"
      className="flex flex-col gap-[18px] rounded-[12px] bg-white px-6 py-4 shadow-card"
    >
      <span className="sr-only">{label}</span>
      {SKELETON_WIDTHS.map((width) => (
        <div key={width} aria-hidden="true" className="h-[18px] animate-skeleton rounded-[6px] bg-divider" style={{ width }} />
      ))}
    </section>
  );
}

/** A failed load: red border, and Try again when the caller can retry (Supplier.dc.html). */
export function ErrorPanel({ children, onRetry }: { children: ReactNode; onRetry?: () => void }) {
  return (
    <section role="alert" className="rounded-[12px] border-2 border-bad-line bg-white px-6 py-9 text-center">
      <div className="text-ink">{children}</div>
      {onRetry && (
        <button type="button" onClick={onRetry} className={`${buttonClass("secondary", "sm")} mt-4`}>
          Try again
        </button>
      )}
    </section>
  );
}

/** A form or action error next to the control that caused it. */
export function InlineError({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p role="alert" className={`font-semibold text-bad${className ? ` ${className}` : ""}`}>
      {children}
    </p>
  );
}
