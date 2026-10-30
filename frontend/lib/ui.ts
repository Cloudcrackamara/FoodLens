/**
 * Shared class names for the design system (design/README.md). Values are copied from
 * design/prototype; don't invent new ones.
 */

/** danger: the red outline "Report a concern" button of Result.dc.html (mismatch). */
export type ButtonVariant = "primary" | "secondary" | "quiet" | "danger";
/**
 * xl: scan and typed-code screens (56px, Scan.dc.html, Confirm.dc.html). lg: consumer primary
 * (54px). md: consumer secondary (48px). sm: workspace (44px).
 */
export type ButtonSize = "xl" | "lg" | "md" | "sm";

const BUTTON_BASE =
  "inline-flex items-center justify-center gap-2 rounded-full px-5 font-heading font-semibold no-underline " +
  "disabled:cursor-not-allowed disabled:border-transparent disabled:bg-line disabled:text-[#4B4F5C]";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-brand text-white",
  secondary: "border-2 border-brand bg-white text-brand-dark",
  quiet: "border-2 border-line-input bg-white text-ink",
  danger: "border-2 border-bad-line bg-white text-bad-line",
};

const BUTTON_SIZES: Record<ButtonSize, string> = {
  xl: "min-h-14 text-[17px]",
  lg: "min-h-[54px] text-[17px]",
  md: "min-h-12 text-base",
  sm: "min-h-11 text-base",
};

export function buttonClass(variant: ButtonVariant = "primary", size: ButtonSize = "sm"): string {
  return `${BUTTON_BASE} ${BUTTON_VARIANTS[variant]} ${BUTTON_SIZES[size]}`;
}

/** A busy primary button with the fl-spin spinner (Confirm.dc.html checking, Report.dc.html sending). */
export const busyButtonClass =
  "inline-flex min-h-14 items-center justify-center gap-2.5 rounded-full bg-brand-tint px-5 font-heading text-base font-semibold text-brand-dark";

/** Text inputs and selects (Accounts.dc.html). */
export const inputClass =
  "min-h-[46px] w-full rounded-[10px] border border-line-input bg-white px-3 text-base text-ink";

/** Multi-line text (same border and radius as inputs). */
export const textareaClass =
  "w-full rounded-[10px] border border-line-input bg-white px-3 py-2 text-base text-ink";

/**
 * The large code field on the typed-code screen (Confirm.dc.html): 1px grey border, 2px green
 * while focused (the board's "typed" state), 2px red on a correction, grey fill while checking.
 */
export function codeInputClass(state: "default" | "error" = "default", checking = false): string {
  const border =
    state === "error" ? "border-2 border-bad-line" : "border border-line-input focus:border-2 focus:border-brand";
  return `h-14 w-full rounded-[12px] ${border} ${checking ? "bg-paper" : "bg-white"} px-4 font-mono text-[22px] font-semibold tracking-[0.04em] text-ink outline-none`;
}

/** Text links on light backgrounds. */
export const linkClass = "font-semibold text-brand-dark underline";

/** Section headings inside cards (Poppins 17px/600). */
export const cardTitleClass = "font-heading text-[17px] font-semibold text-ink";

/** Label/value rows in a card (Result.dc.html "What the register shows"). */
export const detailListClass = "grid grid-cols-[minmax(0,0.9fr)_minmax(0,1.4fr)] text-[15px]";
export const detailTermClass = "border-t border-divider py-2.5 text-[#4B4F5C]";
export const detailValueClass = "border-t border-divider py-2.5 font-semibold";

/** Small muted help text. */
export const helpTextClass = "text-sm text-text-subtle";

/** Filter tabs (Supplier.dc.html): selected is solid brand, others white with a light border. */
export function tabClass(selected: boolean): string {
  return `inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-3.5 font-semibold ${
    selected ? "border border-brand bg-brand text-white" : "border border-line bg-white text-text"
  }`;
}

/** Grey note box inside a card (Result.dc.html). */
export const noteClass = "rounded-[10px] bg-paper p-3 text-sm text-text-muted";
