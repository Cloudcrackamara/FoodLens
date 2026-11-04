import type { Metadata } from "next";
import { CheckPack } from "@/components/check/CheckPack";

export const metadata: Metadata = { title: "Check a pack · FoodLens (demo)" };

/** Free consumer check, no account: Scan QR or Type code (D141). CheckPack draws the whole screen. */
export default function CheckPage() {
  return <CheckPack />;
}
