import type { Metadata } from "next";
import { CompanyReportsScreen } from "@/components/company/CompanyScreens";

export const metadata: Metadata = { title: "Consumer reports · FoodLens (demo)" };

export default function Page() {
  return <CompanyReportsScreen />;
}
