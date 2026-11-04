/** Wholesale order requests are hidden future work (D127). The backend registers the order
 *  routes only with ORDERS_ENABLED=true; this flag only decides what to show. */
export const ordersEnabled = process.env.NEXT_PUBLIC_ORDERS_ENABLED === "true";

/** The simulated till at /demo/pos (D123). The backend registers its routes only with
 *  DEMO_POS_ENABLED=true; this flag only decides whether the page exists. */
export const demoPosEnabled = process.env.NEXT_PUBLIC_DEMO_POS_ENABLED === "true";
