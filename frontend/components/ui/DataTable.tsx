import type { ReactNode } from "react";

/** A list table (Admin.dc.html "Pending reviews"). It scrolls inside its card when narrow. */
export function DataTable({ label, head, children }: { label: string; head: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-[12px] bg-white p-5 shadow-card">
      <table aria-label={label} className="w-full min-w-[520px] border-collapse text-sm text-text">
        <thead>
          <tr className="text-left text-ink">
            {head.map((title) => (
              <th key={title} scope="col" className="pr-3 pb-3 font-semibold">
                {title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export const cellClass = "border-t border-divider py-2.5 pr-3 align-top";
export const numberCellClass = `${cellClass} tabular-nums`;

/** One hue for one measure (never a state colour); the number beside it carries the value. */
export function InlineBar({ value, max }: { value: number; max: number }) {
  const width = max > 0 ? Math.max(4, Math.round((value / max) * 100)) : 0;
  return (
    <span aria-hidden="true" className="block h-2 w-full max-w-[220px] rounded-[4px] bg-paper">
      <span className="block h-2 rounded-[4px] bg-info" style={{ width: `${width}%` }} />
    </span>
  );
}
