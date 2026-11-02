import type { Metadata } from "next";
import { CompanyAlertsScreen } from "@/components/alerts/CompanyAlertsScreen";

export const metadata: Metadata = { title: "Alerts · FoodLens (demo)" };

/** The manufacturer's risk alerts (D125, D152). Full dashboards come in Phase 7. */
export default function CompanyAlertsRoute() {
  return <CompanyAlertsScreen />;
}
