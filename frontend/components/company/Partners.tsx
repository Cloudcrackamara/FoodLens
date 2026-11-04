"use client";

import { cellClass, DataTable, numberCellClass } from "@/components/ui/DataTable";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/Panels";
import { describeError } from "@/lib/api";
import { companyTypeLabel } from "@/lib/companies";
import { usePartners } from "@/lib/dashboards";

/** Companies that recorded this manufacturer's packs, derived from events (D144). */
export function Partners({ companyId }: { companyId: string }) {
  const partners = usePartners(companyId);

  if (partners.isPending) return <LoadingPanel />;
  if (partners.isError) return <ErrorPanel onRetry={() => partners.refetch()}>{describeError(partners.error)}</ErrorPanel>;
  if (partners.data.length === 0) {
    return <EmptyPanel title="No partners yet. Companies appear here once they record your packs." />;
  }
  return (
    <DataTable label="Partners" head={["Company", "Type", "Places", "Received", "Sold", "POS link"]}>
      {partners.data.map((partner) => (
        <tr key={partner.display_name}>
          <td className={`${cellClass} font-semibold text-ink`}>{partner.display_name}</td>
          <td className={cellClass}>{companyTypeLabel(partner)}</td>
          <td className={cellClass}>{partner.places.join(", ") || "—"}</td>
          <td className={numberCellClass}>{partner.received}</td>
          <td className={numberCellClass}>{partner.sold}</td>
          <td className={cellClass}>{partner.pos_partners.join(", ") || "—"}</td>
        </tr>
      ))}
    </DataTable>
  );
}
