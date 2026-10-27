import Link from "next/link";

type Props = {
  title: string;
  backHref: string;
  backLabel: string;
};

/** White consumer header with a back button (Result.dc.html). */
export function ConsumerHeader({ title, backHref, backLabel }: Props) {
  return (
    <header className="flex items-center gap-1 border-b border-divider bg-white px-3 py-2">
      <Link
        href={backHref}
        aria-label={backLabel}
        className="inline-flex size-11 items-center justify-center rounded-full text-ink"
      >
        <svg
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M15 5l-7 7 7 7" />
        </svg>
      </Link>
      <p className="m-0 font-heading text-[17px] font-semibold">{title}</p>
    </header>
  );
}
