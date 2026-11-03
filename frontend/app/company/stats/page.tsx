import type { Metadata } from "next";
import { CompanyStatsScreen } from "@/components/company/CompanyScreens";

export const metadata: Metadata = { title: "Stats · FoodLens (demo)" };

export default function Page() {
  return <CompanyStatsScreen />;
}
