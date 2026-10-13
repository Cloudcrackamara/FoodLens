import type { Metadata } from "next";
import { MyOrders } from "@/components/orders/MyOrders";

export const metadata: Metadata = { title: "My orders · FoodLens (demo)" };

export default function OrdersPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-8 sm:py-10">
      <div>
        <h1 className="text-3xl font-bold leading-tight text-primary">My orders</h1>
        <p className="mt-2 text-muted-foreground">
          Order requests your company sent to suppliers. These are requests only: FoodLens takes
          no payment and does not track deliveries.
        </p>
      </div>
      <MyOrders />
    </main>
  );
}
