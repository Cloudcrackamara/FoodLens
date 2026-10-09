import type { LookupResponse } from "@/lib/lookup";

// Shapes match backend/app/schemas/lookup.py; wording copied from backend/app/services/lookup.py.
const disclaimer =
  "DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE. FoodLens compares the number you entered " +
  "with a simulated, fictional register held by FoodLens. It is not NAFDAC's or SON's own " +
  "system, it is not a laboratory or food-safety test, and a matching number cannot rule out " +
  "a copied number on the pack.";

const record = {
  agency: "NAFDAC (simulated)",
  scheme: "Food product registration (demo)",
  registration_number: "DEMO-NAFDAC-0001",
  registered_product_name: "Sample Palm Oil",
  registered_company_name: "Demo Harvest Foods (fictional) Ltd",
  status: "ACTIVE_IN_DEMO_REGISTER" as const,
  expires_on: "2027-11-13",
  data_mode: "DEMO" as const,
  provenance:
    "Fictional record in the FoodLens simulated register for the capstone demo. Not from NAFDAC or SON.",
  last_checked_on: "2026-10-09",
};
const product = {
  name: "Sample Palm Oil",
  brand: "Demo Harvest Foods",
  category: "Oils",
  package_size: "1 L",
  manufacturer_name: "Demo Harvest Foods (fictional) Ltd",
  company_display_name: "Demo Harvest Foods (fictional)",
  registration_number: "DEMO-NAFDAC-0001",
};
const batch = { batch_number: "DEMO-LOT-101", production_date: "2026-04-01", expiry_date: "2027-11-12" };

function base(overrides: Partial<LookupResponse>): LookupResponse {
  return {
    result: "REGISTERED_ACTIVE",
    data_mode: "DEMO",
    disclaimer,
    title: "Matches an active record in the simulated register",
    message: "",
    warnings: [],
    input: { registration_number: "DEMO-NAFDAC-0001", batch_number: "DEMO-LOT-101" },
    register_record: null,
    mismatch: null,
    product: null,
    batch: null,
    announcements: [],
    ...overrides,
  };
}

export const lookupFixtures: Record<LookupResponse["result"], LookupResponse> = {
  REGISTERED_ACTIVE: base({
    message:
      "This number matches an active record in the simulated NAFDAC register (demo data). " +
      "Compare the registered product and company names below with the pack. A matching number " +
      "cannot rule out a copied number.",
    register_record: record,
    product,
    batch,
    announcements: [
      {
        title: "New packaging",
        message: "From March 2027 the bottle is green.",
        posted_at: "2026-10-09T12:00:00Z",
        label: "Message from the company — not reviewed by FoodLens",
      },
    ],
  }),
  REGISTRATION_NOT_FOUND: base({
    result: "REGISTRATION_NOT_FOUND",
    title: "Number not found in the simulated register",
    message:
      "This number is not in the simulated NAFDAC/SON register (demo data). The demo register is " +
      "small and fictional, so this does not show what the real regulator holds.",
    input: { registration_number: "DEMO-NAFDAC-9999", batch_number: null },
  }),
  REGISTRATION_EXPIRED_OR_INACTIVE: base({
    result: "REGISTRATION_EXPIRED_OR_INACTIVE",
    title: "Registration expired or inactive in the simulated register",
    message:
      "This number is in the simulated NAFDAC register (demo data), but the record is expired. " +
      "This is the status of the demo record, not an official enforcement result.",
    register_record: { ...record, status: "EXPIRED_IN_DEMO_REGISTER", expires_on: "2026-08-10" },
  }),
  REGISTRATION_MISMATCH: base({
    result: "REGISTRATION_MISMATCH",
    title: "Number belongs to a different product or company",
    message:
      "This number is recorded in the simulated NAFDAC register (demo data) for a different " +
      "product or company than the product the batch belongs to.",
    register_record: {
      ...record,
      registration_number: "DEMO-NAFDAC-0009",
      registered_product_name: "Sample Chin Chin",
      registered_company_name: "Northern Snacks (fictional) Ltd",
    },
    mismatch: { reason: "registered_names_differ" },
    product: { ...product, name: "Sample Honey", registration_number: "DEMO-NAFDAC-0009" },
    batch: { ...batch, batch_number: "DEMO-LOT-601" },
  }),
  INSUFFICIENT_OR_AMBIGUOUS: base({
    result: "INSUFFICIENT_OR_AMBIGUOUS",
    title: "More details needed",
    message: "Enter the NAFDAC or SON registration number printed on the pack.",
    input: { registration_number: null, batch_number: null },
  }),
};
