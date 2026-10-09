import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { supplier } from "@/test/companyFixtures";
import { renderWithQuery, routeFetch } from "@/test/utils";
import { SupplierDirectory } from "./SupplierDirectory";

describe("SupplierDirectory", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows each supplier with the demo-review badge and what it means", async () => {
    routeFetch({ "GET /api/suppliers": { body: [supplier] } });
    renderWithQuery(<SupplierDirectory />);

    const card = await screen.findByRole("listitem", { name: supplier.display_name });
    expect(within(card).getByText("FoodLens demo-reviewed profile")).toBeInTheDocument();
    expect(card).toHaveTextContent("not a NAFDAC or SON approval");
    expect(card).toHaveTextContent("Demo Harvest Ikeja depot (fictional)");
    expect(card).toHaveTextContent("Ikeja, Lagos");
    expect(card).toHaveTextContent("Ada Rep, Sales lead · sales@company.example");
  });

  it("says when no supplier matches", async () => {
    routeFetch({ "GET /api/suppliers": { body: [] } });
    renderWithQuery(<SupplierDirectory />);

    expect(await screen.findByText("No demo-reviewed suppliers match.")).toBeInTheDocument();
  });

  it("searches by name or area", async () => {
    const fetchMock = routeFetch({
      "GET /api/suppliers": { body: [supplier] },
      "GET /api/suppliers?q=kano": { body: [] },
    });
    renderWithQuery(<SupplierDirectory />);

    fireEvent.change(screen.getByLabelText("Search by name or area"), {
      target: { value: "kano" },
    });

    await waitFor(() =>
      expect(fetchMock.mock.calls.map((call) => call[0])).toContain("/api/suppliers?q=kano"),
    );
  });
});
