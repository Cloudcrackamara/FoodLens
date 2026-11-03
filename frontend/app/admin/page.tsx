import type { Metadata } from "next";
import { AdminOverviewScreen } from "@/components/admin/AdminScreens";

export const metadata: Metadata = { title: "Overview · FoodLens (demo)" };

export default function Page() {
  return <AdminOverviewScreen />;
}
