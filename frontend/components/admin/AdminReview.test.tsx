import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { adminPendingCompany } from "@/test/companyFixtures";
import { demoUser, renderWithQuery, routeFetch } from "@/test/utils";
import { AdminReview } from "./AdminReview";

const admin = { ...demoUser, display_name: "Demo Admin", is_admin: true };

describe("AdminReview", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("refuses non-admins", async () => {
    routeFetch({
      "GET /api/auth/me": { body: demoUser },
      "GET /api/admin/companies?review_status=PENDING_REVIEW": { status: 403, body: {} },
      "GET /api/admin/locations?review_status=PENDING_REVIEW": { status: 403, body: {} },
    });
    renderWithQuery(<AdminReview />);

    expect(await screen.findByText("Admin access required.")).toBeInTheDocument();
  });

  it("lists pending companies and sends the decision with a note", async () => {
    const decisionUrl = `/api/admin/companies/${adminPendingCompany.company_id}/decision`;
    const fetchMock = routeFetch({
      "GET /api/auth/me": { body: admin },
      "GET /api/admin/companies?review_status=PENDING_REVIEW": { body: [adminPendingCompany] },
      "GET /api/admin/locations?review_status=PENDING_REVIEW": { body: [] },
      [`POST ${decisionUrl}`]: {
        body: { ...adminPendingCompany, review_status: "APPROVED" },
      },
    });
    renderWithQuery(<AdminReview />);

    const row = await screen.findByRole("listitem", { name: adminPendingCompany.display_name });
    expect(row).toHaveTextContent("Owner Demo (owner@example.com)");
    expect(row).toHaveTextContent("Claimed registration no.: DEMO-RC-9999");
    fireEvent.change(within(row).getByLabelText("Review note (optional)"), {
      target: { value: "Fictional details checked" },
    });
    fireEvent.click(within(row).getByRole("button", { name: "Approve" }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => url === decisionUrl)).toBe(true),
    );
    const [, init] = fetchMock.mock.calls.find(([url]) => url === decisionUrl)!;
    expect(JSON.parse(init!.body as string)).toEqual({
      decision: "APPROVE",
      note: "Fictional details checked",
    });
  });
});
