"use client";

import { useState } from "react";
import { OrderCard } from "@/components/orders/OrderCard";
import { describeError } from "@/lib/api";
import { useProducts } from "@/lib/catalogue";
import { useOrderAction, useOrders, type Order } from "@/lib/orders";
import { buttonVariants } from "@/components/ui/button";

type Mode = "idle" | "decline" | "reply" | "fulfil";

function SellerActions({ order, companyId }: { order: Order; companyId: string }) {
  const action = useOrderAction(companyId);
  const products = useProducts(companyId);
  const [mode, setMode] = useState<Mode>("idle");
  const [text, setText] = useState("");
  const [picked, setPicked] = useState<Record<string, string[]>>({});

  const run = (request: Parameters<typeof action.mutate>[0]) =>
    action.mutate(request, { onSuccess: () => { setMode("idle"); setText(""); } });
  const id = order.order_id;

  function toggle(lineId: string, batchId: string) {
    setPicked((current) => {
      const chosen = current[lineId] ?? [];
      return {
        ...current,
        [lineId]: chosen.includes(batchId) ? chosen.filter((b) => b !== batchId) : [...chosen, batchId],
      };
    });
  }

  const canReply = order.status === "REQUESTED" || order.status === "ACCEPTED";
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2 text-sm">
        {order.status === "REQUESTED" && (
          <>
            <button type="button" disabled={action.isPending} onClick={() => run({ orderId: id, action: "accept" })}
              className={buttonVariants({ size: "sm" })}>Accept</button>
            <button type="button" onClick={() => setMode("decline")} className={buttonVariants({ variant: "outline", size: "sm" })}>Decline</button>
          </>
        )}
        {order.status === "ACCEPTED" && (
          <button type="button" onClick={() => setMode("fulfil")} className={buttonVariants({ size: "sm" })}>Mark fulfilled</button>
        )}
        {canReply && <button type="button" onClick={() => setMode("reply")} className={buttonVariants({ variant: "outline", size: "sm" })}>Reply</button>}
      </div>

      {(mode === "decline" || mode === "reply") && (
        <div className="flex flex-col gap-2">
          <label className="flex flex-col gap-1 text-sm">
            {mode === "decline" ? "Reason (optional)" : "Message to the buyer"}
            <textarea value={text} maxLength={500} onChange={(e) => setText(e.target.value)}
              className="min-h-11 w-full rounded-lg border border-input bg-card px-3 py-2 text-base text-foreground outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/40" />
          </label>
          <div className="flex gap-2 text-sm">
            <button type="button" disabled={action.isPending || (mode === "reply" && !text.trim())}
              onClick={() => run(mode === "decline"
                ? { orderId: id, action: "decline", reason: text.trim() || null }
                : { orderId: id, action: "reply", message: text.trim() })}
              className={buttonVariants({ size: "sm" })}>
              {mode === "decline" ? "Confirm decline" : "Send reply"}
            </button>
            <button type="button" onClick={() => setMode("idle")} className="font-medium text-primary underline underline-offset-4 hover:no-underline">Back</button>
          </div>
        </div>
      )}

      {mode === "fulfil" && (
        <fieldset className="flex flex-col gap-2 text-sm">
          <legend className="font-medium">Which batches did you send? (optional)</legend>
          {order.lines.map((line) => {
            const batches = products.data?.find((p) => p.product_id === line.product_id)?.batches ?? [];
            return (
              <div key={line.line_id}>
                <p>{line.product_name}</p>
                {batches.length === 0 ? (
                  <p className="text-muted-foreground">No batches recorded for this product.</p>
                ) : (
                  batches.map((batch) => (
                    <label key={batch.batch_id} className="mr-3 inline-flex items-center gap-1">
                      <input type="checkbox" checked={(picked[line.line_id] ?? []).includes(batch.batch_id)}
                        onChange={() => toggle(line.line_id, batch.batch_id)} />
                      {batch.batch_number}
                    </label>
                  ))
                )}
              </div>
            );
          })}
          <div className="flex gap-2">
            <button type="button" disabled={action.isPending}
              onClick={() => run({
                orderId: id,
                action: "fulfil",
                allocations: Object.entries(picked)
                  .filter(([, ids]) => ids.length > 0)
                  .map(([line_id, batch_ids]) => ({ line_id, batch_ids })),
              })}
              className={buttonVariants({ size: "sm" })}>
              Confirm fulfilled
            </button>
            <button type="button" onClick={() => setMode("idle")} className="font-medium text-primary underline underline-offset-4 hover:no-underline">Back</button>
          </div>
        </fieldset>
      )}
      {action.isError && <p role="alert" className="text-destructive">{describeError(action.error)}</p>}
    </div>
  );
}

/** Seller side on /company: order requests received, with Accept / Decline / Reply / Fulfil. */
export function IncomingOrders({ companyId }: { companyId: string }) {
  const orders = useOrders(companyId, "selling");

  return (
    <section aria-labelledby="incoming-orders-heading" className="flex flex-col gap-3">
      <h2 id="incoming-orders-heading" className="text-xl font-bold">Incoming orders</h2>
      <p className="text-sm text-muted-foreground">
        Order requests from wholesalers. FoodLens takes no payment; arrange that with the buyer.
      </p>
      {orders.isError && <p role="alert">{describeError(orders.error)}</p>}
      {orders.data?.length === 0 && <p>No order requests yet.</p>}
      {orders.data && orders.data.length > 0 && (
        <ul className="flex flex-col gap-3">
          {orders.data.map((order) => (
            <OrderCard key={order.order_id} order={order} perspective="seller">
              <SellerActions order={order} companyId={companyId} />
            </OrderCard>
          ))}
        </ul>
      )}
    </section>
  );
}
