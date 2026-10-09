import type { AdminCompany, Company, Supplier } from "@/lib/companies";

export const pendingCompany: Company = {
  company_id: "22222222-2222-2222-2222-222222222222",
  company_type: "MANUFACTURER",
  display_name: "Test Foods (fictional)",
  contact_email: "hello@testfoods.example.com",
  contact_phone: null,
  claimed_legal_name: "Test Foods Ltd (fictional)",
  claimed_business_identifier: "DEMO-RC-9999",
  claimed_address: null,
  review_status: "PENDING_REVIEW",
  reviewed_at: null,
  review_note: null,
  created_at: "2026-10-08T10:00:00Z",
  locations: [],
};

export const approvedCompany: Company = {
  ...pendingCompany,
  review_status: "APPROVED",
  reviewed_at: "2026-10-08T12:00:00Z",
  locations: [
    {
      location_id: "33333333-3333-3333-3333-333333333333",
      name: "Main depot",
      address: "2 Demo Way",
      area: "Ikeja, Lagos",
      contact_member_id: null,
      review_status: "PENDING_REVIEW",
      reviewed_at: null,
      review_note: null,
      created_at: "2026-10-08T12:30:00Z",
    },
  ],
};

export const adminPendingCompany: AdminCompany = {
  ...pendingCompany,
  owner_display_name: "Owner Demo",
  owner_email: "owner@example.com",
  reviewed_by_display_name: null,
};

export const supplier: Supplier = {
  company_id: "44444444-4444-4444-4444-444444444444",
  display_name: "Demo Harvest Foods (fictional)",
  company_type: "MANUFACTURER",
  contact_email: "contact@demo-rc-0001.example",
  contact_phone: null,
  badge: "FoodLens demo-reviewed profile",
  badge_note:
    "Reviewed for the FoodLens demonstration database only. This is not a NAFDAC or SON " +
    "approval, and it does not verify the company's identity or products.",
  reviewed_at: "2026-10-08T12:00:00Z",
  locations: [
    { name: "Demo Harvest Ikeja depot (fictional)", address: "12 Sample Road", area: "Ikeja, Lagos", reviewed_at: "2026-10-08T12:00:00Z" },
  ],
  contacts: [{ display_name: "Ada Rep", title: "Sales lead", phone: null, email: "sales@company.example" }],
};
