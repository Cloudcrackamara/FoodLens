import type { Metadata } from "next";
import { AdminReportsScreen } from "@/components/admin/AdminScreens";

export const metadata: Metadata = { title: "Consumer reports · FoodLens (demo)" };

export default function Page() {
  return <AdminReportsScreen />;
}
