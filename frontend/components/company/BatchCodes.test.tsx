import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithQuery } from "@/test/utils";
import { BatchCodes } from "./BatchCodes";

const BASE = "/api/companies/c1/batches/b1";
const summary = {
  product_name: "Sample Palm Oil",
  batch_number: "DEMO-LOT-9",
  expiry_date: "2027-12-31",
  released_at: null,
  units: { ISSUED: 4, RELEASED: 2 },
  loose_units: {},
  cartons: [
    { carton_ref: "C001", status: "RELEASED", units: { RELEASED: 2 } },
    { carton_ref: "C002", status: "ISSUED", units: { ISSUED: 2 } },
  ],
};

type Reply = { status?: number; body?: unknown; zip?: boolean; headers?: Record<string, string> };

function stubApi(routes: Record<string, Reply | ((init: RequestInit) => Reply)>) {
  const fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    const key = `${init.method ?? "GET"} ${url}`;
    const route = routes[key] ?? { status: 404, body: { detail: `No route for ${key}` } };
    const { status = 200, body, zip, headers = {} } = typeof route === "function" ? route(init) : route;
    if (zip) {
      return new Response(new Blob(["PK"]), {
        status,
        headers: { "Content-Type": "application/zip", "Content-Disposition": 'attachment; filename="foodlens-labels-DEMO-LOT-9.zip"', ...headers },
      });
    }
    return new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const common = {
  [`GET ${BASE}/units`]: { body: summary },
  [`GET ${BASE}/allocations`]: { body: [] },
  "GET /api/areas": { body: [{ area_id: "a-lagos", city: "Lagos", state: "Lagos" }] },
  "GET /api/companies/c1/allocation-destinations": { body: [] },
};

function sent(fetchMock: ReturnType<typeof stubApi>, key: string) {
  const call = fetchMock.mock.calls.find(([url, init]) => `${init?.method ?? "GET"} ${url}` === key);
  return call ? JSON.parse(String(call[1]?.body)) : undefined;
}

const fill = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

beforeEach(() => {
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: vi.fn(() => "blob:labels"), revokeObjectURL: vi.fn() }));
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("BatchCodes", () => {
  it("shows counts and cartons, and warns the owner that the file holds every code", async () => {
    stubApi(common);
    renderWithQuery(<BatchCodes companyId="c1" batchId="b1" isOwner />);

    expect(await screen.findByText("6 packs: Not released: 4 · Released: 2")).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("The label file holds every raw code.");
    expect(screen.getByRole("note")).toHaveTextContent("delete every copy after printing");
    const table = screen.getByRole("table", { name: "Cartons" });
    expect(within(table).getByText("C002")).toBeInTheDocument();
  });

  it("hides generate and void from staff", async () => {
    stubApi(common);
    renderWithQuery(<BatchCodes companyId="c1" batchId="b1" isOwner={false} />);

    expect(await screen.findByText("Only the company owner can generate codes and download labels.")).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Generate codes and labels" })).not.toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Void unreleased packs" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Release all unreleased packs" })).toBeInTheDocument();
  });

  it("sends only quantity, packs per carton and QR size, then downloads the file", async () => {
    const fetchMock = stubApi({
      ...common,
      [`POST ${BASE}/units`]: { zip: true, headers: { "X-FoodLens-Label-Warning": "QR codes smaller than 15 mm may not scan reliably on every phone." } },
    });
    renderWithQuery(<BatchCodes companyId="c1" batchId="b1" isOwner />);
    await screen.findByRole("form", { name: "Generate codes and labels" });

    fill("Packs to generate", "10");
    fill("Packs per carton (optional)", "4");
    fill("QR size in mm", "12");
    expect(screen.getByText(/may not scan reliably/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Generate and download labels" }));

    expect(await screen.findByText(/Downloaded foodlens-labels-DEMO-LOT-9.zip/)).toHaveTextContent("smaller than 15 mm");
    expect(sent(fetchMock, `POST ${BASE}/units`)).toEqual({ quantity: 10, units_per_carton: 4, qr_size_mm: 12 });
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:labels");
  });

  it("refuses more than 2,000 packs or a carton bigger than the order without a request", async () => {
    const fetchMock = stubApi(common);
    renderWithQuery(<BatchCodes companyId="c1" batchId="b1" isOwner />);
    await screen.findByRole("form", { name: "Generate codes and labels" });

    fill("Packs to generate", "2001");
    fireEvent.click(screen.getByRole("button", { name: "Generate and download labels" }));
    expect(screen.getByText("At most 2000 packs at a time")).toBeInTheDocument();

    fill("Packs to generate", "3");
    fill("Packs per carton (optional)", "4");
    fireEvent.click(screen.getByRole("button", { name: "Generate and download labels" }));
    expect(screen.getByText(/Between 1 and the number of packs/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  });

  it("releases one carton", async () => {
    const fetchMock = stubApi({ ...common, [`POST ${BASE}/release`]: { body: { units: 2 } } });
    renderWithQuery(<BatchCodes companyId="c1" batchId="b1" isOwner={false} />);

    fireEvent.change(await screen.findByLabelText("Carton"), { target: { value: "C002" } });
    fireEvent.click(screen.getByRole("button", { name: "Release carton" }));

    expect(await screen.findByText("Released 2 packs.")).toBeInTheDocument();
    expect(sent(fetchMock, `POST ${BASE}/release`)).toEqual({ carton_ref: "C002" });
  });

  it("voids listed codes with a reason and needs the reason", async () => {
    const fetchMock = stubApi({ ...common, [`POST ${BASE}/void`]: { body: { units: 2 } } });
    renderWithQuery(<BatchCodes companyId="c1" batchId="b1" isOwner />);
    const form = await screen.findByRole("form", { name: "Void unreleased packs" });

    fireEvent.click(within(form).getByLabelText("Single codes from the label file"));
    fireEvent.change(within(form).getByLabelText("Codes, one per line"), { target: { value: "7q2m-8kd3\n1BG4 3JQA\n" } });
    fireEvent.click(within(form).getByRole("button", { name: "Void packs" }));
    expect(within(form).getByText("Give a reason for voiding.")).toBeInTheDocument();

    fireEvent.change(within(form).getByLabelText("Reason"), { target: { value: "Label file lost" } });
    fireEvent.click(within(form).getByRole("button", { name: "Void packs" }));

    expect(await screen.findByText("Voided 2 packs.")).toBeInTheDocument();
    expect(sent(fetchMock, `POST ${BASE}/void`)).toEqual({
      reason: "Label file lost",
      whole_batch: false,
      carton_refs: [],
      codes: ["7q2m-8kd3", "1BG4 3JQA"],
    });
  });

  it("allocates cartons to an area", async () => {
    const fetchMock = stubApi({
      ...common,
      [`POST ${BASE}/allocations`]: {
        status: 201,
        body: {
          allocation_id: "al1", destination_area: { area_id: "a-lagos", city: "Lagos", state: "Lagos" },
          destination_company: null, quantity: 2, planned_date: null, carton_refs: ["C002"], units_listed: 0, created_at: "2026-10-23T10:00:00Z",
        },
      },
    });
    renderWithQuery(<BatchCodes companyId="c1" batchId="b1" isOwner />);
    const form = await screen.findByRole("form", { name: "Add an allocation" });
    await waitFor(() => expect(within(form).getByRole("option", { name: "Lagos, Lagos" })).toBeInTheDocument());

    fireEvent.change(within(form).getByLabelText("Destination area"), { target: { value: "a-lagos" } });
    fireEvent.click(within(form).getByLabelText("Cartons"));
    fireEvent.change(within(form).getByLabelText("Carton references"), { target: { value: "C002" } });
    fireEvent.click(within(form).getByRole("button", { name: "Add allocation" }));

    await waitFor(() => expect(sent(fetchMock, `POST ${BASE}/allocations`)).toEqual({
      destination_area_id: "a-lagos",
      destination_company_id: null,
      quantity: null,
      planned_date: null,
      carton_refs: ["C002"],
      unit_codes: [],
    }));
  });
});
