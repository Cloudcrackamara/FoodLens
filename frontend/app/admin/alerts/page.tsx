import type { Metadata } from "next";
import { AdminAlertsScreen } from "@/components/admin/AdminScreens";

export const metadata: Metadata = { title: "Alerts · FoodLens (demo)" };

export default function Page() {
  return <AdminAlertsScreen />;
}
