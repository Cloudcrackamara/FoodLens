import Link from "next/link";
import type { ReactNode } from "react";

const TONES = {
  neutral: "bg-neutral-bg text-neutral",
  info: "bg-info-bg text-info",
  new: "bg-new-bg text-new",
  alert: "bg-alert-bg text-alert",
  pending: "bg-pending-bg text-pending",
} as const;

type Props = {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  /** The whole card is a link when set (design/README.md, component 8). */
  href?: string;
  tone?: keyof typeof TONES;
};

/** A summary card (Supplier.dc.html `ws-cards`): 20px padding, 12px radius, large Poppins value. */
export function SummaryCard({ label, value, sub, href, tone = "neutral" }: Props) {
  const body = (
    <>
      <span className="text-[13px] font-bold">{label}</span>
      <span className="font-heading text-[28px] font-bold leading-[1.1]">{value}</span>
      {sub && <span className="text-xs">{sub}</span>}
    </>
  );
  const className = `flex flex-col items-start gap-1 rounded-[12px] p-5 no-underline ${TONES[tone]}`;
  return href ? (
    <Link href={href} className={className}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  );
}

/** The card grid: 5 columns, 3 below 1200px, 2 below 640px (Supplier.dc.html). */
export function SummaryGrid({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section
      aria-label={label}
      className="grid grid-cols-2 gap-3 sm:gap-5 min-[641px]:grid-cols-3 min-[1200px]:grid-cols-5"
    >
      {children}
    </section>
  );
}
