import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Product } from "@/lib/catalogue";
import type { AdminNotice } from "@/lib/changeNotices";
import { AdminReview } from "@/components/admin/AdminReview";
import { demoUser, renderWithQuery, routeFetch } from "@/test/utils";
import { ChangeNotices } from "./ChangeNotices";

const companyId = "c1";
const product: Product = {
  product_id: "p1",
  product_code: "DEMO-PC-7001",
  name: "Old Name",
  brand: "Test Foods",
  category: "Oils",
  package_size: null,
  manufacturer_name: "Test Foods Ltd (fictional)",
  label_information: null,
  status: "PUBLISHED",
  created_at: "2026-10-09T10:00:00Z",
  batches: [{ batch_id: "b1", batch_number: "LOT-7", production_date: null, expiry_date: null, created_at: "2026-10-09T10:00:00Z" }],
  credentials: [],
};
const notice: AdminNotice = {
  notice_id: "n1",
  company_id: companyId,
  target_type: "product",
  product_id: "p1",
  product_code: "DEMO-PC-7001",
  product_name: "Old Name",
  batch_id: null,
  batch_number: null,
  change_type: "PRODUCT_DETAILS",
  reason: "Rebranding",
  effective_date: "2026-12-01",
  review_status: "PENDING_REVIEW",
  reviewed_at: null,
  review_note: null,
  created_at: "2026-10-09T11:00:00Z",
  fields: [{ field_name: "name", current_value: "Old Name", proposed_value: "New Name", applied_old_value: null }],
  attachments: [{ attachment_id: "a1", original_filename: "label.pdf", mime_type: "application/pdf", size_bytes: 20, created_at: "2026-10-09T11:00:00Z" }],
  company_display_name: "Test Foods (fictional)",
  submitted_by_display_name: "Ada Owner",
  reviewed_by_display_name: null,
};

const base = `/api/companies/${companyId}/change-notices`;

function setUp(extra: Record<string, unknown> = {}) {
  return routeFetch({
    [`GET ${base}`]: { body: [] },
    [`GET /api/companies/${companyId}/products`]: { body: [product] },
    [`POST ${base}`]: { status: 201, body: notice },
    [`POST ${base}/n1/attachments`]: { status: 201, body: notice.attachments[0] },
    ...extra,
  } as Parameters<typeof routeFetch>[0]);
}

async function fillForm(form: HTMLElement) {
  await within(form).findByRole("option", { name: "Old Name (DEMO-PC-7001)" });
  fireEvent.change(within(form).getByLabelText("What to change"), { target: { value: "product:p1" } });
  fireEvent.change(within(form).getByLabelText("Product name"), { target: { value: " New Name " } });
  fireEvent.change(within(form).getByLabelText("Reason"), { target: { value: "Rebranding" } });
}

describe("ChangeNotices", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("submits only the filled-in fields, then uploads attachments as form data", async () => {
    const fetchMock = setUp();
    renderWithQuery(<ChangeNotices companyId={companyId} />);
    const form = await screen.findByRole("form", { name: "Submit a change notice" });

    await fillForm(form);
    const pdf = new File(["%PDF-1.4"], "label.pdf", { type: "application/pdf" });
    fireEvent.change(within(form).getByLabelText(/Supporting files/), { target: { files: [pdf] } });
    fireEvent.click(within(form).getByRole("button", { name: "Submit for review" }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => url === `${base}/n1/attachments`)).toBe(true),
    );
    const [, init] = fetchMock.mock.calls.find(([url, i]) => url === base && i?.method === "POST")!;
    expect(JSON.parse(init!.body as string)).toEqual({
      product_id: "p1",
      change_type: "PRODUCT_DETAILS",
      reason: "Rebranding",
      effective_date: null,
      proposed_changes: { name: "New Name" },
    });
    const [, uploadInit] = fetchMock.mock.calls.find(([url]) => url === `${base}/n1/attachments`)!;
    expect(uploadInit!.body).toBeInstanceOf(FormData);
  });

  it("rejects a bad file type before sending anything", async () => {
    const fetchMock = setUp();
    renderWithQuery(<ChangeNotices companyId={companyId} />);
    const form = await screen.findByRole("form", { name: "Submit a change notice" });

    await fillForm(form);
    const exe = new File(["MZ"], "tool.exe", { type: "application/octet-stream" });
    fireEvent.change(within(form).getByLabelText(/Supporting files/), { target: { files: [exe] } });
    fireEvent.click(within(form).getByRole("button", { name: "Submit for review" }));

    expect(await within(form).findByRole("alert")).toHaveTextContent("only PDF, PNG, or JPG files are accepted");
    expect(fetchMock.mock.calls.some(([, i]) => i?.method === "POST")).toBe(false);
  });

  it("shows submitted notices as pending with before and proposed values", async () => {
    setUp({ [`GET ${base}`]: { body: [notice] } });
    renderWithQuery(<ChangeNotices companyId={companyId} />);

    const card = await screen.findByRole("listitem", { name: "Notice for Old Name" });
    expect(card).toHaveTextContent("Pending FoodLens review (published data unchanged)");
    expect(card).toHaveTextContent("Product nameOld NameNew Name");
  });
});

describe("AdminReview change notices", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("approves a notice from the queue", async () => {
    const decisionUrl = "/api/admin/change-notices/n1/decision";
    const fetchMock = routeFetch({
      "GET /api/auth/me": { body: { ...demoUser, is_admin: true } },
      "GET /api/admin/companies?review_status=PENDING_REVIEW": { body: [] },
      "GET /api/admin/locations?review_status=PENDING_REVIEW": { body: [] },
      "GET /api/admin/credentials?review_status=PENDING_REVIEW": { body: [] },
      "GET /api/admin/change-notices": { body: [notice] },
      [`POST ${decisionUrl}`]: { body: { ...notice, review_status: "APPROVED" } },
    });
    renderWithQuery(<AdminReview />);

    const row = await screen.findByRole("listitem", { name: "Notice for Old Name" });
    expect(within(row).getByRole("link", { name: "label.pdf" })).toHaveAttribute("href", "/api/admin/attachments/a1");
    fireEvent.click(within(row).getByRole("button", { name: "Approve and apply" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => url === decisionUrl)).toBe(true));
    const [, init] = fetchMock.mock.calls.find(([url]) => url === decisionUrl)!;
    expect(JSON.parse(init!.body as string)).toEqual({ decision: "APPROVE", note: null });
  });
});
