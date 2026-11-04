import type { Metadata } from "next";
import { AdminStatsScreen } from "@/components/admin/AdminScreens";

export const metadata: Metadata = { title: "Platform stats · FoodLens (demo)" };

export default function Page() {
  return <AdminStatsScreen />;
}
