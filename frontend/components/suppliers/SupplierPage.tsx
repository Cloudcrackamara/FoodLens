"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { DemoDataBanner } from "@/components/DemoDataBanner";
import { describeError } from "@/lib/api";
import { canOrder, useCurrentUser } from "@/lib/auth";
import { useSupplier, type SupplierDetail } from "@/lib/companies";
import { ordersEnabled } from "@/lib/features";
import { usePlaceOrder, type OrderRequest } from "@/lib/orders";
import { SupplierCard } from "./SupplierDirectory";

type LineDraft = { quantity: string; unit: string };

/** Order request to this supplier. Shown only to approved distributor members while orders are
 *  enabled (D127); the server checks the same rules (D95-D97). No prices or payment (rule 7). */
export function OrderRequestForm({
  supplier,
  buyerCompanyId,
}: {
  supplier: SupplierDetail;
  buyerCompanyId: string;
}) {
  const placeOrder = usePlaceOrder(buyerCompanyId);
  const [lines, setLines] = useState<Record<string, LineDraft>>({});
  const [method, setMethod] = useState<"PICKUP" | "DELIVERY">("PICKUP");
  const [locationId, setLocationId] = useState(supplier.locations[0]?.location_id ?? "");
  const [delivery, setDelivery] = useState("");
  const [note, setNote] = useState("");
  const [problem, setProblem] = useState<string | null>(null);

  function setLine(productId: string, change: Partial<LineDraft>) {
    setLines((current) => ({
      ...current,
      [productId]: { ...(current[productId] ?? { quantity: "", unit: "carton" }), ...change },
    }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setProblem(null);
    const chosen = Object.entries(lines).filter(([, line]) => line.quantity.trim() !== "");
    if (chosen.length === 0) return setProblem("Enter a quantity for at least one product.");
    if (chosen.some(([, line]) => !(Number(line.quantity) > 0))) {
      return setProblem("Quantities must be more than zero.");
    }
    if (chosen.some(([, line]) => !line.unit.trim())) {
      return setProblem("Enter a unit, such as carton or bag, for each product.");
    }
    if (method === "DELIVERY" && delivery.trim().length < 5) {
      return setProblem("Enter a delivery address or delivery notes.");
    }
    const body: OrderRequest = {
      lines: chosen.map(([productId, line]) => ({
        product_id: productId,
        quantity: line.quantity.trim(),
        unit: line.unit.trim(),
      })),
      fulfilment_method: method,
      pickup_location_id: method === "PICKUP" ? locationId : null,
      delivery_details: method === "DELIVERY" ? delivery.trim() : null,
      buyer_note: note.trim() || null,
    };
    placeOrder.mutate(body);
  }

  if (placeOrder.isSuccess) {
    return (
      <p role="status" className="rounded-md border border-zinc-400 p-4">
        Order request sent to {supplier.display_name}. Track it in{" "}
        <Link href="/orders" className="underline">My orders</Link>.
      </p>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate aria-label="Request an order" className="flex flex-col gap-4 rounded-md border border-zinc-300 p-4 dark:border-zinc-700">
      <h2 className="text-lg font-semibold">Request an order</h2>
      <p className="text-sm text-zinc-700 dark:text-zinc-300">
        This is a request only. The supplier accepts or declines it; FoodLens takes no payment.
      </p>
      <fieldset className="flex flex-col gap-2">
        <legend className="font-medium">Products</legend>
        {supplier.products.map((product) => (
          <div key={product.product_id} className="flex flex-wrap items-end gap-2">
            <span className="min-w-40 flex-1">{product.name}</span>
            <label className="flex flex-col text-sm">
              Quantity
              <input aria-label={`Quantity of ${product.name}`} inputMode="decimal" value={lines[product.product_id]?.quantity ?? ""}
                onChange={(e) => setLine(product.product_id, { quantity: e.target.value })}
                className="w-24 rounded-md border border-zinc-400 px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900" />
            </label>
            <label className="flex flex-col text-sm">
              Unit
              <input aria-label={`Unit for ${product.name}`} value={lines[product.product_id]?.unit ?? "carton"}
                onChange={(e) => setLine(product.product_id, { unit: e.target.value })}
                className="w-28 rounded-md border border-zinc-400 px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900" />
            </label>
          </div>
        ))}
      </fieldset>

      <fieldset className="flex flex-col gap-2">
        <legend className="font-medium">Pickup or delivery</legend>
        <label className="flex items-center gap-2">
          <input type="radio" name="method" checked={method === "PICKUP"} onChange={() => setMethod("PICKUP")} />
          Pickup from the supplier
        </label>
        {method === "PICKUP" && (
          <select aria-label="Pickup location" value={locationId} onChange={(e) => setLocationId(e.target.value)}
            className="rounded-md border border-zinc-400 px-2 py-2 dark:border-zinc-600 dark:bg-zinc-900">
            {supplier.locations.map((location) => (
              <option key={location.location_id} value={location.location_id}>
                {location.name} ({location.area})
              </option>
            ))}
          </select>
        )}
        <label className="flex items-center gap-2">
          <input type="radio" name="method" checked={method === "DELIVERY"} onChange={() => setMethod("DELIVERY")} />
          Delivery
        </label>
        {method === "DELIVERY" && (
          <textarea aria-label="Delivery address or notes" value={delivery} maxLength={500} onChange={(e) => setDelivery(e.target.value)}
            className="rounded-md border border-zinc-400 px-2 py-2 dark:border-zinc-600 dark:bg-zinc-900" />
        )}
      </fieldset>

      <label className="flex flex-col gap-1">
        <span className="font-medium">Note to the supplier (optional)</span>
        <textarea value={note} maxLength={500} onChange={(e) => setNote(e.target.value)}
          className="rounded-md border border-zinc-400 px-2 py-2 dark:border-zinc-600 dark:bg-zinc-900" />
      </label>

      {(problem || placeOrder.isError) && (
        <p role="alert" className="text-red-700 dark:text-red-400">
          {problem ?? (placeOrder.error ? describeError(placeOrder.error) : null)}
        </p>
      )}
      <button type="submit" disabled={placeOrder.isPending}
        className="rounded-md bg-zinc-900 px-4 py-2 font-semibold text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900">
        {placeOrder.isPending ? "Sending…" : "Send order request"}
      </button>
    </form>
  );
}

export function SupplierPage({ companyId }: { companyId: string }) {
  const supplier = useSupplier(companyId);
  const { data: user } = useCurrentUser();

  if (supplier.isError) {
    return <p role="alert">{describeError(supplier.error)}</p>;
  }
  if (!supplier.data) return <p>Loading…</p>;
  const data = supplier.data;
  const buyerCompanyId = user?.membership?.company_id;
  const ownCompany = buyerCompanyId === data.company_id;

  return (
    <div className="flex flex-col gap-6">
      <ul>
        <SupplierCard supplier={data} />
      </ul>

      <section aria-labelledby="products-heading" className="flex flex-col gap-3">
        <h2 id="products-heading" className="text-lg font-semibold">Products</h2>
        <DemoDataBanner />
        <p className="text-sm text-zinc-700 dark:text-zinc-300">{data.disclaimer}</p>
        {data.products.length === 0 ? (
          <p>No published products yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {data.products.map((product) => (
              <li key={product.product_id} aria-label={product.name} className="rounded-md border border-zinc-200 p-3 dark:border-zinc-800">
                <p className="font-medium">{product.name}</p>
                <p className="text-sm">
                  {product.brand} · {product.category}
                  {product.size && ` · ${product.size}`}
                </p>
                <p className="text-sm">
                  NAFDAC number (as printed): {product.registration_number ?? "none given"}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {data.products.length > 0 && !ownCompany && buyerCompanyId && canOrder(user) ? (
        <OrderRequestForm supplier={data} buyerCompanyId={buyerCompanyId} />
      ) : (
        ordersEnabled &&
        !ownCompany && (
          <p className="text-sm">
            Members of FoodLens-approved distributor companies can request orders here.{" "}
            {!user && <Link href="/login" className="underline">Sign in</Link>}
          </p>
        )
      )}
    </div>
  );
}
