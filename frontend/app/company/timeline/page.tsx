import type { Metadata } from "next";
import { CompanyTimelineScreen } from "@/components/company/CompanyScreens";

export const metadata: Metadata = { title: "Pack timeline · FoodLens (demo)" };

export default function Page() {
  return <CompanyTimelineScreen />;
}
