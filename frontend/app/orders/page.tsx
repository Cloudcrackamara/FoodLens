import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { MyOrders } from "@/components/orders/MyOrders";
import { ordersEnabled } from "@/lib/features";

export const metadata: Metadata = { title: "My orders · FoodLens (demo)" };

export default function OrdersPage() {
  // Order requests are hidden future work (D127).
  if (!ordersEnabled) notFound();
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-4 py-8">
      <div>
        <h1 className="text-2xl font-bold">My orders</h1>
        <p className="mt-2 text-zinc-700 dark:text-zinc-300">
          Order requests your company sent to suppliers. These are requests only: FoodLens takes
          no payment and does not track deliveries.
        </p>
      </div>
      <MyOrders />
    </main>
  );
}
