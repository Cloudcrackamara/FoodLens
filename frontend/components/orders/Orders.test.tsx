import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { IncomingOrders } from "@/components/company/IncomingOrders";
import { SupplierPage } from "@/components/suppliers/SupplierPage";
import { supplier } from "@/test/companyFixtures";
import {
  acceptedOrder,
  buyerCompanyId,
  manufacturerUser,
  requestedOrder,
  supplierDetail,
  wholesalerUser,
} from "@/test/orderFixtures";
import { renderWithQuery, routeFetch } from "@/test/utils";
import { MyOrders } from "./MyOrders";

const SUPPLIER = `GET /api/suppliers/${supplier.company_id}`;
const BUYER_ORDERS = `/api/companies/${buyerCompanyId}/orders`;
const SELLER_ORDERS = `/api/companies/${supplier.company_id}/orders`;

function bodyOf(fetchMock: ReturnType<typeof routeFetch>, key: string) {
  const call = fetchMock.mock.calls.find(([url, init]) => `${init?.method ?? "GET"} ${url}` === key);
  return call ? JSON.parse(String(call[1]?.body)) : undefined;
}

afterEach(() => vi.unstubAllGlobals());

describe("Supplier page", () => {
  it("shows each product's register result, labelled demo data, never 'safe'", async () => {
    routeFetch({ [SUPPLIER]: { body: supplierDetail }, "GET /api/auth/me": { status: 401 } });
    renderWithQuery(<SupplierPage companyId={supplier.company_id} />);

    const oil = await screen.findByRole("listitem", { name: "Sample Palm Oil" });
    expect(oil).toHaveTextContent("Active in the simulated register (demo data)");
    expect(screen.getByRole("listitem", { name: "Sample Tomato Paste" })).toHaveTextContent("Expired or inactive");
    expect(screen.getByRole("listitem", { name: "Sample Honey" })).toHaveTextContent("Not found in the simulated register");
    expect(screen.getByRole("listitem", { name: "Sample Yam Flour" })).toHaveTextContent("No registration number given");
    expect(screen.getByRole("listitem", { name: "Sample Cocoa" })).toHaveTextContent("different product or company");
    expect(screen.getByRole("note", { name: "Demo data notice" })).toHaveTextContent(
      "DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE",
    );
    expect(document.body.textContent).not.toMatch(/\b(safe|unsafe|genuine)\b/i);
  });

  it("hides the order form from signed-out users and non-wholesalers", async () => {
    routeFetch({ [SUPPLIER]: { body: supplierDetail }, "GET /api/auth/me": { body: manufacturerUser } });
    renderWithQuery(<SupplierPage companyId={supplier.company_id} />);

    await screen.findByRole("listitem", { name: "Sample Palm Oil" });
    expect(screen.queryByRole("form", { name: "Request an order" })).not.toBeInTheDocument();
    expect(screen.getByText(/approved wholesaler companies can request orders/)).toBeInTheDocument();
  });

  it("sends only products, quantities, units, and pickup choice; no status, ids, or prices", async () => {
    const fetchMock = routeFetch({
      [SUPPLIER]: { body: supplierDetail },
      "GET /api/auth/me": { body: wholesalerUser },
      [`POST ${BUYER_ORDERS}`]: { status: 201, body: requestedOrder },
    });
    renderWithQuery(<SupplierPage companyId={supplier.company_id} />);

    const form = await screen.findByRole("form", { name: "Request an order" });
    fireEvent.change(within(form).getByLabelText("Quantity of Sample Palm Oil"), { target: { value: "20" } });
    fireEvent.change(within(form).getByLabelText("Unit for Sample Palm Oil"), { target: { value: "carton" } });
    fireEvent.change(within(form).getByLabelText("Quantity of Sample Honey"), { target: { value: "5" } });
    fireEvent.change(within(form).getByLabelText("Unit for Sample Honey"), { target: { value: "jar" } });
    fireEvent.click(within(form).getByRole("button", { name: "Send order request" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Order request sent");
    expect(bodyOf(fetchMock, `POST ${BUYER_ORDERS}`)).toEqual({
      lines: [
        { product_id: "p-oil", quantity: "20", unit: "carton" },
        { product_id: "p-honey", quantity: "5", unit: "jar" },
      ],
      fulfilment_method: "PICKUP",
      pickup_location_id: supplier.locations[0].location_id,
      delivery_details: null,
      buyer_note: null,
    });
  });

  it("switches to delivery and requires details", async () => {
    const fetchMock = routeFetch({
      [SUPPLIER]: { body: supplierDetail },
      "GET /api/auth/me": { body: wholesalerUser },
      [`POST ${BUYER_ORDERS}`]: { status: 201, body: requestedOrder },
    });
    renderWithQuery(<SupplierPage companyId={supplier.company_id} />);

    const form = await screen.findByRole("form", { name: "Request an order" });
    fireEvent.change(within(form).getByLabelText("Quantity of Sample Palm Oil"), { target: { value: "2" } });
    fireEvent.click(within(form).getByLabelText("Delivery"));
    expect(within(form).queryByLabelText("Pickup location")).not.toBeInTheDocument();
    fireEvent.click(within(form).getByRole("button", { name: "Send order request" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent("delivery address");

    fireEvent.change(within(form).getByLabelText("Delivery address or notes"), {
      target: { value: "Stall 7, Sample Market" },
    });
    fireEvent.click(within(form).getByRole("button", { name: "Send order request" }));

    await screen.findByRole("status");
    expect(bodyOf(fetchMock, `POST ${BUYER_ORDERS}`)).toMatchObject({
      fulfilment_method: "DELIVERY",
      pickup_location_id: null,
      delivery_details: "Stall 7, Sample Market",
    });
  });

  it("refuses zero quantities before sending", async () => {
    const fetchMock = routeFetch({ [SUPPLIER]: { body: supplierDetail }, "GET /api/auth/me": { body: wholesalerUser } });
    renderWithQuery(<SupplierPage companyId={supplier.company_id} />);

    const form = await screen.findByRole("form", { name: "Request an order" });
    fireEvent.change(within(form).getByLabelText("Quantity of Sample Palm Oil"), { target: { value: "0" } });
    fireEvent.click(within(form).getByRole("button", { name: "Send order request" }));

    expect(await within(form).findByRole("alert")).toHaveTextContent("more than zero");
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  });
});

describe("My orders (buyer)", () => {
  it("lists requests and lets the buyer cancel only while requested", async () => {
    const fetchMock = routeFetch({
      "GET /api/auth/me": { body: wholesalerUser },
      [`GET ${BUYER_ORDERS}?role=buying`]: { body: [requestedOrder, acceptedOrder] },
      [`POST ${BUYER_ORDERS}/o-1/cancel`]: { body: { ...requestedOrder, status: "CANCELLED" } },
    });
    renderWithQuery(<MyOrders />);

    const cards = await screen.findAllByRole("listitem", { name: /^Order from/ });
    expect(cards).toHaveLength(2);
    expect(within(cards[0]).getByText("Requested")).toBeInTheDocument();
    expect(within(cards[0]).getByText("Sample Palm Oil: 20 carton")).toBeInTheDocument();
    expect(within(cards[1]).getByText("Supplier message: Ready on Friday")).toBeInTheDocument();
    expect(within(cards[1]).queryByRole("button", { name: "Cancel request" })).not.toBeInTheDocument();

    fireEvent.click(within(cards[0]).getByRole("button", { name: "Cancel request" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(`${BUYER_ORDERS}/o-1/cancel`, expect.objectContaining({ method: "POST" })),
    );
  });
});

describe("Incoming orders (seller)", () => {
  const products = [
    {
      product_id: "p-oil", product_code: "DEMO-PC-0001", name: "Sample Palm Oil", brand: "Demo", category: "Oils",
      package_size: null, manufacturer_name: "Demo", label_information: null, registration_number: null,
      status: "PUBLISHED", created_at: "2026-10-01T00:00:00Z",
      batches: [
        { batch_id: "b-101", batch_number: "DEMO-LOT-101", production_date: null, expiry_date: null, created_at: "2026-10-01T00:00:00Z" },
        { batch_id: "b-102", batch_number: "DEMO-LOT-102", production_date: null, expiry_date: null, created_at: "2026-10-01T00:00:00Z" },
      ],
    },
  ];

  it("accepts, declines with a reason, and replies", async () => {
    const fetchMock = routeFetch({
      [`GET ${SELLER_ORDERS}?role=selling`]: { body: [requestedOrder] },
      [`GET /api/companies/${supplier.company_id}/products`]: { body: products },
      [`POST ${SELLER_ORDERS}/o-1/decline`]: { body: { ...requestedOrder, status: "DECLINED" } },
      [`POST ${SELLER_ORDERS}/o-1/reply`]: { body: requestedOrder },
    });
    renderWithQuery(<IncomingOrders companyId={supplier.company_id} />);

    const card = await screen.findByRole("listitem", { name: /^Order from/ });
    expect(within(card).getByRole("button", { name: "Accept" })).toBeInTheDocument();
    fireEvent.click(within(card).getByRole("button", { name: "Decline" }));
    fireEvent.change(within(card).getByLabelText("Reason (optional)"), { target: { value: "Out of season" } });
    fireEvent.click(within(card).getByRole("button", { name: "Confirm decline" }));
    await waitFor(() => expect(bodyOf(fetchMock, `POST ${SELLER_ORDERS}/o-1/decline`)).toEqual({ reason: "Out of season" }));

    fireEvent.click(within(card).getByRole("button", { name: "Reply" }));
    fireEvent.change(within(card).getByLabelText("Message to the buyer"), { target: { value: "Can do 15" } });
    fireEvent.click(within(card).getByRole("button", { name: "Send reply" }));
    await waitFor(() => expect(bodyOf(fetchMock, `POST ${SELLER_ORDERS}/o-1/reply`)).toEqual({ message: "Can do 15" }));
  });

  it("marks fulfilled with the chosen batches for each line", async () => {
    const fetchMock = routeFetch({
      [`GET ${SELLER_ORDERS}?role=selling`]: { body: [acceptedOrder] },
      [`GET /api/companies/${supplier.company_id}/products`]: { body: products },
      [`POST ${SELLER_ORDERS}/o-2/fulfil`]: { body: { ...acceptedOrder, status: "FULFILLED" } },
    });
    renderWithQuery(<IncomingOrders companyId={supplier.company_id} />);

    const card = await screen.findByRole("listitem", { name: /^Order from/ });
    expect(within(card).queryByRole("button", { name: "Accept" })).not.toBeInTheDocument();
    fireEvent.click(within(card).getByRole("button", { name: "Mark fulfilled" }));
    fireEvent.click(await within(card).findByLabelText("DEMO-LOT-101"));
    fireEvent.click(within(card).getByRole("button", { name: "Confirm fulfilled" }));

    await waitFor(() =>
      expect(bodyOf(fetchMock, `POST ${SELLER_ORDERS}/o-2/fulfil`)).toEqual({
        allocations: [{ line_id: "l-1", batch_ids: ["b-101"] }],
      }),
    );
  });
});
