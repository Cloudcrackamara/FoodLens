import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Lookup } from "@/lib/merchant";
import type { QrDecoder } from "@/lib/qr";
import { DEMO_CODE } from "@/test/checkFixtures";
import { renderWithQuery, routeFetch } from "@/test/utils";
import { MerchantPage } from "./MerchantPage";

afterEach(() => vi.unstubAllGlobals());

const COMPANY = "c0ffee00-0000-4000-8000-000000000001";
const BASE = `/api/companies/${COMPANY}/merchant`;

function unit(overrides: Partial<Lookup> = {}): Lookup {
  return {
    subject: "UNIT",
    code_last4: "0W1Y",
    product_name: "Sample Palm Oil",
    brand: "Demo Harvest",
    size: "1 L",
    batch_number: "DEMO-LOT-001",
    expiry_date: "2027-06-30",
    packs: 1,
    status_counts: [{ status: "RELEASED", packs: 1 }],
    recalled: false,
    you_hold: 0,
    sold_by_you: 0,
    allowed_events: ["RECEIVED", "SOLD"],
    blocked_reason: null,
    ...overrides,
  };
}

function api(lookup: Lookup, result: object = {}) {
  return routeFetch({
    [`POST ${BASE}/lookup`]: { body: lookup },
    [`POST ${BASE}/events`]: (init) => {
      const sent = JSON.parse(init.body as string);
      return {
        body: {
          event_type: sent.event_type,
          subject: lookup.subject,
          packs: lookup.packs,
          status_after: "IN_STOCK",
          notes: [],
          ...result,
        },
      };
    },
    [`GET ${BASE}/destinations`]: {
      body: [{ company_id: "d1d1d1d1-0000-4000-8000-000000000002", display_name: "Demo Corner Shop" }],
    },
  });
}

function sentEvents(fetchMock: ReturnType<typeof api>) {
  return fetchMock.mock.calls
    .filter(([url]) => url === `${BASE}/events`)
    .map(([, init]) => JSON.parse((init as RequestInit).body as string));
}

async function typeCode(code = "7q2m-8kd3 xh4n op1r 5s6t 9vow ly") {
  fireEvent.change(screen.getByLabelText("Or type the code printed under the QR"), { target: { value: code } });
  fireEvent.click(screen.getByRole("button", { name: "Look up code" }));
  await screen.findByRole("heading", { level: 2, name: "Sample Palm Oil" });
}

describe("merchant page", () => {
  it("normalises the typed code and records a sale with only the code and event", async () => {
    const fetchMock = api(unit());
    renderWithQuery(<MerchantPage companyId={COMPANY} />);

    await typeCode();
    expect(JSON.parse(fetchMock.mock.calls[0][1]!.body as string)).toEqual({ code: DEMO_CODE });
    fireEvent.click(screen.getByRole("radio", { name: /^Sold/ }));
    fireEvent.click(screen.getByRole("button", { name: "Record" }));

    expect(await screen.findByRole("status")).toHaveTextContent("1 pack recorded as sold.");
    expect(sentEvents(fetchMock)).toEqual([{ code: DEMO_CODE, event_type: "SOLD" }]);
  });

  it("offers only the events the server allows", async () => {
    api(unit({ allowed_events: ["RETURNED", "SALE_CORRECTED"] }));
    renderWithQuery(<MerchantPage companyId={COMPANY} />);

    await typeCode();

    expect(screen.getAllByRole("radio").map((radio) => (radio as HTMLInputElement).value)).toEqual([
      "RETURNED",
      "SALE_CORRECTED",
    ]);
  });

  it("sends the receiving company for a transfer", async () => {
    const fetchMock = api(unit({ allowed_events: ["TRANSFERRED", "SOLD"], status_counts: [{ status: "IN_STOCK", packs: 1 }] }));
    renderWithQuery(<MerchantPage companyId={COMPANY} />);
    await typeCode();

    fireEvent.click(screen.getByRole("radio", { name: /^Transferred/ }));
    const record = screen.getByRole("button", { name: "Record" });
    expect(record).toBeDisabled();
    const target = await screen.findByRole("option", { name: "Demo Corner Shop" });
    fireEvent.change(screen.getByLabelText("Send to"), { target: { value: (target as HTMLOptionElement).value } });
    fireEvent.click(record);

    await screen.findByRole("status");
    expect(sentEvents(fetchMock)).toEqual([
      { code: DEMO_CODE, event_type: "TRANSFERRED", to_company_id: "d1d1d1d1-0000-4000-8000-000000000002" },
    ]);
  });

  it("needs a reason for a correction and sends it trimmed", async () => {
    const fetchMock = api(unit({ allowed_events: ["RETURNED", "SALE_CORRECTED"] }));
    renderWithQuery(<MerchantPage companyId={COMPANY} />);
    await typeCode();

    fireEvent.click(screen.getByRole("radio", { name: /^Sale corrected/ }));
    expect(screen.getByRole("button", { name: "Record" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Reason for the correction"), { target: { value: "  Wrong pack  " } });
    fireEvent.click(screen.getByRole("button", { name: "Record" }));

    await screen.findByRole("status");
    expect(sentEvents(fetchMock)).toEqual([{ code: DEMO_CODE, event_type: "SALE_CORRECTED", reason: "Wrong pack" }]);
  });

  it("records a return with no extra fields", async () => {
    const fetchMock = api(unit({ allowed_events: ["RETURNED", "SALE_CORRECTED"] }));
    renderWithQuery(<MerchantPage companyId={COMPANY} />);
    await typeCode();

    fireEvent.click(screen.getByRole("radio", { name: /^Returned/ }));
    fireEvent.click(screen.getByRole("button", { name: "Record" }));

    expect(await screen.findByRole("status")).toHaveTextContent("1 pack recorded as returned.");
    expect(sentEvents(fetchMock)).toEqual([{ code: DEMO_CODE, event_type: "RETURNED" }]);
  });

  it("asks for confirmation before a carton event, and can go back", async () => {
    const carton = unit({ subject: "CARTON", packs: 12, status_counts: [{ status: "RELEASED", packs: 12 }], allowed_events: ["RECEIVED", "SOLD"] });
    const fetchMock = api(carton, { notes: ["Received without a recorded transfer."] });
    renderWithQuery(<MerchantPage companyId={COMPANY} />);
    await typeCode();

    expect(screen.getByText("Carton of 12 packs")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Record" }));
    expect(screen.getByRole("heading", { name: "Record received for 12 packs?" })).toBeInTheDocument();
    expect(sentEvents(fetchMock)).toEqual([]);

    fireEvent.click(screen.getByRole("button", { name: "Go back" }));
    expect(screen.getByRole("radio", { name: /^Received/ })).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "Record" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm for 12 packs" }));

    expect(await screen.findByRole("status")).toHaveTextContent("12 packs received.");
    expect(screen.getByText("Received without a recorded transfer.")).toBeInTheDocument();
    expect(sentEvents(fetchMock)).toEqual([{ code: DEMO_CODE, event_type: "RECEIVED" }]);
  });

  it("explains why nothing can be recorded", async () => {
    api(unit({ allowed_events: [], blocked_reason: "This pack is already recorded as sold." }));
    renderWithQuery(<MerchantPage companyId={COMPANY} />);
    await typeCode();

    expect(screen.getByRole("alert")).toHaveTextContent("This pack is already recorded as sold.");
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
  });

  it("shows the server's refusal", async () => {
    routeFetch({
      [`POST ${BASE}/lookup`]: { body: unit() },
      [`POST ${BASE}/events`]: { status: 403, body: { detail: "Only the company that recorded the sale can do this." } },
    });
    renderWithQuery(<MerchantPage companyId={COMPANY} />);
    await typeCode();

    fireEvent.click(screen.getByRole("button", { name: "Record" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Only the company that recorded the sale can do this.");
  });

  it("shows an unknown code message", async () => {
    routeFetch({
      [`POST ${BASE}/lookup`]: { status: 404, body: { detail: "No FoodLens code found. Check the code and try again." } },
    });
    renderWithQuery(<MerchantPage companyId={COMPANY} />);

    fireEvent.change(screen.getByLabelText("Or type the code printed under the QR"), { target: { value: "ABCD" } });
    fireEvent.click(screen.getByRole("button", { name: "Look up code" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("No FoodLens code found.");
  });

  it("looks up a scanned QR with the camera reader and sends no image", async () => {
    const stream = { getTracks: () => [{ stop: vi.fn() }] } as unknown as MediaStream;
    vi.stubGlobal("navigator", { ...navigator, mediaDevices: { getUserMedia: vi.fn().mockResolvedValue(stream) } });
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    Object.defineProperty(HTMLMediaElement.prototype, "readyState", { configurable: true, get: () => 4 });
    const decoder: QrDecoder = {
      fromVideo: vi.fn().mockResolvedValue(`https://foodlens.online/p/${DEMO_CODE}`),
      fromFile: vi.fn(),
    };
    const fetchMock = api(unit());
    renderWithQuery(<MerchantPage companyId={COMPANY} decoder={decoder} />);

    fireEvent.click(screen.getByRole("button", { name: "Open the camera" }));

    await screen.findByRole("heading", { level: 2, name: "Sample Palm Oil" });
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    for (const [, init] of fetchMock.mock.calls) {
      expect(String((init as RequestInit).body ?? "")).not.toMatch(/data:image|base64|blob:/i);
    }
    expect(JSON.parse(fetchMock.mock.calls[0][1]!.body as string)).toEqual({ code: DEMO_CODE });
  });
});
