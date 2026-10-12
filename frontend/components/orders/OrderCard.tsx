"use client";

import type { ReactNode } from "react";
import { formatQuantity, orderStatusLabels, type Order } from "@/lib/orders";

/** One order, as seen by the buyer or the seller. No prices: order requests only. */
export function OrderCard({
  order,
  perspective,
  children,
}: {
  order: Order;
  perspective: "buyer" | "seller";
  children?: ReactNode;
}) {
  const other = perspective === "buyer" ? order.seller : order.buyer;
  return (
    <li aria-label={`Order from ${order.buyer.display_name} to ${order.seller.display_name}`}
      className="flex flex-col gap-2 rounded-md border border-zinc-300 p-4 dark:border-zinc-700">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold">
            {perspective === "buyer" ? "To" : "From"} {other.display_name}
          </p>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Sent {new Date(order.created_at).toLocaleDateString("en-GB")}
          </p>
        </div>
        <span className="rounded-full border border-zinc-500 px-3 py-1 text-xs font-semibold">
          {orderStatusLabels[order.status]}
        </span>
      </div>
      <ul className="text-sm">
        {order.lines.map((line) => (
          <li key={line.line_id}>
            {line.product_name}: {formatQuantity(line.quantity)} {line.unit}
            {line.batches.length > 0 && (
              <span className="text-zinc-600 dark:text-zinc-400">
                {" "}· batches {line.batches.map((b) => b.batch_number).join(", ")}
              </span>
            )}
          </li>
        ))}
      </ul>
      <p className="text-sm">
        {order.fulfilment_method === "PICKUP" && order.pickup_location
          ? `Pickup: ${order.pickup_location.name}, ${order.pickup_location.address}, ${order.pickup_location.area}`
          : `Delivery: ${order.delivery_details ?? ""}`}
      </p>
      {order.buyer_note && <p className="text-sm">Buyer note: {order.buyer_note}</p>}
      {order.seller_note && <p className="text-sm">Supplier message: {order.seller_note}</p>}
      {children}
    </li>
  );
}
