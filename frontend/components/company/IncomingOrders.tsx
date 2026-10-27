"use client";

import { useState } from "react";
import { OrderCard } from "@/components/orders/OrderCard";
import { describeError } from "@/lib/api";
import { useProducts } from "@/lib/catalogue";
import { useOrderAction, useOrders, type Order } from "@/lib/orders";
import { buttonClass } from "@/lib/ui";
import { EmptyPanel, ErrorPanel } from "@/components/ui/Panels";

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
              className={buttonClass("primary", "sm")}>Accept</button>
            <button type="button" onClick={() => setMode("decline")} className={buttonClass("secondary", "sm")}>Decline</button>
          </>
        )}
        {order.status === "ACCEPTED" && (
          <button type="button" onClick={() => setMode("fulfil")} className={buttonClass("primary", "sm")}>Mark fulfilled</button>
        )}
        {canReply && <button type="button" onClick={() => setMode("reply")} className={buttonClass("secondary", "sm")}>Reply</button>}
      </div>

      {(mode === "decline" || mode === "reply") && (
        <div className="flex flex-col gap-2">
          <label className="flex flex-col gap-1 text-sm">
            {mode === "decline" ? "Reason (optional)" : "Message to the buyer"}
            <textarea value={text} maxLength={500} onChange={(e) => setText(e.target.value)}
              className="min-h-[46px] rounded-[10px] border border-line-input bg-white px-3 text-base text-ink" />
          </label>
          <div className="flex gap-2 text-sm">
            <button type="button" disabled={action.isPending || (mode === "reply" && !text.trim())}
              onClick={() => run(mode === "decline"
                ? { orderId: id, action: "decline", reason: text.trim() || null }
                : { orderId: id, action: "reply", message: text.trim() })}
              className={buttonClass("primary", "sm")}>
              {mode === "decline" ? "Confirm decline" : "Send reply"}
            </button>
            <button type="button" onClick={() => setMode("idle")} className="font-semibold text-brand-dark underline">Back</button>
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
                  <p className="text-text-subtle">No batches recorded for this product.</p>
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
              className={buttonClass("primary", "sm")}>
              Confirm fulfilled
            </button>
            <button type="button" onClick={() => setMode("idle")} className="font-semibold text-brand-dark underline">Back</button>
          </div>
        </fieldset>
      )}
      {action.isError && <p role="alert" className="font-semibold text-bad">{describeError(action.error)}</p>}
    </div>
  );
}

/** Seller side on /company: order requests received, with Accept / Decline / Reply / Fulfil. */
export function IncomingOrders({ companyId }: { companyId: string }) {
  const orders = useOrders(companyId, "selling");

  return (
    <section aria-labelledby="incoming-orders-heading" className="flex flex-col gap-3">
      <h2 id="incoming-orders-heading" className="font-heading text-[17px] font-semibold text-ink">Incoming orders</h2>
      <p className="text-sm text-text-muted">
        Order requests from wholesalers. FoodLens takes no payment; arrange that with the buyer.
      </p>
      {orders.isError && <ErrorPanel>{describeError(orders.error)}</ErrorPanel>}
      {orders.data?.length === 0 && <EmptyPanel title="No order requests yet." />}
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
