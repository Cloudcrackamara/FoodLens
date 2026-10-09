import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { approvedCompany, pendingCompany } from "@/test/companyFixtures";
import { renderWithQuery, routeFetch } from "@/test/utils";
import { CompanyView } from "./CompanyDashboard";
import { CompanyRegisterForm } from "./CompanyRegisterForm";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

describe("CompanyRegisterForm", () => {
  beforeEach(() => push.mockReset());
  afterEach(() => vi.unstubAllGlobals());

  it("sends only company fields, never review status, and goes to the dashboard", async () => {
    const fetchMock = routeFetch({ "POST /api/companies": { status: 201, body: pendingCompany } });
    renderWithQuery(<CompanyRegisterForm />);

    fill("Company name (shown publicly)", "Test Foods (fictional)");
    fill("Contact email (shown publicly)", "hello@testfoods.example.com");
    fill("Registered legal name", "Test Foods Ltd (fictional)");
    fireEvent.click(screen.getByRole("button", { name: "Submit for FoodLens review" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/company"));
    const [, init] = fetchMock.mock.calls.find(([url]) => url === "/api/companies")!;
    expect(Object.keys(JSON.parse(init!.body as string)).sort()).toEqual([
      "claimed_address",
      "claimed_business_identifier",
      "claimed_legal_name",
      "company_type",
      "contact_email",
      "contact_phone",
      "display_name",
    ]);
  });

  it("requires a name, email and legal name", () => {
    const fetchMock = routeFetch({});
    renderWithQuery(<CompanyRegisterForm />);

    fireEvent.click(screen.getByRole("button", { name: "Submit for FoodLens review" }));

    expect(screen.getByText("Enter the company name")).toBeInTheDocument();
    expect(screen.getByText("Enter a valid email address")).toBeInTheDocument();
    expect(screen.getByText("Enter the registered legal name")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("CompanyView", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("explains pending review and hides the location form", () => {
    renderWithQuery(<CompanyView company={pendingCompany} />);

    expect(screen.getByText("Status: Pending FoodLens review")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Add a supplier location" })).not.toBeInTheDocument();
  });

  it("lets an approved company submit a location for review", async () => {
    const fetchMock = routeFetch({
      [`POST /api/companies/${approvedCompany.company_id}/locations`]: {
        status: 201,
        body: approvedCompany.locations[0],
      },
      [`GET /api/companies/${approvedCompany.company_id}`]: { body: approvedCompany },
    });
    renderWithQuery(<CompanyView company={approvedCompany} />);

    expect(screen.getByText("Pending FoodLens review")).toBeInTheDocument();
    expect(screen.getByText(/not a NAFDAC or SON approval/)).toBeInTheDocument();
    fill("Location name", "Second depot");
    fill("Address", "5 Demo Way");
    fill("Area or city", "Lagos");
    fireEvent.click(screen.getByRole("button", { name: "Submit location for review" }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/locations"))).toBe(true),
    );
  });
});
