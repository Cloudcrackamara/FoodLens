import type { CheckResponse } from "@/lib/check";

export const DISCLAIMER =
  "FoodLens shows what has been recorded for this code in a demonstration database with fictional companies and products. It is not NAFDAC's or SON's service, it is not a laboratory test, and it cannot prove anything about the item in your hand. No QR system catches every copied code.";

export const DEMO_CODE = "7Q2M8KD3XH4N0P1R5S6T9V0W1Y";

const base: CheckResponse = {
  data_mode: "DEMO",
  disclaimer: DISCLAIMER,
  result: "RECOGNISED_NOT_SOLD",
  identifier_type: "QR",
  subject: "PACK",
  code_last4: "0W1Y",
  title: "In circulation, not yet sold",
  message: "This code was issued by Demo Harvest Foods and is in circulation.",
  tip: "Scan again after you pay. It should show this item as just sold by the shop.",
  advice: null,
  just_sold_window_hours: 6,
  product: {
    name: "Sample Palm Oil",
    brand: "Demo Harvest",
    size: "1 L",
    manufacturer_name: "Demo Harvest Foods",
    registration_number: "DEMO-01-2345",
  },
  batch: { batch_number: "DEMO-LOT-001", expiry_date: "2027-06-30", expired: false },
  sale: null,
  recorded_facts: [
    "Code issued by Demo Harvest Foods on 1 Oct 2026.",
    "Released for sale by Demo Harvest Foods on 2 Oct 2026.",
  ],
  possible_patterns: [],
  warnings: [],
  notices: [],
  can_note_purchase: true,
  copy_help:
    "A copied QR carries the same code. FoodLens spots copies by whether the code was sold, where it is checked, how often, and where the stock was sent, not by the QR alone. No QR system catches every copied code.",
  can_report: true,
};

const sale = { retailer_name: "Demo Corner Shop", area: "Kano", sold_at: "2026-10-26T06:00:00Z" };

export const checkFixtures: Record<string, CheckResponse> = {
  notSold: base,
  justSold: {
    ...base,
    result: "RECOGNISED_JUST_SOLD",
    title: "Just sold",
    message:
      "Just sold by Demo Corner Shop, Kano, at 07:00 on 26 Oct 2026 (Nigeria time). If that was your purchase, this matches.",
    tip: "Sales recorded in the last 6 hours show as just sold.",
    sale,
    can_note_purchase: false,
  },
  previouslySold: {
    ...base,
    result: "RECOGNISED_PREVIOUSLY_SOLD",
    title: "Already recorded as sold",
    message: "This code was already recorded as sold on 20 Oct 2026 in Lagos.",
    tip: null,
    advice: "If you are buying it now, ask the seller about it or choose another pack.",
    sale: { ...sale, area: "Lagos" },
    can_note_purchase: false,
  },
  recall: {
    ...base,
    result: "BATCH_OR_PRODUCT_WARNING",
    title: "Recall posted for this product",
    message: "Demo Harvest Foods has posted a recall that covers this pack.",
    tip: null,
    notices: [
      {
        kind: "RECALL",
        title: "Recall of demo lot",
        message: "Please return this demo lot to the shop.",
        posted_at: "2026-10-25T09:00:00Z",
        label: "Message from the company — not reviewed by FoodLens",
      },
    ],
  },
  suspicious: {
    ...base,
    result: "SUSPICIOUS_ACTIVITY",
    title: "This code may have been copied",
    message:
      "FoodLens has seen activity for this code that often happens when a QR code is copied. This is a warning, not proof about the pack in your hand.",
    tip: null,
    advice: "Ask the seller about it or choose another pack, and report a concern.",
    possible_patterns: ["Checked in places too far apart for the time between checks."],
    can_note_purchase: false,
  },
  invalidScanned: {
    ...base,
    result: "INVALID_IDENTITY",
    subject: null,
    title: "Code not recognised",
    message: "FoodLens has no active record of this code from an approved manufacturer.",
    tip: null,
    advice: "Ask the seller about this pack, or choose another one.",
    product: null,
    batch: null,
    recorded_facts: [],
    can_note_purchase: false,
  },
  invalidTyped: {
    ...base,
    result: "INVALID_IDENTITY",
    identifier_type: "TYPED",
    subject: null,
    title: "We couldn't find that code",
    message: "Check you typed it correctly, or scan the QR.",
    tip: null,
    product: null,
    batch: null,
    recorded_facts: [],
    can_note_purchase: false,
  },
  carton: {
    ...base,
    result: "CARTON_CODE",
    subject: "CARTON",
    title: "This is a carton code",
    message: "This is a carton code; check the individual pack.",
    tip: null,
    can_note_purchase: false,
  },
};
