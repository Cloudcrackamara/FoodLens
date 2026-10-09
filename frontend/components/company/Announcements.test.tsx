import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LookupResultView } from "@/components/lookup/LookupResultView";
import { lookupFixtures } from "@/test/lookupFixtures";
import { renderWithQuery, routeFetch } from "@/test/utils";
import { Announcements } from "./Announcements";

describe("Announcements on the lookup result", () => {
  it("shows the company message with the not-reviewed label and can be closed", () => {
    render(<LookupResultView response={lookupFixtures.DEMO_RECORD_FOUND} />);

    const box = screen.getByRole("complementary", { name: "Messages from the company" });
    expect(box).toHaveTextContent("Message from the company — not reviewed by FoodLens");
    expect(box).toHaveTextContent("From March 2027 the bottle is green.");
    fireEvent.click(within(box).getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("complementary", { name: "Messages from the company" })).not.toBeInTheDocument();
  });

  it("shows nothing when there are no announcements", () => {
    render(<LookupResultView response={lookupFixtures.BATCH_NOT_FOUND} />);

    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
  });
});

describe("Announcements (company)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("posts only a title and message for the chosen product", async () => {
    const url = "/api/companies/c1/products/p1/announcements";
    const fetchMock = routeFetch({
      "GET /api/companies/c1/products": {
        body: [{
          product_id: "p1", product_code: "DEMO-PC-8001", name: "Sample Oil", brand: "B", category: "Oils",
          package_size: null, manufacturer_name: "M", label_information: null, status: "PUBLISHED",
          created_at: "2026-10-09T10:00:00Z", batches: [], credentials: [],
        }],
      },
      "GET /api/companies/c1/announcements": { body: [] },
      [`POST ${url}`]: {
        status: 201,
        body: {
          announcement_id: "a1", product_id: "p1", product_code: "DEMO-PC-8001", product_name: "Sample Oil",
          title: "New packaging", message: "Green bottle", status: "LIVE", created_at: "2026-10-09T12:00:00Z", hidden_at: null,
        },
      },
    });
    renderWithQuery(<Announcements companyId="c1" />);
    const form = screen.getByRole("form", { name: "Post an announcement" });

    await within(form).findByRole("option", { name: "Sample Oil (DEMO-PC-8001)" });
    fireEvent.change(within(form).getByLabelText("Product"), { target: { value: "p1" } });
    fireEvent.change(within(form).getByLabelText("Title"), { target: { value: "New packaging" } });
    fireEvent.change(within(form).getByLabelText("Message"), { target: { value: "Green bottle" } });
    fireEvent.click(within(form).getByRole("button", { name: "Post announcement" }));

    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => u === url)).toBe(true));
    const [, init] = fetchMock.mock.calls.find(([u]) => u === url)!;
    expect(JSON.parse(init!.body as string)).toEqual({ title: "New packaging", message: "Green bottle" });
  });
});
