"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import {
  ArrowLeftRight,
  CalendarX2,
  CircleHelp,
  ScrollText,
  SearchX,
  Send,
  type LucideIcon,
} from "lucide-react";
import { DemoDataBanner } from "@/components/DemoDataBanner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { describeError } from "@/lib/api";
import { canOrder, useCurrentUser } from "@/lib/auth";
import {
  useSupplier,
  type RegistrationResult,
  type SupplierDetail,
} from "@/lib/companies";
import { usePlaceOrder, type OrderRequest } from "@/lib/orders";
import { cn } from "@/lib/utils";
import { SupplierCard, SupplierCardSkeleton } from "./SupplierDirectory";

/** Same tones as lookup results (D104): ink for a register match, amber to look at again, grey
 *  for no number. Never green or red; each badge has an icon and its label. */
const badgeStyles: Record<RegistrationResult, { icon: LucideIcon; className: string }> = {
  ACTIVE_IN_DEMO_REGISTER: {
    icon: ScrollText,
    className: "border-primary/30 bg-secondary text-secondary-foreground",
  },
  EXPIRED_OR_INACTIVE_IN_DEMO_REGISTER: {
    icon: CalendarX2,
    className: "border-notice/30 bg-notice-soft text-notice-strong",
  },
  REGISTERED_TO_ANOTHER_PRODUCT: {
    icon: ArrowLeftRight,
    className: "border-notice/30 bg-notice-soft text-notice-strong",
  },
  NOT_FOUND_IN_DEMO_REGISTER: {
    icon: SearchX,
    className: "border-notice/30 bg-notice-soft text-notice-strong",
  },
  NO_NUMBER_GIVEN: { icon: CircleHelp, className: "border-border bg-muted text-muted-foreground" },
};

function RegistrationBadge({ result, label }: { result: RegistrationResult; label: string }) {
  const { icon: Icon, className } = badgeStyles[result];
  return (
    <span
      className={cn(
        "inline-flex w-fit items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold",
        className,
      )}
    >
      <Icon aria-hidden="true" className="size-3.5 shrink-0" />
      {label}
    </span>
  );
}

type LineDraft = { quantity: string; unit: string };

const choiceClass =
  "flex min-h-11 items-center gap-3 rounded-lg border border-input bg-card px-3 has-checked:border-primary has-checked:bg-secondary";

/** Order request to this supplier. Shown only to approved wholesaler/both members; the server
 *  checks the same rules (D95-D97). No prices or payment (rule 6). */
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
      <p
        role="status"
        className="rounded-xl border border-primary/30 bg-secondary p-4 text-secondary-foreground"
      >
        Order request sent to {supplier.display_name}. Track it in{" "}
        <Link href="/orders" className="font-semibold underline">
          My orders
        </Link>
        .
      </p>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      aria-label="Request an order"
      className="flex flex-col gap-5 rounded-xl border border-border bg-card p-4 sm:p-5"
    >
      <div>
        <h2 className="text-xl font-bold">Request an order</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          This is a request only. The supplier accepts or declines it; FoodLens takes no payment.
        </p>
      </div>
      <fieldset className="flex flex-col gap-3">
        <legend className="mb-2 font-semibold">Products</legend>
        {supplier.products.map((product) => (
          <div
            key={product.product_id}
            className="grid grid-cols-2 items-end gap-2 rounded-lg bg-muted p-3 sm:grid-cols-[1fr_7rem_8rem]"
          >
            <span className="col-span-2 font-medium sm:col-span-1 sm:self-center">{product.name}</span>
            <label className="flex flex-col gap-1 text-sm text-muted-foreground">
              Quantity
              <Input
                aria-label={`Quantity of ${product.name}`}
                inputMode="decimal"
                value={lines[product.product_id]?.quantity ?? ""}
                onChange={(e) => setLine(product.product_id, { quantity: e.target.value })}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm text-muted-foreground">
              Unit
              <Input
                aria-label={`Unit for ${product.name}`}
                value={lines[product.product_id]?.unit ?? "carton"}
                onChange={(e) => setLine(product.product_id, { unit: e.target.value })}
              />
            </label>
          </div>
        ))}
      </fieldset>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 font-semibold">Pickup or delivery</legend>
        <label className={choiceClass}>
          <input
            type="radio"
            name="method"
            checked={method === "PICKUP"}
            onChange={() => setMethod("PICKUP")}
            className="size-4 accent-primary"
          />
          Pickup from the supplier
        </label>
        {method === "PICKUP" && (
          <NativeSelect
            aria-label="Pickup location"
            value={locationId}
            onChange={(e) => setLocationId(e.target.value)}
          >
            {supplier.locations.map((location) => (
              <option key={location.location_id} value={location.location_id}>
                {location.name} ({location.area})
              </option>
            ))}
          </NativeSelect>
        )}
        <label className={choiceClass}>
          <input
            type="radio"
            name="method"
            checked={method === "DELIVERY"}
            onChange={() => setMethod("DELIVERY")}
            className="size-4 accent-primary"
          />
          Delivery
        </label>
        {method === "DELIVERY" && (
          <Textarea
            aria-label="Delivery address or notes"
            value={delivery}
            maxLength={500}
            onChange={(e) => setDelivery(e.target.value)}
          />
        )}
      </fieldset>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="buyer-note">Note to the supplier (optional)</Label>
        <Textarea id="buyer-note" value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />
      </div>

      {(problem || placeOrder.isError) && (
        <Alert variant="destructive" role="alert">
          <AlertDescription>
            {problem ?? (placeOrder.error ? describeError(placeOrder.error) : null)}
          </AlertDescription>
        </Alert>
      )}
      <Button
        type="submit"
        size="lg"
        disabled={placeOrder.isPending}
        className="w-full sm:w-auto sm:self-start"
      >
        <Send aria-hidden="true" />
        {placeOrder.isPending ? "Sending…" : "Send order request"}
      </Button>
    </form>
  );
}

export function SupplierPageSkeleton() {
  return (
    <div role="status" aria-label="Loading supplier" className="flex flex-col gap-6">
      <SupplierCardSkeleton />
      <Skeleton className="h-8 w-40" />
      <div className="grid gap-3 sm:grid-cols-2">
        <Skeleton className="h-28" />
        <Skeleton className="h-28" />
      </div>
    </div>
  );
}

export function SupplierPage({ companyId }: { companyId: string }) {
  const supplier = useSupplier(companyId);
  const { data: user } = useCurrentUser();

  if (supplier.isError) {
    return (
      <Alert variant="destructive" role="alert">
        <AlertDescription>{describeError(supplier.error)}</AlertDescription>
      </Alert>
    );
  }
  if (!supplier.data) return <SupplierPageSkeleton />;
  const data = supplier.data;
  const buyerCompanyId = user?.membership?.company_id;
  const ownCompany = buyerCompanyId === data.company_id;

  return (
    <div className="flex flex-col gap-8">
      <ul>
        <SupplierCard supplier={data} />
      </ul>

      <section aria-labelledby="products-heading" className="flex flex-col gap-3">
        <h2 id="products-heading" className="text-2xl font-bold">
          Products
        </h2>
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          <DemoDataBanner />
          <p className="p-4 text-sm text-muted-foreground">{data.disclaimer}</p>
        </div>
        {data.products.length === 0 ? (
          <p className="rounded-xl border border-dashed border-input p-6 text-center text-muted-foreground">
            No published products yet.
          </p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2">
            {data.products.map((product) => (
              <li
                key={product.product_id}
                aria-label={product.name}
                className="flex flex-col gap-2 rounded-xl border border-border bg-card p-4"
              >
                <p className="font-semibold">{product.name}</p>
                <p className="text-sm text-muted-foreground">
                  {product.brand} · {product.category}
                  {product.package_size && ` · ${product.package_size}`}
                </p>
                <p className="text-sm">
                  Number on the pack:{" "}
                  <span className="font-mono">{product.registration_number ?? "none given"}</span>
                </p>
                <RegistrationBadge
                  result={product.registration_result}
                  label={product.registration_label}
                />
              </li>
            ))}
          </ul>
        )}
      </section>

      {data.products.length > 0 && !ownCompany && buyerCompanyId && canOrder(user) ? (
        <OrderRequestForm supplier={data} buyerCompanyId={buyerCompanyId} />
      ) : (
        !ownCompany && (
          <p className="rounded-xl bg-muted p-4 text-sm">
            Members of FoodLens-approved wholesaler companies can request orders here.{" "}
            {!user && (
              <Link href="/login" className="font-semibold text-primary underline">
                Sign in
              </Link>
            )}
          </p>
        )
      )}
    </div>
  );
}
