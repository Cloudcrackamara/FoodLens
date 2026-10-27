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
      className="flex flex-col gap-2 rounded-[12px] bg-white p-6 shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold">
            {perspective === "buyer" ? "To" : "From"} {other.display_name}
          </p>
          <p className="text-sm text-text-subtle">
            Sent {new Date(order.created_at).toLocaleDateString("en-GB")}
          </p>
        </div>
        <span className="inline-flex items-center rounded-full bg-neutral-bg px-2.5 py-0.5 text-sm font-bold text-neutral">
          {orderStatusLabels[order.status]}
        </span>
      </div>
      <ul className="text-sm">
        {order.lines.map((line) => (
          <li key={line.line_id}>
            {line.product_name}: {formatQuantity(line.quantity)} {line.unit}
            {line.batches.length > 0 && (
              <span className="text-text-subtle">
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
