import type { Metadata } from "next";
import { AdminScanningScreen } from "@/components/admin/AdminScreens";

export const metadata: Metadata = { title: "Automated scanning · FoodLens (demo)" };

export default function Page() {
  return <AdminScanningScreen />;
}
