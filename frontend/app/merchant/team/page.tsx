import type { Metadata } from "next";
import { MerchantTeamScreen } from "@/components/merchant/MerchantShell";

export const metadata: Metadata = { title: "Team · FoodLens (demo)" };

export default function TeamRoute() {
  return <MerchantTeamScreen />;
}
