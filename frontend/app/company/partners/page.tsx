import type { Metadata } from "next";
import { CompanyPartnersScreen } from "@/components/company/CompanyScreens";

export const metadata: Metadata = { title: "Partners · FoodLens (demo)" };

export default function Page() {
  return <CompanyPartnersScreen />;
}
