import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Partner } from "@/lib/pos";
import { renderWithQuery, routeFetch } from "@/test/utils";
import { PosPartners } from "./PosPartners";

afterEach(() => vi.unstubAllGlobals());

const PARTNER: Partner = {
  partner_id: "aaaaaaaa-0000-4000-8000-000000000001",
  name: "Demo Till Systems (fictional)",
  status: "ACTIVE",
  created_at: "2026-10-30T09:00:00Z",
  keys: [{ key_id: "bbbbbbbb-0000-4000-8000-000000000001", key_prefix: "flk_AbCd", created_at: "2026-10-30T09:00:00Z", revoked_at: null }],
  links: [
    {
      link_id: "cccccccc-0000-4000-8000-000000000001",
      retailer_id: "dddddddd-0000-4000-8000-000000000001",
      retailer_name: "Demo Corner Shop (fictional)",
      status: "ACTIVE",
    },
  ],
  tills: [],
};

const RETAILERS = [
  {
    retailer_id: "dddddddd-0000-4000-8000-000000000001",
    display_name: "Demo Corner Shop (fictional)",
    locations: [{ location_id: "eeeeeeee-0000-4000-8000-000000000001", name: "Ikeja shop", area: "Lagos" }],
  },
];

const ONE_TIME =
  "Copy these now. FoodLens shows the API key and signing secret only once and can't show them again.";

describe("POS partners", () => {
  it("shows an empty state", async () => {
    routeFetch({
      "GET /api/admin/pos/partners": { body: [] },
      "GET /api/admin/pos/retailers": { body: [] },
    });
    renderWithQuery(<PosPartners />);

    expect(await screen.findByText("No POS partners yet. Add one to issue an API key.")).toBeInTheDocument();
  });

  it("shows the key and secret once after creating a partner", async () => {
    routeFetch({
      "GET /api/admin/pos/partners": { body: [] },
      "GET /api/admin/pos/retailers": { body: [] },
      "POST /api/admin/pos/partners": {
        status: 201,
        body: { partner: PARTNER, credentials: { api_key: "flk_raw-key", signing_secret: "fls_raw-secret" } },
      },
    });
    renderWithQuery(<PosPartners />);

    fireEvent.change(await screen.findByLabelText("Partner name"), { target: { value: "Demo Till Systems (fictional)" } });
    fireEvent.click(screen.getByRole("button", { name: "Add partner" }));

    const panel = await screen.findByRole("status");
    expect(panel).toHaveTextContent(ONE_TIME);
    expect(panel).toHaveTextContent("flk_raw-key");
    expect(panel).toHaveTextContent("fls_raw-secret");
    fireEvent.click(within(panel).getByRole("button", { name: "Done" }));
    await waitFor(() => expect(screen.queryByText("fls_raw-secret")).not.toBeInTheDocument());
  });

  it("revokes a key and adds a till on a linked retailer's location", async () => {
    const pid = PARTNER.partner_id;
    const fetchMock = routeFetch({
      "GET /api/admin/pos/partners": { body: [PARTNER] },
      "GET /api/admin/pos/retailers": { body: RETAILERS },
      [`POST /api/admin/pos/partners/${pid}/keys/${PARTNER.keys[0].key_id}/revoke`]: {
        body: { ...PARTNER.keys[0], revoked_at: "2026-10-30T10:00:00Z" },
      },
      [`POST /api/admin/pos/partners/${pid}/tills`]: { body: PARTNER },
    });
    renderWithQuery(<PosPartners />);

    const row = await screen.findByRole("listitem", { name: PARTNER.name });
    expect(row).toHaveTextContent("flk_AbCd…");
    expect(row).not.toHaveTextContent("fls_");
    fireEvent.click(within(row).getByRole("button", { name: "Revoke key" }));

    const form = await within(row).findByRole("form", { name: `Add till for ${PARTNER.name}` });
    await waitFor(() => expect(within(form).getAllByRole("option").length).toBeGreaterThan(1));
    fireEvent.change(within(form).getByLabelText("Retailer"), { target: { value: RETAILERS[0].retailer_id } });
    fireEvent.change(within(form).getByLabelText("Location"), { target: { value: RETAILERS[0].locations[0].location_id } });
    fireEvent.change(within(form).getByLabelText("Till"), { target: { value: " TILL-2 " } });
    fireEvent.click(within(form).getByRole("button", { name: "Add till" }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => url === `/api/admin/pos/partners/${pid}/tills`)).toBe(true),
    );
    const [, init] = fetchMock.mock.calls.find(([url]) => url === `/api/admin/pos/partners/${pid}/tills`)!;
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      retailer_id: RETAILERS[0].retailer_id,
      till_ref: "TILL-2",
      location_id: RETAILERS[0].locations[0].location_id,
    });
    expect(
      fetchMock.mock.calls.some(([url]) => url === `/api/admin/pos/partners/${pid}/keys/${PARTNER.keys[0].key_id}/revoke`),
    ).toBe(true);
  });
});
