import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { lookupFixtures } from "@/test/lookupFixtures";
import { mockFetch, renderWithQuery } from "@/test/utils";
import { LookupForm } from "./LookupForm";

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

function submit() {
  fireEvent.click(screen.getByRole("button", { name: "Check demo records" }));
}

describe("LookupForm", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("posts the trimmed codes and shows the result", async () => {
    const fetchMock = mockFetch({ status: 200, body: lookupFixtures.DEMO_RECORD_FOUND });
    renderWithQuery(<LookupForm />);

    fill("Product code", "  demo-pc-0001 ");
    fill("Batch number", "demo-lot-101");
    submit();

    expect(await screen.findByRole("heading", { name: "Demo record found" })).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/lookups/batch");
    expect(JSON.parse(init.body)).toEqual({
      product_code: "demo-pc-0001",
      batch_number: "demo-lot-101",
    });
    expect(init.credentials).toBe("same-origin");
  });

  it("resubmits with the chosen product when the batch number is ambiguous", async () => {
    const fetchMock = mockFetch(
      { status: 200, body: lookupFixtures.INSUFFICIENT_OR_AMBIGUOUS },
      { status: 200, body: lookupFixtures.DEMO_RECORD_FOUND },
    );
    renderWithQuery(<LookupForm />);

    fill("Batch number", "DEMO-LOT-001");
    submit();
    fireEvent.click((await screen.findAllByRole("button", { name: "Choose this product" }))[0]);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      product_code: "DEMO-PC-0001",
      batch_number: "DEMO-LOT-001",
    });
    expect(screen.getByLabelText("Product code")).toHaveValue("DEMO-PC-0001");
    expect(await screen.findByRole("heading", { name: "Demo record found" })).toBeInTheDocument();
  });

  it("explains a per-network rate limit and when to retry", async () => {
    mockFetch({
      status: 429,
      body: { detail: "Too many requests from your network. Try again in 4 seconds." },
      headers: { "Retry-After": "4" },
    });
    renderWithQuery(<LookupForm />);

    fill("Product code", "DEMO-PC-0001");
    fill("Batch number", "DEMO-LOT-101");
    submit();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/shared by everyone on the same network/);
    expect(alert).toHaveTextContent(/try again in about 4 seconds/i);
  });

  it("rejects a response that is not marked as demo data", async () => {
    mockFetch({
      status: 200,
      body: { ...lookupFixtures.DEMO_RECORD_FOUND, data_mode: "OFFICIAL" },
    });
    renderWithQuery(<LookupForm />);

    fill("Product code", "DEMO-PC-0001");
    fill("Batch number", "DEMO-LOT-101");
    submit();

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Demo record found" })).not.toBeInTheDocument();
  });
});
