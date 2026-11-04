import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { DemoTill as Till, PosEventResult, PosLookup } from "@/lib/pos";
import { demoUser, renderWithQuery, routeFetch } from "@/test/utils";
import { DemoTill, DemoTillScreen } from "./DemoTill";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));

afterEach(() => vi.unstubAllGlobals());

const TILLS: Till[] = [
  { till_ref: "DEMO-TILL-1", retailer_name: "Demo Corner Shop (fictional)", location_name: "Ikeja shop", area: "Lagos" },
  { till_ref: "DEMO-TILL-2", retailer_name: "Demo Corner Shop (fictional)", location_name: "Ikeja shop", area: "Lagos" },
];

function lookup(overrides: Partial<PosLookup> = {}): PosLookup {
  return {
    subject: "UNIT",
    code_last4: "BZ3F",
    product_name: "Sample Palm Oil",
    brand: "Demo Harvest",
    size: "1 L",
    gtin: "96385074",
    batch_number: "DEMO-LOT-101",
    expiry_date: "2027-12-04",
    status: "IN_STOCK",
    warning: null,
    ...overrides,
  };
}

function result(action: PosEventResult["event_type"], error: PosEventResult["units"][0]["error"] = null): PosEventResult {
  return {
    transaction_id: "DEMO-TXN-ABC",
    event_type: action,
    recorded: error ? 0 : 1,
    errors: error ? 1 : 0,
    units: [{ index: 0, code_last4: "BZ3F", result: error ? "ERROR" : "RECORDED", error }],
  };
}

function sent(fetchMock: ReturnType<typeof routeFetch>, path: string) {
  return fetchMock.mock.calls
    .filter(([url]) => url === path)
    .map(([, init]) => JSON.parse((init as RequestInit).body as string));
}

async function lookUp(code = "7q2m-8kd3 xh4n 9prt 6wcv 5jbz 3f") {
  fireEvent.change(screen.getByLabelText("Scan or type the pack code"), { target: { value: code } });
  fireEvent.click(screen.getByRole("button", { name: "Look up" }));
  await screen.findByRole("region", { name: "Pack details" });
}

describe("demo till", () => {
  it("sends only the till and the normalised code, and shows the lookup", async () => {
    const fetchMock = routeFetch({ "POST /api/demo/pos/lookup": { body: lookup() } });
    renderWithQuery(<DemoTill tills={TILLS} retailerName="Demo Corner Shop (fictional)" />);

    fireEvent.change(screen.getByLabelText("Till"), { target: { value: "DEMO-TILL-2" } });
    await lookUp();

    expect(sent(fetchMock, "/api/demo/pos/lookup")).toEqual([
      { till_ref: "DEMO-TILL-2", code: "7Q2M8KD3XH4N9PRT6WCV5JBZ3F" },
    ]);
    const card = screen.getByRole("region", { name: "Pack details" });
    expect(card).toHaveTextContent("Sample Palm Oil · 1 L");
    expect(card).toHaveTextContent("DEMO-LOT-101");
    expect(card).toHaveTextContent("In stock");
    expect(card).toHaveTextContent("Code endingBZ3F");
    expect(screen.getByText(/No payment happens here\. FoodLens records the sale only after/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Refund" })).not.toBeInTheDocument();
  });

  it("Confirm payment records the sale and shows the just-sold message", async () => {
    let sold = false;
    const fetchMock = routeFetch({
      "POST /api/demo/pos/lookup": () => ({ body: lookup(sold ? { status: "SOLD", warning: { code: "ALREADY_SOLD", message: "Already recorded as sold on 30 Oct 2026. Don't sell this pack until it's checked." } } : {}) }),
      "POST /api/demo/pos/sales": () => {
        sold = true;
        return { body: result("SOLD") };
      },
    });
    renderWithQuery(<DemoTill tills={TILLS} retailerName="Demo Corner Shop (fictional)" />);
    await lookUp();

    fireEvent.click(screen.getByRole("button", { name: "Confirm payment" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      'Sale recorded. A buyer who checks this pack now sees "Just sold by Demo Corner Shop (fictional)".',
    );
    expect(sent(fetchMock, "/api/demo/pos/sales")).toEqual([
      { till_ref: "DEMO-TILL-1", code: "7Q2M8KD3XH4N9PRT6WCV5JBZ3F" },
    ]);
    // The lookup refreshes, so a sold pack now offers Refund and Void sale.
    expect(await screen.findByRole("button", { name: "Refund" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Void sale" })).toBeInTheDocument();
    // The till's own sale is not flagged as "already sold" next to the success message.
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows the server's warning and per-pack error", async () => {
    const message =
      "This pack is already recorded as sold. Don't complete the sale; set the pack aside and check it.";
    routeFetch({
      "POST /api/demo/pos/lookup": {
        body: lookup({
          status: "SOLD",
          warning: { code: "ALREADY_SOLD", message: "Already recorded as sold on 28 Oct 2026. Don't sell this pack until it's checked." },
        }),
      },
      "POST /api/demo/pos/sales": { body: result("SOLD", { code: "ALREADY_SOLD", message }) },
    });
    renderWithQuery(<DemoTill tills={TILLS} retailerName="Demo Corner Shop (fictional)" />);
    await lookUp();

    expect(screen.getByRole("alert")).toHaveTextContent("Already recorded as sold on 28 Oct 2026.");
    fireEvent.click(screen.getByRole("button", { name: "Confirm payment" }));

    await waitFor(() => expect(screen.getAllByRole("alert").map((a) => a.textContent)).toContain(message));
  });

  it("refunds a sold pack", async () => {
    const fetchMock = routeFetch({
      "POST /api/demo/pos/lookup": { body: lookup({ status: "SOLD" }) },
      "POST /api/demo/pos/refunds": { body: result("RETURNED") },
    });
    renderWithQuery(<DemoTill tills={TILLS} retailerName="Demo Corner Shop (fictional)" />);
    await lookUp();

    fireEvent.click(screen.getByRole("button", { name: "Refund" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Refund recorded. The pack is back in stock, and the sale stays in the history.",
    );
    expect(sent(fetchMock, "/api/demo/pos/refunds")).toEqual([
      { till_ref: "DEMO-TILL-1", code: "7Q2M8KD3XH4N9PRT6WCV5JBZ3F" },
    ]);
  });

  it("a void needs a reason and sends it", async () => {
    const fetchMock = routeFetch({
      "POST /api/demo/pos/lookup": { body: lookup({ status: "SOLD" }) },
      "POST /api/demo/pos/voids": { body: result("SALE_CORRECTED") },
    });
    renderWithQuery(<DemoTill tills={TILLS} retailerName="Demo Corner Shop (fictional)" />);
    await lookUp();

    fireEvent.click(screen.getByRole("button", { name: "Void sale" }));
    const submit = screen.getByRole("button", { name: "Void sale" });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Reason for the void"), { target: { value: " Scanned twice " } });
    fireEvent.click(submit);

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Sale voided. The earlier sale stays in the history.",
    );
    expect(sent(fetchMock, "/api/demo/pos/voids")).toEqual([
      { till_ref: "DEMO-TILL-1", code: "7Q2M8KD3XH4N9PRT6WCV5JBZ3F", reason: "Scanned twice" },
    ]);
  });

  it("never sends a key, secret, amount or card field", async () => {
    const fetchMock = routeFetch({
      "POST /api/demo/pos/lookup": { body: lookup() },
      "POST /api/demo/pos/sales": { body: result("SOLD") },
    });
    renderWithQuery(<DemoTill tills={TILLS} retailerName="Demo Corner Shop (fictional)" />);
    await lookUp();
    fireEvent.click(screen.getByRole("button", { name: "Confirm payment" }));
    await screen.findByRole("status");

    for (const [, init] of fetchMock.mock.calls) {
      const keys = Object.keys(JSON.parse((init as RequestInit).body as string));
      expect(keys.every((key) => ["till_ref", "code", "reason"].includes(key))).toBe(true);
      expect(JSON.stringify((init as RequestInit).headers ?? {})).not.toMatch(/FoodLens/i);
    }
  });
});

describe("demo till wording", () => {
  it("uses none of the banned words in any state", async () => {
    const banned = /\b(original|genuine|authentic|safe|unsafe|fake|adulteration)\b|verified by nafdac/i;
    routeFetch({
      "POST /api/demo/pos/lookup": { body: lookup({ status: "SOLD" }) },
      "POST /api/demo/pos/voids": { body: result("SALE_CORRECTED") },
    });
    const { container } = renderWithQuery(<DemoTill tills={TILLS} retailerName="Demo Corner Shop (fictional)" />);
    await lookUp();
    expect(container.textContent).not.toMatch(banned);
    fireEvent.click(screen.getByRole("button", { name: "Void sale" }));
    fireEvent.change(screen.getByLabelText("Reason for the void"), { target: { value: "Scanned twice" } });
    fireEvent.click(screen.getByRole("button", { name: "Void sale" }));
    await screen.findByRole("status");
    expect(container.textContent).not.toMatch(banned);
  });
});

describe("demo till screen", () => {
  it("asks a signed-out visitor to sign in", async () => {
    routeFetch({ "GET /api/auth/me": { status: 401, body: { detail: "Not signed in" } } });
    renderWithQuery(<DemoTillScreen />);

    expect(await screen.findByText("Sign in as a member of a retailer linked to the demo till.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
  });

  it("shows the server's refusal for an account that is not a linked retailer", async () => {
    routeFetch({
      "GET /api/auth/me": { body: demoUser },
      "GET /api/demo/pos/tills": {
        status: 403,
        body: { error: { code: "NOT_A_RETAILER", message: "Sign in as a member of a retailer linked to the demo till." } },
      },
    });
    renderWithQuery(<DemoTillScreen />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Sign in as a member of a retailer linked to the demo till.",
    );
  });
});
