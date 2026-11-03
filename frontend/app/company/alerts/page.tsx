import type { Metadata } from "next";
import { CompanyAlertsScreen } from "@/components/company/CompanyScreens";

export const metadata: Metadata = { title: "Alerts · FoodLens (demo)" };

export default function Page() {
  return <CompanyAlertsScreen />;
}
