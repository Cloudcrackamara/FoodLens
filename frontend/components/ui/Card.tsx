import type { ComponentPropsWithoutRef, ElementType } from "react";

const VARIANTS = {
  // Consumer screens: white, 16px radius, light border (Result.dc.html).
  consumer: "rounded-[16px] border border-line bg-white p-5",
  // Business workspace: white, 12px radius, card shadow (Supplier.dc.html).
  workspace: "rounded-[12px] bg-white p-6 shadow-card",
} as const;

type Props<T extends ElementType> = {
  as?: T;
  variant?: keyof typeof VARIANTS;
} & Omit<ComponentPropsWithoutRef<T>, "as">;

export function Card<T extends ElementType = "section">({ as, variant = "consumer", className, ...rest }: Props<T>) {
  const Component: ElementType = as ?? "section";
  return <Component className={`${VARIANTS[variant]}${className ? ` ${className}` : ""}`} {...rest} />;
}
