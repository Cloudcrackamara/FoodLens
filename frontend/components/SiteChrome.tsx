"use client";

import { usePathname } from "next/navigation";
import { isConsumerCheckPath } from "@/lib/routes";
import { DemoDataBanner } from "./DemoDataBanner";
import { SiteHeader } from "./SiteHeader";

/** Site-wide demo banner and header, except on the consumer check screens (they draw their own). */
export function SiteChrome() {
  const pathname = usePathname();
  if (isConsumerCheckPath(pathname)) return null;
  return (
    <>
      <DemoDataBanner />
      <SiteHeader />
    </>
  );
}
