/** Wholesale order requests are hidden future work (D127). The backend registers the order
 *  routes only with ORDERS_ENABLED=true; this flag only decides what to show. */
export const ordersEnabled = process.env.NEXT_PUBLIC_ORDERS_ENABLED === "true";
