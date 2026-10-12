import type { SupplierDetail } from "@/lib/companies";
import type { Order } from "@/lib/orders";
import { demoUser } from "./utils";
import { supplier } from "./companyFixtures";

export const buyerCompanyId = "66666666-6666-6666-6666-666666666666";

export const wholesalerUser = {
  ...demoUser,
  membership: {
    company_id: buyerCompanyId,
    company_display_name: "Demo Market Traders (fictional)",
    company_review_status: "APPROVED",
    company_type: "WHOLESALER",
    role: "OWNER",
  },
};

export const manufacturerUser = {
  ...wholesalerUser,
  membership: { ...wholesalerUser.membership, company_type: "MANUFACTURER" },
};

const product = {
  brand: "Demo Harvest",
  category: "Oils",
  package_size: "1 L",
  register_name: "simulated NAFDAC register",
};

export const supplierDetail: SupplierDetail = {
  ...supplier,
  data_mode: "DEMO",
  disclaimer:
    "DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE. Registration results come from a simulated, " +
    "fictional register held by FoodLens, not NAFDAC's or SON's own system.",
  products: [
    { ...product, product_id: "p-oil", name: "Sample Palm Oil", registration_number: "DEMO-NAFDAC-0001", registration_result: "ACTIVE_IN_DEMO_REGISTER", registration_label: "Active in the simulated register (demo data)" },
    { ...product, product_id: "p-paste", name: "Sample Tomato Paste", registration_number: "DEMO-NAFDAC-0003", registration_result: "EXPIRED_OR_INACTIVE_IN_DEMO_REGISTER", registration_label: "Expired or inactive in the simulated register (demo data)" },
    { ...product, product_id: "p-honey", name: "Sample Honey", registration_number: "DEMO-NAFDAC-9999", registration_result: "NOT_FOUND_IN_DEMO_REGISTER", registration_label: "Not found in the simulated register (demo data)", register_name: null },
    { ...product, product_id: "p-cocoa", name: "Sample Cocoa", registration_number: "DEMO-NAFDAC-0009", registration_result: "REGISTERED_TO_ANOTHER_PRODUCT", registration_label: "Number belongs to a different product or company in the simulated register (demo data)" },
    { ...product, product_id: "p-yam", name: "Sample Yam Flour", registration_number: null, registration_result: "NO_NUMBER_GIVEN", registration_label: "No registration number given by the company", register_name: null },
  ],
};

export const requestedOrder: Order = {
  order_id: "o-1",
  status: "REQUESTED",
  buyer: { company_id: buyerCompanyId, display_name: "Demo Market Traders (fictional)" },
  seller: { company_id: supplier.company_id, display_name: supplier.display_name },
  fulfilment_method: "PICKUP",
  pickup_location: {
    location_id: supplier.locations[0].location_id,
    name: supplier.locations[0].name,
    address: "12 Sample Road",
    area: "Ikeja, Lagos",
  },
  delivery_details: null,
  buyer_note: "Weekly restock",
  seller_note: null,
  lines: [
    {
      line_id: "l-1",
      product_id: "p-oil",
      product_name: "Sample Palm Oil",
      product_code: "DEMO-PC-0001",
      quantity: "20.000",
      unit: "carton",
      batches: [],
    },
  ],
  created_at: "2026-10-12T10:00:00Z",
  updated_at: "2026-10-12T10:00:00Z",
};

export const acceptedOrder: Order = {
  ...requestedOrder,
  order_id: "o-2",
  status: "ACCEPTED",
  seller_note: "Ready on Friday",
};
