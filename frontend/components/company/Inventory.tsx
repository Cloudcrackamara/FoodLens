"use client";

import { cellClass, DataTable, numberCellClass } from "@/components/ui/DataTable";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/Panels";
import { describeError } from "@/lib/api";
import { useInventory, type InventoryRow } from "@/lib/dashboards";
import { cardTitleClass } from "@/lib/ui";

// Approved wording (3 Nov 2026).
function destination(row: InventoryRow): string {
  if (row.not_allocated) return "Not allocated";
  return [row.company_name, row.area].filter(Boolean).join(" · ");
}

/** Allocated, received, in stock, sold and returned per destination (D142, D154). */
export function Inventory({ companyId, batchId }: { companyId: string; batchId: string }) {
  const inventory = useInventory(companyId, batchId);

  return (
    <section aria-labelledby="inventory-heading" className="flex flex-col gap-3">
      <h2 id="inventory-heading" className={`m-0 ${cardTitleClass}`}>Inventory by destination</h2>
      {inventory.isPending && <LoadingPanel />}
      {inventory.isError && <ErrorPanel onRetry={() => inventory.refetch()}>{describeError(inventory.error)}</ErrorPanel>}
      {inventory.data?.length === 0 && <EmptyPanel title="No stock recorded yet." />}
      {inventory.data && inventory.data.length > 0 && (
        <DataTable
          label="Inventory by destination"
          head={["Destination", "Allocated", "Received", "In stock", "Sold", "Returned"]}
        >
          {inventory.data.map((row) => (
            <tr key={destination(row)}>
              <td className={cellClass}>{destination(row)}</td>
              <td className={numberCellClass}>{row.allocated}</td>
              <td className={numberCellClass}>{row.received}</td>
              <td className={numberCellClass}>{row.in_stock}</td>
              <td className={numberCellClass}>{row.sold}</td>
              <td className={numberCellClass}>{row.returned}</td>
            </tr>
          ))}
        </DataTable>
      )}
    </section>
  );
}
