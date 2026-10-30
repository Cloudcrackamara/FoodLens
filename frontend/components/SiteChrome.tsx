"use client";

import { usePathname } from "next/navigation";
import { isConsumerCheckPath, isDemoTillPath, isMerchantPath } from "@/lib/routes";
import { DemoDataBanner } from "./DemoDataBanner";
import { SiteHeader } from "./SiteHeader";

/** Site-wide demo banner and header, except on the consumer check screens, the merchant pages and the demo till (they draw their own). */
export function SiteChrome() {
  const pathname = usePathname();
  if (isConsumerCheckPath(pathname) || isMerchantPath(pathname) || isDemoTillPath(pathname)) return null;
  return (
    <>
      <DemoDataBanner />
      <SiteHeader />
    </>
  );
}
