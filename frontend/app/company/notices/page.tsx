import type { Metadata } from "next";
import { CompanyNoticesScreen } from "@/components/company/CompanyScreens";

export const metadata: Metadata = { title: "Notices · FoodLens (demo)" };

export default function Page() {
  return <CompanyNoticesScreen />;
}
