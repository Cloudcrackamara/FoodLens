import { fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DEMO_BANNER_TEXT } from "@/components/DemoDataBanner";
import { demoUser, renderWithQuery, routeFetch } from "@/test/utils";
import { MerchantShell } from "./MerchantShell";
import { TeamPage } from "./TeamPage";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));

afterEach(() => vi.unstubAllGlobals());

const COMPANY = "c0ffee00-0000-4000-8000-000000000001";

function member(overrides = {}) {
  return {
    ...demoUser,
    membership: {
      company_id: COMPANY,
      company_display_name: "Demo Corner Shop",
      company_review_status: "APPROVED",
      is_manufacturer: false,
      is_distributor: false,
      is_retailer: true,
      role: "OWNER",
      ...overrides,
    },
  };
}

function renderShell(me: unknown, ownerOnly = false) {
  routeFetch({ "GET /api/auth/me": me === null ? { status: 401, body: { detail: "x" } } : { body: me } });
  return renderWithQuery(
    <MerchantShell href="/merchant" title="Record stock events" ownerOnly={ownerOnly}>
      {({ companyId, role }) => <p>Inside {companyId} as {role}</p>}
    </MerchantShell>,
  );
}

describe("merchant shell", () => {
  it("shows the workspace shell with one demo banner to an approved retailer", async () => {
    renderShell(member());

    expect(await screen.findByText(`Inside ${COMPANY} as OWNER`)).toBeInTheDocument();
    expect(screen.getAllByText(DEMO_BANNER_TEXT, { selector: "[role=note]" })).toHaveLength(1);
    expect(screen.getAllByText("Retailer")[0]).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Record events" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Team" })).toBeInTheDocument();
  });

  it("hides Team from staff and blocks owner-only pages", async () => {
    renderShell(member({ role: "STAFF" }), true);

    expect(await screen.findByText("Only the owner can manage the team")).toBeInTheDocument();
  });

  it.each([
    ["a pending company", member({ company_review_status: "PENDING_REVIEW" })],
    ["a manufacturer only", member({ is_manufacturer: true, is_retailer: false })],
  ])("turns away %s", async (_, me) => {
    renderShell(me);

    expect(await screen.findByText("This page is for approved distributors and retailers")).toBeInTheDocument();
    expect(screen.queryByText(/Inside/)).not.toBeInTheDocument();
  });

  it("asks a signed-out visitor to sign in", async () => {
    renderShell(null);

    expect(await screen.findByText("Sign in to record stock events")).toBeInTheDocument();
  });

  it("opens the navigation drawer on small screens", async () => {
    renderShell(member());
    await screen.findByText(/Inside/);

    fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));

    expect(screen.getByRole("button", { name: "Open navigation" })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getAllByRole("complementary", { name: "Business sidebar" })).toHaveLength(2);
  });
});

describe("team page", () => {
  const MEMBERS = `/api/companies/${COMPANY}/members`;

  it("adds staff by email and deactivates them", async () => {
    let roster = [
      { member_id: "m1", email: "owner@example.test", display_name: "Ada Owner", role: "OWNER", membership_status: "ACTIVE" },
      { member_id: "m2", email: "staff@example.test", display_name: "Bayo Staff", role: "STAFF", membership_status: "ACTIVE" },
    ];
    const fetchMock = routeFetch({
      [`GET ${MEMBERS}`]: () => ({ body: roster }),
      [`POST ${MEMBERS}`]: (init) => {
        const { email } = JSON.parse(init.body as string);
        const added = { member_id: "m3", email, display_name: "Chi New", role: "STAFF", membership_status: "ACTIVE" };
        roster = [...roster, added];
        return { status: 201, body: added };
      },
      [`POST ${MEMBERS}/m2/deactivate`]: () => {
        roster = roster.map((m) => (m.member_id === "m2" ? { ...m, membership_status: "INACTIVE" } : m));
        return { body: roster[1] };
      },
    });
    renderWithQuery(<TeamPage companyId={COMPANY} />);

    expect(await screen.findByText("Bayo Staff")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Deactivate Ada Owner" })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Their account email"), { target: { value: "new@example.test" } });
    fireEvent.click(screen.getByRole("button", { name: "Add staff member" }));
    expect(await screen.findByText("Chi New")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Deactivate Bayo Staff" }));
    expect(await screen.findByText("Deactivated")).toBeInTheDocument();

    const posts = fetchMock.mock.calls.filter(([url, init]) => url === MEMBERS && (init as RequestInit).method === "POST");
    expect(JSON.parse((posts[0][1] as RequestInit).body as string)).toEqual({ email: "new@example.test" });
  });

  it("shows why a person can't be added", async () => {
    routeFetch({
      [`GET ${MEMBERS}`]: { body: [] },
      [`POST ${MEMBERS}`]: { status: 409, body: { detail: "That person already belongs to a company." } },
    });
    renderWithQuery(<TeamPage companyId={COMPANY} />);

    fireEvent.change(screen.getByLabelText("Their account email"), { target: { value: "x@example.test" } });
    fireEvent.click(screen.getByRole("button", { name: "Add staff member" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("That person already belongs to a company.");
  });
});
