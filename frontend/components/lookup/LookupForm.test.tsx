import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { lookupQueryFromUrl } from "@/lib/lookup";
import { lookupFixtures } from "@/test/lookupFixtures";
import { mockFetch, renderWithQuery } from "@/test/utils";
import { LookupForm } from "./LookupForm";

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

function submit() {
  fireEvent.click(screen.getByRole("button", { name: "Check the register" }));
}

describe("LookupForm", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("asks only for the number on the pack and an optional batch, then shows the result", async () => {
    const fetchMock = mockFetch({ status: 200, body: lookupFixtures.REGISTERED_ACTIVE });
    renderWithQuery(<LookupForm />);

    expect(screen.queryByLabelText(/product code/i)).not.toBeInTheDocument();
    fill("NAFDAC or SON number on the pack", "  NAFDAC Reg No: demo-nafdac-0001 ");
    fill("Batch number (optional)", "demo-lot-101");
    submit();

    expect(
      await screen.findByRole("heading", { name: "Matches an active record in the simulated register" }),
    ).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/lookups/registration");
    expect(JSON.parse(init.body)).toEqual({
      registration_number: "NAFDAC Reg No: demo-nafdac-0001",
      batch_number: "demo-lot-101",
    });
  });

  it("sends a null batch when it is left blank", async () => {
    const fetchMock = mockFetch({ status: 200, body: lookupFixtures.REGISTERED_ACTIVE });
    renderWithQuery(<LookupForm />);

    fill("NAFDAC or SON number on the pack", "DEMO-NAFDAC-0001");
    submit();

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).batch_number).toBeNull();
  });

  it("fills in and checks straight away from initial values (?reg=&batch= on the page)", async () => {
    const fetchMock = mockFetch({ status: 200, body: lookupFixtures.REGISTERED_ACTIVE });
    renderWithQuery(
      <LookupForm initial={lookupQueryFromUrl("?reg=DEMO-NAFDAC-0001&batch=DEMO-LOT-101")} />,
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(screen.getByLabelText("NAFDAC or SON number on the pack")).toHaveValue("DEMO-NAFDAC-0001");
    expect(screen.getByLabelText("Batch number (optional)")).toHaveValue("DEMO-LOT-101");
  });

  it("explains a per-network rate limit and when to retry", async () => {
    mockFetch({
      status: 429,
      body: { detail: "Too many requests from your network. Try again in 4 seconds." },
      headers: { "Retry-After": "4" },
    });
    renderWithQuery(<LookupForm />);

    fill("NAFDAC or SON number on the pack", "DEMO-NAFDAC-0001");
    submit();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/shared by everyone on the same network/);
    expect(alert).toHaveTextContent(/try again in about 4 seconds/i);
  });

  it("rejects a response that is not marked as demo data", async () => {
    mockFetch({ status: 200, body: { ...lookupFixtures.REGISTERED_ACTIVE, data_mode: "OFFICIAL" } });
    renderWithQuery(<LookupForm />);

    fill("NAFDAC or SON number on the pack", "DEMO-NAFDAC-0001");
    submit();

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});

describe("lookupQueryFromUrl", () => {
  it("reads reg and batch, with long names as fallback", () => {
    expect(lookupQueryFromUrl("?reg=A1&batch=B2")).toEqual({ registrationNumber: "A1", batchNumber: "B2" });
    expect(lookupQueryFromUrl("?registration_number=A1")).toEqual({ registrationNumber: "A1", batchNumber: "" });
    expect(lookupQueryFromUrl("")).toEqual({ registrationNumber: "", batchNumber: "" });
  });
});
