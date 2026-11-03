import type { Metadata } from "next";
import { CompanyProfileScreen } from "@/components/company/CompanyScreens";

export const metadata: Metadata = { title: "Company profile · FoodLens (demo)" };

export default function Page() {
  return <CompanyProfileScreen />;
}
