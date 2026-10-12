"use client";

import Link from "next/link";
import { describeError } from "@/lib/api";
import { canOrder, useCurrentUser } from "@/lib/auth";
import { useOrderAction, useOrders } from "@/lib/orders";
import { OrderCard } from "./OrderCard";

function BuyerOrders({ companyId }: { companyId: string }) {
  const orders = useOrders(companyId, "buying");
  const action = useOrderAction(companyId);

  if (orders.isError) return <p role="alert">{describeError(orders.error)}</p>;
  if (!orders.data) return <p>Loading…</p>;
  if (orders.data.length === 0) {
    return (
      <p>
        No order requests yet. Find a supplier in the{" "}
        <Link href="/suppliers" className="underline">supplier directory</Link>.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {action.isError && <p role="alert" className="text-red-700 dark:text-red-400">{describeError(action.error)}</p>}
      <ul className="flex flex-col gap-3">
        {orders.data.map((order) => (
          <OrderCard key={order.order_id} order={order} perspective="buyer">
            {order.status === "REQUESTED" && (
              <button type="button" disabled={action.isPending}
                onClick={() => action.mutate({ orderId: order.order_id, action: "cancel" })}
                className="self-start rounded-md border border-zinc-600 px-3 py-1 text-sm">
                Cancel request
              </button>
            )}
          </OrderCard>
        ))}
      </ul>
    </div>
  );
}

/** "My orders" for wholesalers: requests they sent and their status. */
export function MyOrders() {
  const { data: user, isPending } = useCurrentUser();
  if (isPending) return <p>Loading…</p>;
  if (!user) {
    return (
      <p>
        <Link href="/login" className="underline">Sign in</Link> to see your order requests.
      </p>
    );
  }
  if (!user.membership || !canOrder(user)) {
    return <p>Order requests are for members of FoodLens-approved wholesaler companies.</p>;
  }
  return <BuyerOrders companyId={user.membership.company_id} />;
}
