import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AlertsBoard } from "@/components/alerts/AlertsBoard";
import { AdminOverview, PlatformStats, ScanningPanel } from "@/components/admin/AdminStats";
import { AdminScreen } from "@/components/admin/AdminScreens";
import { ReportsBoard } from "@/components/reports/ReportsBoard";
import type { Report, Stats as StatsData, Timeline } from "@/lib/dashboards";
import { demoUser, renderWithQuery, routeFetch } from "@/test/utils";
import { CompanyShell } from "./CompanyShell";
import { Inventory } from "./Inventory";
import { PackTimeline } from "./PackTimeline";
import { Partners } from "./Partners";
import { Overview, Stats } from "./Stats";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));

afterEach(() => vi.unstubAllGlobals());

const COMPANY = "c0ffee00-0000-4000-8000-000000000001";
const BASE = `/api/companies/${COMPANY}`;
const BANNED = /\b(original|genuine|authentic|safe|unsafe|fake|adulteration)\b|verified by nafdac|recall/i;

function member(overrides = {}) {
  return {
    ...demoUser,
    membership: {
      company_id: COMPANY,
      company_display_name: "Demo Harvest Foods (fictional)",
      company_review_status: "APPROVED",
      is_manufacturer: true,
      is_distributor: false,
      is_retailer: false,
      role: "OWNER",
      ...overrides,
    },
  };
}

const STATS: StatsData = {
  issued: 40,
  released: 30,
  sale_coverage_pct: 25,
  pos_sales: 6,
  merchant_sales: 2,
  pos_share_pct: 75,
  merchant_share_pct: 25,
  checks_by_city_week: [
    { week_start: "2026-10-19", city: "Kano", checks: 3 },
    { week_start: "2026-10-26", city: "Lagos", checks: 12 },
  ],
  hot_spots: [{ city: "Kano", open_alerts: 2, checks: 3 }],
  alerts: [{ rule: "R3_SCAN_VOLUME", rule_name: "Many checks in 24 hours", level: "MEDIUM", raised: 2, resolved: 1 }],
  alerts_raised: 2,
  alerts_resolved: 1,
  median_hours_to_resolve: 4.5,
};

const EMPTY_STATS: StatsData = {
  ...STATS,
  issued: 0,
  released: 0,
  sale_coverage_pct: null,
  pos_sales: 0,
  merchant_sales: 0,
  pos_share_pct: null,
  merchant_share_pct: null,
  checks_by_city_week: [],
  hot_spots: [],
  alerts: [],
  alerts_raised: 0,
  alerts_resolved: 0,
  median_hours_to_resolve: null,
};

const TIMELINE: Timeline = {
  subject: "PACK",
  code_last4: "BZ3F",
  product_name: "Sample Palm Oil",
  size: "1 L",
  batch_number: "DEMO-LOT-101",
  expiry_date: "2027-11-12",
  status: "IN_STOCK",
  entries: [
    { at: "2026-10-01T09:00:00Z", event_type: "RELEASED", text: "Released for sale by Demo Harvest Foods on 1 Oct 2026.", note: null },
    { at: "2026-10-02T09:00:00Z", event_type: "RECEIVED", text: "Received by Demo Corner Shop in Kano on 2 Oct 2026.", note: "Received outside its allocation." },
  ],
  open_alerts: [{ alert_id: "a1", rule_name: "Many checks in 24 hours", level: "MEDIUM" }],
};

const REPORT: Report = {
  report_id: "r1r1r1r1-0000-4000-8000-000000000001",
  concern_type: "PACKAGING",
  description: "The seal looked broken.",
  status: "NEW",
  manufacturer_name: null,
  product_name: "Sample Palm Oil",
  batch_number: "DEMO-LOT-101",
  area: "Lagos",
  created_at: "2026-10-30T09:00:00Z",
};

describe("company shell", () => {
  it("gives an approved manufacturer the full navigation", async () => {
    routeFetch({ "GET /api/auth/me": { body: member() } });
    renderWithQuery(
      <CompanyShell href="/company/stats" title="Stats" manufacturerOnly>
        {() => <p>Page body</p>}
      </CompanyShell>,
    );

    expect(await screen.findByText("Page body")).toBeInTheDocument();
    expect(screen.getByText("COMPANY")).toBeInTheDocument();
    const [sidebar] = screen.getAllByRole("navigation", { name: "Business navigation" });
    const labels = within(sidebar).getAllByRole("link").map((link) => link.textContent);
    expect(labels).toEqual([
      "Overview",
      "Products and batches",
      "Pack timeline",
      "Alerts",
      "Notices",
      "Partners",
      "Consumer reports",
      "Stats",
      "Company profile",
    ]);
    expect(within(sidebar).getByRole("link", { name: "Stats" })).toHaveAttribute("aria-current", "page");
  });

  it("gives a retailer only its profile and the merchant page, and blocks manufacturer pages", async () => {
    routeFetch({ "GET /api/auth/me": { body: member({ is_manufacturer: false, is_retailer: true }) } });
    renderWithQuery(
      <CompanyShell href="/company/stats" title="Stats" manufacturerOnly>
        {() => <p>Page body</p>}
      </CompanyShell>,
    );

    expect(await screen.findByText("Only manufacturer companies manage pack codes")).toBeInTheDocument();
    expect(screen.queryByText("Page body")).not.toBeInTheDocument();
    const [sidebar] = screen.getAllByRole("navigation", { name: "Business navigation" });
    expect(within(sidebar).getAllByRole("link").map((link) => link.textContent)).toEqual([
      "Company profile",
      "Record events",
    ]);
  });

  it("holds an unapproved manufacturer back from manufacturer pages", async () => {
    routeFetch({ "GET /api/auth/me": { body: member({ company_review_status: "PENDING_REVIEW" }) } });
    renderWithQuery(
      <CompanyShell href="/company/products" title="Products and batches" manufacturerOnly>
        {() => <p>Page body</p>}
      </CompanyShell>,
    );

    expect(await screen.findByText("Pack codes can be managed after FoodLens approves your company profile")).toBeInTheDocument();
  });

  it("asks a signed-out visitor to sign in, and a user with no company to register", async () => {
    routeFetch({ "GET /api/auth/me": { status: 401, body: { detail: "Not signed in" } } });
    const first = renderWithQuery(<CompanyShell href="/company" title="Overview">{() => <p>Page body</p>}</CompanyShell>);
    expect(await screen.findByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
    first.unmount();

    routeFetch({ "GET /api/auth/me": { body: demoUser } });
    renderWithQuery(<CompanyShell href="/company" title="Overview">{() => <p>Page body</p>}</CompanyShell>);
    expect(await screen.findByRole("link", { name: "Register your company" })).toHaveAttribute("href", "/company/register");
  });
});

describe("admin screen", () => {
  it("refuses a non-admin and shows the admin navigation to an admin", async () => {
    routeFetch({ "GET /api/auth/me": { body: member() } });
    const refused = renderWithQuery(<AdminScreen href="/admin">Admin body</AdminScreen>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Admin access required.");
    expect(screen.queryByText("Admin body")).not.toBeInTheDocument();
    refused.unmount();

    routeFetch({ "GET /api/auth/me": { body: { ...demoUser, is_admin: true } } });
    renderWithQuery(<AdminScreen href="/admin/scanning">Admin body</AdminScreen>);
    expect(await screen.findByText("Admin body")).toBeInTheDocument();
    const [sidebar] = screen.getAllByRole("navigation", { name: "Admin navigation" });
    expect(within(sidebar).getAllByRole("link").map((link) => link.textContent)).toEqual([
      "Overview",
      "Review queues",
      "POS partners",
      "Alerts",
      "Consumer reports",
      "Platform stats",
      "Automated scanning",
    ]);
  });
});

describe("stats", () => {
  it("shows each stat and the coverage note, with no recall reach", async () => {
    routeFetch({ [`GET ${BASE}/stats`]: { body: STATS } });
    const { container } = renderWithQuery(<Stats companyId={COMPANY} />);

    const summary = await screen.findByRole("region", { name: "Stats summary" });
    expect(summary).toHaveTextContent("Packs issued40");
    expect(summary).toHaveTextContent("Packs released30");
    expect(summary).toHaveTextContent("Sale coverage25%");
    expect(summary).toHaveTextContent("POS sales675%");
    expect(summary).toHaveTextContent("Merchant page sales225%");
    expect(summary).toHaveTextContent("Median time to resolve4.5 h");
    expect(screen.getByText(/Sale coverage counts only sales recorded on FoodLens/)).toBeInTheDocument();

    const checks = screen.getByRole("table", { name: "Checks by city and week" });
    expect(within(checks).getByRole("cell", { name: "19 Oct 2026" })).toBeInTheDocument();
    expect(within(checks).getByRole("cell", { name: "Lagos" })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Hot spots" })).toHaveTextContent("Kano23");
    expect(screen.getByRole("table", { name: "Alerts by rule and level" })).toHaveTextContent("Many checks in 24 hours");
    expect(container.textContent).not.toMatch(BANNED);
  });

  it("says so when no check came from a known place", async () => {
    routeFetch({ [`GET ${BASE}/stats`]: { body: { ...STATS, hot_spots: [] } } });
    renderWithQuery(<Stats companyId={COMPANY} />);

    const section = await screen.findByRole("heading", { name: "Hot spots" });
    expect(section.parentElement).toHaveTextContent("No checks from a known place yet.");
  });

  it("shows the empty state before anything is issued", async () => {
    routeFetch({ [`GET ${BASE}/stats`]: { body: EMPTY_STATS } });
    renderWithQuery(<Stats companyId={COMPANY} />);

    expect(await screen.findByText("Nothing to show yet. Stats appear once packs are released and checked.")).toBeInTheDocument();
  });

  it("shows an error with Try again, and refetches", async () => {
    const fetchMock = routeFetch({ [`GET ${BASE}/stats`]: { status: 500, body: { detail: "Server error" } } });
    renderWithQuery(<Stats companyId={COMPANY} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Server error");
    const before = fetchMock.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(before));
  });

  it("shows a loading state first", () => {
    routeFetch({ [`GET ${BASE}/stats`]: { body: STATS } });
    renderWithQuery(<Stats companyId={COMPANY} />);

    expect(screen.getByLabelText("Loading")).toBeInTheDocument();
  });

  it("links each overview card to its page", async () => {
    routeFetch({ [`GET ${BASE}/stats`]: { body: STATS } });
    renderWithQuery(<Overview companyId={COMPANY} />);

    expect(await screen.findByRole("link", { name: /Sale coverage/ })).toHaveAttribute("href", "/company/stats");
    expect(screen.getByRole("link", { name: /Alerts raised/ })).toHaveAttribute("href", "/company/alerts");
  });
});

describe("inventory", () => {
  it("shows a row per destination and the Not allocated row", async () => {
    routeFetch({
      [`GET ${BASE}/batches/b1/inventory`]: {
        body: [
          { company_name: "Demo Corner Shop", area: "Lagos", not_allocated: false, allocated: 5, received: 3, in_stock: 2, sold: 1, returned: 1 },
          { company_name: null, area: "Kano", not_allocated: false, allocated: 4, received: 1, in_stock: 0, sold: 0, returned: 0 },
          { company_name: null, area: null, not_allocated: true, allocated: 0, received: 1, in_stock: 1, sold: 1, returned: 0 },
        ],
      },
    });
    renderWithQuery(<Inventory companyId={COMPANY} batchId="b1" />);

    const table = await screen.findByRole("table", { name: "Inventory by destination" });
    const rows = within(table).getAllByRole("row").map((row) => row.textContent);
    expect(rows).toEqual([
      "DestinationAllocatedReceivedIn stockSoldReturned",
      "Demo Corner Shop · Lagos53211",
      "Kano41000",
      "Not allocated01110",
    ]);
  });

  it("shows the empty state", async () => {
    routeFetch({ [`GET ${BASE}/batches/b1/inventory`]: { body: [] } });
    renderWithQuery(<Inventory companyId={COMPANY} batchId="b1" />);

    expect(await screen.findByText("No stock recorded yet.")).toBeInTheDocument();
  });
});

describe("pack timeline", () => {
  it("sends the normalised code in the body and shows the history in plain words", async () => {
    const fetchMock = routeFetch({ [`POST ${BASE}/units/timeline`]: { body: TIMELINE } });
    renderWithQuery(<PackTimeline companyId={COMPANY} />);

    fireEvent.change(screen.getByLabelText("The code printed under the QR"), { target: { value: "7q2m-8kd3 xh4n" } });
    fireEvent.click(screen.getByRole("button", { name: "Look up" }));

    const card = await screen.findByRole("region", { name: "Pack timeline" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/units/timeline`);
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({ code: "7Q2M8KD3XH4N" });
    expect(card).toHaveTextContent("Released for sale by Demo Harvest Foods on 1 Oct 2026.");
    expect(card).toHaveTextContent("Received outside its allocation.");
    expect(card).toHaveTextContent("Code ending BZ3F");
    expect(within(card).getByRole("heading", { name: "Open alerts on this pack" })).toBeInTheDocument();
    expect(card).toHaveTextContent("Many checks in 24 hours");
  });

  it("shows the server's message for a code that is not this company's", async () => {
    routeFetch({
      [`POST ${BASE}/units/timeline`]: { status: 404, body: { detail: "We couldn't find that code among your packs." } },
    });
    renderWithQuery(<PackTimeline companyId={COMPANY} />);

    fireEvent.change(screen.getByLabelText("The code printed under the QR"), { target: { value: "7Q2M" } });
    fireEvent.click(screen.getByRole("button", { name: "Look up" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("We couldn't find that code among your packs.");
  });

  it("shows the timeline on a pack's alert, and none on an alert with no pack", async () => {
    const alert = {
      alert_id: "a1",
      rule: "R3_SCAN_VOLUME",
      rule_name: "Many checks in 24 hours",
      level: "MEDIUM",
      status: "OPEN",
      explanation: "Checked 11 times in 24 hours (alert threshold: 10 checks).",
      occurrences: 1,
      manufacturer_name: null,
      product_name: "Sample Palm Oil",
      batch_number: "DEMO-LOT-101",
      carton_ref: null,
      area: null,
      created_at: "2026-10-30T09:00:00Z",
      updated_at: "2026-10-30T09:00:00Z",
      resolved_by_name: null,
      resolved_at: null,
    };
    const burst = { ...alert, alert_id: "a2", rule: "R9_MORE_OBSERVED_THAN_ALLOCATED", rule_name: "More seen than allocated" };
    const detail = { snapshot: [], notes: [] };
    const fetchMock = routeFetch({
      [`GET ${BASE}/alerts?status=OPEN`]: { body: [alert, burst] },
      [`GET ${BASE}/alerts/a1`]: { body: { ...alert, ...detail } },
      [`GET ${BASE}/alerts/a2`]: { body: { ...burst, ...detail } },
      [`GET ${BASE}/alerts/a1/timeline`]: { body: { ...TIMELINE, code_last4: null } },
    });
    renderWithQuery(<AlertsBoard base={`${BASE}/alerts`} withTimeline />);

    fireEvent.click(await screen.findByRole("button", { name: /Many checks in 24 hours/ }));
    expect(await screen.findByRole("heading", { name: "Pack timeline" })).toBeInTheDocument();
    expect(await screen.findByText("Received by Demo Corner Shop in Kano on 2 Oct 2026.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /More seen than allocated/ }));
    await screen.findByRole("region", { name: "More seen than allocated" });
    expect(screen.queryByRole("heading", { name: "Pack timeline" })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => url === `${BASE}/alerts/a2/timeline`)).toBe(false);
  });
});

describe("partners", () => {
  it("lists partners with their places, counts and POS links", async () => {
    routeFetch({
      [`GET ${BASE}/partners`]: {
        body: [
          {
            display_name: "Demo Corner Shop",
            is_manufacturer: false,
            is_distributor: false,
            is_retailer: true,
            places: ["Kano", "Lagos"],
            received: 4,
            sold: 3,
            pos_partners: ["Demo Till Systems (fictional)"],
          },
        ],
      },
    });
    renderWithQuery(<Partners companyId={COMPANY} />);

    const table = await screen.findByRole("table", { name: "Partners" });
    expect(table).toHaveTextContent("Kano, Lagos");
    expect(table).toHaveTextContent("Demo Till Systems (fictional)");
  });

  it("shows the empty state", async () => {
    routeFetch({ [`GET ${BASE}/partners`]: { body: [] } });
    renderWithQuery(<Partners companyId={COMPANY} />);

    expect(await screen.findByText("No partners yet. Companies appear here once they record your packs.")).toBeInTheDocument();
  });
});

describe("consumer reports", () => {
  const url = `${BASE}/reports`;

  it("shows a report and sends only the new status", async () => {
    const fetchMock = routeFetch({
      [`GET ${url}?status=NEW`]: { body: [REPORT] },
      [`POST ${url}/${REPORT.report_id}/status`]: { body: { ...REPORT, status: "REVIEWED" } },
    });
    renderWithQuery(<ReportsBoard base={url} />);

    const row = await screen.findByRole("listitem", { name: "Packaging or label looks different" });
    expect(row).toHaveTextContent("Sample Palm Oil · DEMO-LOT-101");
    expect(row).toHaveTextContent("The seal looked broken.");
    fireEvent.click(within(row).getByRole("button", { name: "Mark reviewed" }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([called]) => called === `${url}/${REPORT.report_id}/status`);
      expect(JSON.parse((call![1] as RequestInit).body as string)).toEqual({ status: "REVIEWED" });
    });
  });

  it("offers no action on a closed report, and switches lists", async () => {
    routeFetch({
      [`GET ${url}?status=NEW`]: { body: [] },
      [`GET ${url}?status=CLOSED`]: { body: [{ ...REPORT, status: "CLOSED" }] },
    });
    renderWithQuery(<ReportsBoard base={url} />);

    expect(await screen.findByText("No reports in this list.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Closed" }));
    const row = await screen.findByRole("listitem", { name: "Packaging or label looks different" });
    expect(within(row).queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("admin stats", () => {
  const PLATFORM = {
    companies: 8,
    approved_companies: 6,
    packs_issued: 120,
    checks_last_30_days: 45,
    pos_partners: 1,
    open_alerts: 3,
    new_reports: 2,
    pos_rate_limit_hits_last_30_days: 7,
  };

  it("shows the platform stats", async () => {
    routeFetch({ "GET /api/admin/stats": { body: PLATFORM } });
    renderWithQuery(<PlatformStats />);

    const summary = await screen.findByRole("region", { name: "Platform stats" });
    expect(summary).toHaveTextContent("Approved companies6");
    expect(summary).toHaveTextContent("POS rate-limit hits7");
  });

  it("links the overview cards", async () => {
    routeFetch({ "GET /api/admin/stats": { body: PLATFORM } });
    renderWithQuery(<AdminOverview />);

    expect(await screen.findByRole("link", { name: /Open alerts/ })).toHaveAttribute("href", "/admin/alerts");
    expect(screen.getByRole("link", { name: /New reports/ })).toHaveAttribute("href", "/admin/reports");
  });

  it("shows the scanning panel by area and day, with the no-IP note", async () => {
    routeFetch({
      "GET /api/admin/scanning": {
        body: [{ day: "2026-10-30", area: "Lagos", rate_limit_hits: 7, invalid_codes: 2, burst_alerts: 1 }],
      },
    });
    renderWithQuery(<ScanningPanel />);

    const table = await screen.findByRole("table", { name: "Automated scanning" });
    expect(within(table).getAllByRole("row")[1]).toHaveTextContent("30 Oct 2026Lagos721");
    expect(screen.getByText("Counts by area and day only. FoodLens stores no IP addresses.")).toBeInTheDocument();
  });

  it("shows the scanning panel's empty state and error", async () => {
    routeFetch({ "GET /api/admin/scanning": { body: [] } });
    const first = renderWithQuery(<ScanningPanel />);
    expect(await screen.findByText("No activity in the last 30 days.")).toBeInTheDocument();
    first.unmount();

    routeFetch({ "GET /api/admin/scanning": { status: 500, body: { detail: "Server error" } } });
    renderWithQuery(<ScanningPanel />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Server error");
  });
});
