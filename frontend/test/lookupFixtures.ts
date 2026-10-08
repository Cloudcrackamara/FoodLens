import type { LookupResponse } from "@/lib/lookup";

// Shapes match backend/app/schemas/lookup.py; wording copied from backend/app/services/lookup.py.
const disclaimer =
  "DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE. FoodLens compares what you entered with " +
  "fictional demonstration records. It is not a laboratory or food-safety test, it does not " +
  "check the package in your hand, and it is not a NAFDAC or SON decision.";
const credentialScopeNote =
  "Credentials shown are product-level records in the demo data. They apply to the product in " +
  "general, not to this batch, and are not a batch certificate or a test result.";

const product = {
  product_code: "DEMO-PC-0001",
  name: "Sample Palm Oil",
  brand: "Demo Harvest Foods",
  category: "Oils",
  package_size: "1 L",
  manufacturer_name: "Demo Harvest Foods (fictional) Ltd",
  company_display_name: "Demo Harvest Foods (fictional)",
};
const batch = {
  batch_number: "DEMO-LOT-101",
  production_date: "2026-04-01",
  expiry_date: "2027-11-12",
};
const nafdac = {
  agency: "NAFDAC (simulated)",
  scheme: "Food product registration (demo)",
  reference_number: "DEMO-NAFDAC-0001",
  scope: "PRODUCT" as const,
  status: "ACTIVE_IN_DEMO_DATA" as const,
  valid_from: "2025-05-26",
  valid_until: "2027-11-12",
  data_mode: "DEMO" as const,
  provenance: "Fictional record created for the FoodLens capstone demo. Not from any regulator.",
  checked_on: "2026-10-08",
};

function base(overrides: Partial<LookupResponse>): LookupResponse {
  return {
    result: "DEMO_RECORD_FOUND",
    data_mode: "DEMO",
    disclaimer,
    title: "Demo record found",
    message: "",
    warnings: [],
    input: { product_code: "DEMO-PC-0001", batch_number: "DEMO-LOT-101" },
    mismatch: null,
    product: null,
    batch: null,
    credentials: [],
    credential_scope_note: credentialScopeNote,
    candidates: [],
    ...overrides,
  };
}

export const lookupFixtures: Record<LookupResponse["result"], LookupResponse> = {
  DEMO_RECORD_FOUND: base({
    message:
      "A matching product and batch record was found in the FoodLens demonstration dataset, " +
      "with at least one active product-level credential record.",
    product,
    batch,
    credentials: [nafdac],
  }),
  BATCH_NOT_FOUND: base({
    result: "BATCH_NOT_FOUND",
    title: "No match in demo data",
    message:
      "No matching batch was found in the FoodLens demonstration dataset. This only means the " +
      "batch is not in the demo data; it says nothing about the product itself.",
  }),
  BATCH_EXPIRED: base({
    result: "BATCH_EXPIRED",
    title: "Batch expiry date has passed in demo data",
    message:
      "A matching record was found, but the expiry date stored for this batch in the demo data " +
      "has passed.",
    product,
    batch: { ...batch, expiry_date: "2026-08-09" },
    credentials: [nafdac],
  }),
  DETAILS_MISMATCH: base({
    result: "DETAILS_MISMATCH",
    title: "Details do not match",
    message:
      "This batch number is recorded in the demo data under a different product code. Check " +
      "the product code and batch number printed on the package.",
    mismatch: { field: "product_code" },
  }),
  CREDENTIAL_EXPIRED_OR_INACTIVE: base({
    result: "CREDENTIAL_EXPIRED_OR_INACTIVE",
    title: "Credential shown as expired or inactive in demo data",
    message:
      "The product and batch were found. The credential records stored for this product are " +
      "expired or inactive in the demo data. This is the status of the stored demo record, not " +
      "an official enforcement result.",
    product,
    batch,
    credentials: [{ ...nafdac, status: "EXPIRED_IN_DEMO_DATA", valid_until: "2026-08-09" }],
  }),
  INSUFFICIENT_OR_AMBIGUOUS: base({
    result: "INSUFFICIENT_OR_AMBIGUOUS",
    title: "More details needed",
    message: "Enter the product code too. If your product is listed below, choose it to continue.",
    input: { product_code: null, batch_number: "DEMO-LOT-001" },
    candidates: [
      { product_code: "DEMO-PC-0001", name: "Sample Palm Oil", brand: "Demo Harvest Foods" },
      { product_code: "DEMO-PC-0002", name: "Sample Groundnut Oil", brand: "Demo Harvest Foods" },
    ],
  }),
};
