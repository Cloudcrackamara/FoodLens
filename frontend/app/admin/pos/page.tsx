import type { Metadata } from "next";
import { AdminPosScreen } from "@/components/admin/AdminScreens";

export const metadata: Metadata = { title: "POS partners · FoodLens (demo)" };

export default function Page() {
  return <AdminPosScreen />;
}
