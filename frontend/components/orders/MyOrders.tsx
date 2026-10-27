"use client";

import Link from "next/link";
import { describeError } from "@/lib/api";
import { canOrder, useCurrentUser } from "@/lib/auth";
import { useOrderAction, useOrders } from "@/lib/orders";
import { OrderCard } from "./OrderCard";
import { buttonClass } from "@/lib/ui";
import { ErrorPanel, LoadingPanel } from "@/components/ui/Panels";

function BuyerOrders({ companyId }: { companyId: string }) {
  const orders = useOrders(companyId, "buying");
  const action = useOrderAction(companyId);

  if (orders.isError) return <ErrorPanel>{describeError(orders.error)}</ErrorPanel>;
  if (!orders.data) return <LoadingPanel />;
  if (orders.data.length === 0) {
    return (
      <p>
        No order requests yet. Find a supplier in the{" "}
        <Link href="/suppliers" className="font-semibold text-brand-dark underline">partner directory</Link>.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {action.isError && <p role="alert" className="font-semibold text-bad">{describeError(action.error)}</p>}
      <ul className="flex flex-col gap-3">
        {orders.data.map((order) => (
          <OrderCard key={order.order_id} order={order} perspective="buyer">
            {order.status === "REQUESTED" && (
              <button type="button" disabled={action.isPending}
                onClick={() => action.mutate({ orderId: order.order_id, action: "cancel" })}
                className={`self-start ${buttonClass("secondary", "sm")}`}>
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
  if (isPending) return <LoadingPanel />;
  if (!user) {
    return (
      <p>
        <Link href="/login" className="font-semibold text-brand-dark underline">Sign in</Link> to see your order requests.
      </p>
    );
  }
  if (!user.membership || !canOrder(user)) {
    return <p>Order requests are for members of FoodLens-approved wholesaler companies.</p>;
  }
  return <BuyerOrders companyId={user.membership.company_id} />;
}
