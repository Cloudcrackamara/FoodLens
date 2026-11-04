import type { Metadata } from "next";
import { CompanyProductsScreen } from "@/components/company/CompanyScreens";

export const metadata: Metadata = { title: "Products and batches · FoodLens (demo)" };

export default function Page() {
  return <CompanyProductsScreen />;
}
