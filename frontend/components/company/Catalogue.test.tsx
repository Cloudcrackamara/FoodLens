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
  registration_number: "DEMO-NAFDAC-5001",
  status: "PUBLISHED",
  created_at: "2026-10-09T10:00:00Z",
  batches: [
    { batch_id: "b1", batch_number: "LOT-1", production_date: null, expiry_date: "2027-12-31", created_at: "2026-10-09T10:00:00Z" },
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

  it("lists products with batches and the number printed on the pack", async () => {
    routeFetch({
      [`GET /api/companies/${companyId}/products`]: { body: [product] },
    });
    renderWithQuery(<Catalogue companyId={companyId} />);

    const card = await screen.findByRole("listitem", { name: "Sample Cocoa Drink" });
    expect(card).toHaveTextContent("LOT-1 · expires 31 Dec 2027");
    expect(card).toHaveTextContent("Number on the pack: DEMO-NAFDAC-5001");
    expect(card).not.toHaveTextContent(/credential/i);
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
    fill(container, "NAFDAC or SON number printed on the pack (optional)", "demo-nafdac-5002");
    fireEvent.click(screen.getByRole("button", { name: "Publish product" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([, i]) => i?.method === "POST")).toBe(true));
    expect(Object.keys(body(fetchMock, url)).sort()).toEqual([
      "brand",
      "category",
      "manufacturer_name",
      "name",
      "package_size",
      "product_code",
      "registration_number",
    ]);
  });

});
