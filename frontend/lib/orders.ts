import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { apiFetch } from "./api";

// Mirrors backend/app/schemas/order.py. Order requests only: no prices or payments (rule 6).
const orderStatusValues = ["REQUESTED", "ACCEPTED", "DECLINED", "FULFILLED", "CANCELLED"] as const;
export type OrderStatus = (typeof orderStatusValues)[number];

export const orderStatusLabels: Record<OrderStatus, string> = {
  REQUESTED: "Requested",
  ACCEPTED: "Accepted",
  DECLINED: "Declined",
  FULFILLED: "Fulfilled",
  CANCELLED: "Cancelled",
};

const party = z.object({ company_id: z.string(), display_name: z.string() });

export const orderSchema = z.object({
  order_id: z.string(),
  status: z.enum(orderStatusValues),
  buyer: party,
  seller: party,
  fulfilment_method: z.enum(["PICKUP", "DELIVERY"]),
  pickup_location: z
    .object({ location_id: z.string(), name: z.string(), address: z.string(), area: z.string() })
    .nullable(),
  delivery_details: z.string().nullable(),
  buyer_note: z.string().nullable(),
  seller_note: z.string().nullable(),
  lines: z.array(
    z.object({
      line_id: z.string(),
      product_id: z.string(),
      product_name: z.string(),
      product_code: z.string(),
      quantity: z.string(),
      unit: z.string(),
      batches: z.array(
        z.object({
          batch_id: z.string(),
          batch_number: z.string(),
          expiry_date: z.string().nullable(),
        }),
      ),
    }),
  ),
  created_at: z.string(),
  updated_at: z.string(),
});
export type Order = z.infer<typeof orderSchema>;

/** What the order form sends. The buyer comes from the URL company, the seller from the
 *  products: no status, company, user, or payment fields (D95-D97). */
export type OrderRequest = {
  lines: { product_id: string; quantity: string; unit: string }[];
  fulfilment_method: "PICKUP" | "DELIVERY";
  pickup_location_id: string | null;
  delivery_details: string | null;
  buyer_note: string | null;
};

/** "10.000" -> "10", "2.500" -> "2.5". */
export function formatQuantity(value: string): string {
  return value.includes(".") ? value.replace(/0+$/, "").replace(/\.$/, "") : value;
}

const ordersKey = (companyId: string) => ["orders", companyId] as const;

export function useOrders(companyId: string, role: "buying" | "selling") {
  return useQuery({
    queryKey: [...ordersKey(companyId), role],
    queryFn: () =>
      apiFetch(`/api/companies/${companyId}/orders?role=${role}`, z.array(orderSchema)),
  });
}

export function usePlaceOrder(companyId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: OrderRequest) =>
      apiFetch(`/api/companies/${companyId}/orders`, orderSchema, { method: "POST", body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ordersKey(companyId) }),
  });
}

export type OrderAction =
  | { action: "accept" }
  | { action: "cancel" }
  | { action: "decline"; reason: string | null }
  | { action: "reply"; message: string }
  | { action: "fulfil"; allocations: { line_id: string; batch_ids: string[] }[] };

export function useOrderAction(companyId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orderId, ...request }: OrderAction & { orderId: string }) => {
      const { action, ...body } = request;
      return apiFetch(`/api/companies/${companyId}/orders/${orderId}/${action}`, orderSchema, {
        method: "POST",
        body,
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ordersKey(companyId) }),
  });
}
