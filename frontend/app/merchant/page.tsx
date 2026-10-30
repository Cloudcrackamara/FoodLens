import type { Metadata } from "next";
import { MerchantRecordScreen } from "@/components/merchant/MerchantShell";

export const metadata: Metadata = { title: "Record stock events · FoodLens (demo)" };

/** Mobile merchant page for approved distributors and retailers (owner and staff). */
export default function MerchantRoute() {
  return <MerchantRecordScreen />;
}
