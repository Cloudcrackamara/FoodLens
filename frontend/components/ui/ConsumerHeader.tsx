import Link from "next/link";

type Props = {
  title: string;
  backHref: string;
  backLabel: string;
  /** light: white bar (Result.dc.html, Confirm.dc.html). dark: on the ink scan screen (Scan.dc.html). */
  tone?: "light" | "dark";
  /** The heading level of the title; the boards use h1 on screens with no other page heading. */
  titleAs?: "p" | "h1";
};

/** Consumer header with a back button. */
export function ConsumerHeader({ title, backHref, backLabel, tone = "light", titleAs = "p" }: Props) {
  const Title = titleAs;
  const dark = tone === "dark";
  return (
    <header
      className={
        dark
          ? "flex items-center justify-between gap-3 px-3 py-2 text-white"
          : "flex items-center gap-1 border-b border-divider bg-white px-3 py-2"
      }
    >
      <Link
        href={backHref}
        aria-label={backLabel}
        className={`inline-flex size-11 flex-none items-center justify-center rounded-full ${dark ? "text-white" : "text-ink"}`}
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
      <Title className="m-0 font-heading text-[17px] font-semibold">{title}</Title>
      {/* Keeps the title centred where the board has its help button (no guide page yet). */}
      {dark && <span aria-hidden="true" className="size-11 flex-none" />}
    </header>
  );
}
