import type { Metadata } from "next";
import { AdminQueuesScreen } from "@/components/admin/AdminScreens";

export const metadata: Metadata = { title: "Review queues · FoodLens (demo)" };

export default function Page() {
  return <AdminQueuesScreen />;
}
