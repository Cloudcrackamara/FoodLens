import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { DemoTillScreen } from "@/components/pos/DemoTill";
import { demoPosEnabled } from "@/lib/features";

export const metadata: Metadata = { title: "Demo till · FoodLens (demo)" };

/** The simulated POS till (D123). Exists only with NEXT_PUBLIC_DEMO_POS_ENABLED=true. */
export default function DemoPosRoute() {
  if (!demoPosEnabled) notFound();
  return <DemoTillScreen />;
}
