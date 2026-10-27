import type { ReactNode } from "react";

export type StatusTone = "ok" | "warn" | "neutral" | "bad" | "info" | "alert";

type Style = {
  card: string;
  circle: string;
  label: string;
  body: string;
  icon: { size: number; stroke: string; width: number; paths: ReactNode };
};

const TRIANGLE = (
  <>
    <path d="M12 3L2.5 20h19z" />
    <path d="M12 10v4.5M12 17.5h.01" />
  </>
);

// Status sections from Result.dc.html. The warn icon is the clock from the board's "Expired" pill.
// The alert tone (recall) has no board: alert background with no border (founder, 26 Oct 2026),
// the warning triangle and the standard text colour.
const STYLES: Record<StatusTone, Style> = {
  ok: {
    card: "border border-[#BFE0CC] bg-ok-bg",
    circle: "bg-brand",
    label: "text-ok",
    body: "text-[#2E3A33]",
    icon: { size: 26, stroke: "#FFFFFF", width: 2.6, paths: <path d="M5 12.5l4.5 4.5L19 7.5" /> },
  },
  warn: {
    card: "border border-[#F2D29C] bg-warn-bg",
    circle: "bg-[#B45309]",
    label: "text-warn",
    body: "text-[#4A3412]",
    icon: {
      size: 26,
      stroke: "#FFFFFF",
      width: 2.2,
      paths: (
        <>
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7v5l3 2" />
        </>
      ),
    },
  },
  neutral: {
    card: "border border-[#DADCE2] bg-neutral-bg",
    circle: "bg-[#4B4F5C]",
    label: "text-neutral",
    body: "text-[#3A3F4B]",
    icon: {
      size: 24,
      stroke: "#FFFFFF",
      width: 2.2,
      paths: (
        <>
          <circle cx="11" cy="11" r="6.5" />
          <path d="M20 20l-4.2-4.2M8.8 8.8l4.4 4.4M13.2 8.8l-4.4 4.4" />
        </>
      ),
    },
  },
  bad: {
    card: "bg-bad-line text-white shadow-[0_10px_24px_rgba(180,35,24,0.25)]",
    circle: "bg-white",
    label: "text-white",
    body: "text-[#FFE9E6]",
    icon: { size: 26, stroke: "#B42318", width: 2.4, paths: TRIANGLE },
  },
  info: {
    card: "border border-[#D4D2EE] bg-info-bg",
    circle: "bg-info",
    label: "text-info",
    body: "text-[#2F2C5E]",
    icon: {
      size: 24,
      stroke: "#FFFFFF",
      width: 2.4,
      paths: <path d="M9 9.5a3 3 0 1 1 4.2 2.8c-.8.3-1.2 1-1.2 1.8v.6M12 18h.01" />,
    },
  },
  alert: {
    card: "bg-alert-bg",
    circle: "bg-alert",
    label: "text-alert",
    body: "text-text",
    icon: { size: 26, stroke: "#FFFFFF", width: 2.4, paths: TRIANGLE },
  },
};

type Props = {
  tone: StatusTone;
  label: ReactNode;
  title: ReactNode;
  titleId?: string;
  children?: ReactNode;
};

/** The coloured status card at the top of a check result. */
export function StatusCard({ tone, label, title, titleId, children }: Props) {
  const { card, circle, label: labelClass, body, icon } = STYLES[tone];
  return (
    <section className={`rounded-[18px] px-5 py-[22px] ${card}`}>
      <div className="flex flex-wrap items-center gap-3">
        <span
          aria-hidden="true"
          className={`inline-flex size-12 flex-none items-center justify-center rounded-full ${circle}`}
        >
          <svg
            width={icon.size}
            height={icon.size}
            viewBox="0 0 24 24"
            fill="none"
            stroke={icon.stroke}
            strokeWidth={icon.width}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            {icon.paths}
          </svg>
        </span>
        <span className={`text-[13px] font-bold uppercase tracking-[0.04em] ${labelClass}`}>{label}</span>
      </div>
      <h2 id={titleId} className="mt-3.5 mb-1.5 font-heading text-[25px] font-bold leading-[1.25]">
        {title}
      </h2>
      {children && <div className={body}>{children}</div>}
    </section>
  );
}
