import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Product } from "@/lib/catalogue";
import { renderWithQuery, routeFetch } from "@/test/utils";
import { Catalogue } from "./Catalogue";

const companyId = "c1";
const product: Product = {
  product_id: "p1",
  product_code: "DEMO-PC-5001",
  name: "Sample Cocoa Drink",
  brand: "Test Foods",
  category: "Beverages",
  package_size: "500 g",
  manufacturer_name: "Test Foods Ltd (fictional)",
  label_information: null,
  status: "PUBLISHED",
  created_at: "2026-10-09T10:00:00Z",
  batches: [
    { batch_id: "b1", batch_number: "LOT-1", production_date: null, expiry_date: "2027-12-31", created_at: "2026-10-09T10:00:00Z" },
  ],
  credentials: [
    {
      credential_id: "cr1",
      agency: "NAFDAC (simulated)",
      scheme: "Food product registration (demo)",
      reference_number: "DEMO-NAFDAC-5001",
      status: "ACTIVE",
      valid_from: null,
      valid_until: null,
      data_mode: "DEMO",
      review_status: "PENDING_REVIEW",
      reviewed_at: null,
      review_note: null,
    },
  ],
};

function fill(container: HTMLElement, label: string, value: string) {
  fireEvent.change(within(container).getByLabelText(label), { target: { value } });
}

function body(fetchMock: ReturnType<typeof routeFetch>, url: string) {
  const call = fetchMock.mock.calls.find(([u, init]) => u === url && init?.method === "POST");
  return JSON.parse(call![1]!.body as string);
}

describe("Catalogue", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("lists products with batches and shows credential claims as awaiting review", async () => {
    routeFetch({
      [`GET /api/companies/${companyId}/products`]: { body: [product] },
      "GET /api/agencies": { body: [] },
    });
    renderWithQuery(<Catalogue companyId={companyId} />);

    const card = await screen.findByRole("listitem", { name: "Sample Cocoa Drink" });
    expect(card).toHaveTextContent("LOT-1 · expires 31 Dec 2027");
    expect(card).toHaveTextContent("Claimed, awaiting FoodLens review (hidden from lookups)");
    expect(card).toHaveTextContent("Credential claims (product-level)");
  });

  it("publishes a product with only catalogue fields", async () => {
    const url = `/api/companies/${companyId}/products`;
    const fetchMock = routeFetch({
      [`GET ${url}`]: { body: [] },
      [`POST ${url}`]: { status: 201, body: {} },
    });
    const { container } = renderWithQuery(<Catalogue companyId={companyId} />);

    fill(container, "Product code", "demo-pc-5002");
    fill(container, "Product name", "Sample Biscuits");
    fill(container, "Brand", "Test Foods");
    fill(container, "Category", "Snacks");
    fill(container, "Manufacturer", "Test Foods Ltd (fictional)");
    fireEvent.click(screen.getByRole("button", { name: "Publish product" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([, i]) => i?.method === "POST")).toBe(true));
    expect(Object.keys(body(fetchMock, url)).sort()).toEqual([
      "brand",
      "category",
      "manufacturer_name",
      "name",
      "package_size",
      "product_code",
    ]);
  });

  it("submits a credential claim without any status field", async () => {
    const url = `/api/companies/${companyId}/products/p1/credentials`;
    const fetchMock = routeFetch({
      [`GET /api/companies/${companyId}/products`]: { body: [product] },
      "GET /api/agencies": {
        body: [{ agency_id: "a1", name: "NAFDAC (simulated)", scheme: "Food product registration (demo)" }],
      },
      [`POST ${url}`]: { status: 201, body: [product] },
    });
    renderWithQuery(<Catalogue companyId={companyId} />);

    const form = await screen.findByRole("form", { name: "Claim credential for Sample Cocoa Drink" });
    expect(form).toHaveTextContent("never a NAFDAC or SON check");
    await within(form).findByRole("option", { name: /NAFDAC \(simulated\)/ });
    fireEvent.change(within(form).getByRole("combobox"), { target: { value: "a1" } });
    fill(form, "Reference number", "demo-nafdac-5002");
    fireEvent.click(within(form).getByRole("button", { name: "Submit claim for review" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => u === url)).toBe(true));
    expect(body(fetchMock, url)).toEqual({
      agency_id: "a1",
      reference_number: "demo-nafdac-5002",
      valid_from: null,
      valid_until: null,
    });
  });
});
