import type { Metadata } from "next";
import { CompanyHomeScreen } from "@/components/company/CompanyScreens";

export const metadata: Metadata = { title: "Overview · FoodLens (demo)" };

/** The manufacturer overview; other companies see their profile. */
export default function Page() {
  return <CompanyHomeScreen />;
}
