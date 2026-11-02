import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Alert, AlertDetail } from "@/lib/alerts";
import { renderWithQuery, routeFetch } from "@/test/utils";
import { AlertsBoard } from "./AlertsBoard";

afterEach(() => vi.unstubAllGlobals());

const BASE = "/api/companies/c0ffee00-0000-4000-8000-000000000001/alerts";
const ID = "a1a1a1a1-0000-4000-8000-000000000001";
const BANNED = /\b(original|genuine|authentic|safe|unsafe|fake|adulteration)\b|verified by nafdac/i;

const ALERT: Alert = {
  alert_id: ID,
  rule: "R2_IMPOSSIBLE_TRAVEL",
  rule_name: "Seen too far apart, too quickly",
  level: "HIGH",
  status: "OPEN",
  explanation: "Seen in Lagos at 09:00 on 30 Oct 2026 and in Kano at 12:00 on 30 Oct 2026: 832 km apart in 3 h 0 min (about 277 km/h).",
  occurrences: 1,
  manufacturer_name: "Demo Harvest Foods (fictional)",
  product_name: "Sample Palm Oil",
  batch_number: "DEMO-LOT-101",
  carton_ref: null,
  area: "Kano",
  created_at: "2026-10-30T11:00:00Z",
  updated_at: "2026-10-30T11:00:00Z",
  resolved_by_name: null,
  resolved_at: null,
};

function detail(overrides: Partial<AlertDetail> = {}): AlertDetail {
  return {
    ...ALERT,
    snapshot: [{ at: "2026-10-30T11:00:00Z", explanation: ALERT.explanation }],
    notes: [],
    ...overrides,
  };
}

function sent(fetchMock: ReturnType<typeof routeFetch>, path: string) {
  return fetchMock.mock.calls
    .filter(([url]) => url === path)
    .map(([, init]) => JSON.parse((init as RequestInit).body as string));
}

async function openAlert() {
  fireEvent.click(await screen.findByRole("button", { name: /Seen too far apart, too quickly/ }));
  return screen.findByRole("region", { name: "Seen too far apart, too quickly" });
}

describe("alerts board", () => {
  it("lists open alerts with level and status pills", async () => {
    routeFetch({ [`GET ${BASE}?status=OPEN`]: { body: [ALERT] } });
    renderWithQuery(<AlertsBoard base={BASE} />);

    const row = await screen.findByRole("button", { name: /Seen too far apart, too quickly/ });
    expect(row).toHaveTextContent("High");
    expect(row).toHaveTextContent("Open");
    expect(row).toHaveTextContent("Sample Palm Oil · DEMO-LOT-101 · Kano · Raised 30 Oct 2026");
    expect(
      screen.getByText("Alerts are signals to review, not verdicts. Low alerts show only here, never to buyers."),
    ).toBeInTheDocument();
  });

  it("shows the empty state and switches filters", async () => {
    const fetchMock = routeFetch({
      [`GET ${BASE}?status=OPEN`]: { body: [] },
      [`GET ${BASE}?status=RESOLVED`]: { body: [{ ...ALERT, status: "RESOLVED_LEGITIMATE" }] },
    });
    renderWithQuery(<AlertsBoard base={BASE} />);

    expect(await screen.findByText("No alerts in this list.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Resolved" }));

    expect(await screen.findByText("Resolved: legitimate")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => url === `${BASE}?status=RESOLVED`)).toBe(true);
  });

  it("shows an error with Try again", async () => {
    routeFetch({ [`GET ${BASE}?status=OPEN`]: { status: 500, body: { detail: "Server error" } } });
    renderWithQuery(<AlertsBoard base={BASE} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Server error");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("shows the evidence and sends only the new status", async () => {
    let current = detail();
    const fetchMock = routeFetch({
      [`GET ${BASE}?status=OPEN`]: { body: [ALERT] },
      [`GET ${BASE}/${ID}`]: () => ({ body: current }),
      [`POST ${BASE}/${ID}/status`]: () => {
        current = detail({ status: "RESOLVED_SUSPECTED_COPY", resolved_by_name: "Ada Staff", resolved_at: "2026-10-31T09:00:00Z" });
        return { body: current };
      },
    });
    renderWithQuery(<AlertsBoard base={BASE} />);
    const panel = await openAlert();

    expect(within(panel).getByRole("heading", { name: "Evidence" })).toBeInTheDocument();
    expect(within(panel).getAllByText(ALERT.explanation).length).toBeGreaterThan(0);
    expect(within(panel).getByRole("button", { name: "Mark investigating" })).toBeInTheDocument();
    fireEvent.click(within(panel).getByRole("button", { name: "Resolve as suspected copy" }));

    await waitFor(() => expect(sent(fetchMock, `${BASE}/${ID}/status`)).toEqual([{ status: "RESOLVED_SUSPECTED_COPY" }]));
    expect(await screen.findByText(/Resolved by Ada Staff on 31 Oct 2026/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reopen" })).toBeInTheDocument();
  });

  it("adds a trimmed note and shows who wrote it", async () => {
    let current = detail();
    const fetchMock = routeFetch({
      [`GET ${BASE}?status=OPEN`]: { body: [ALERT] },
      [`GET ${BASE}/${ID}`]: () => ({ body: current }),
      [`POST ${BASE}/${ID}/notes`]: () => {
        current = detail({ notes: [{ author_name: "Ada Staff", body: "Asked the depot.", created_at: "2026-10-31T09:00:00Z" }] });
        return { body: current };
      },
    });
    renderWithQuery(<AlertsBoard base={BASE} />);
    const panel = await openAlert();

    const add = within(panel).getByRole("button", { name: "Add note" });
    expect(add).toBeDisabled();
    fireEvent.change(within(panel).getByLabelText("Note"), { target: { value: "  Asked the depot.  " } });
    fireEvent.click(add);

    await waitFor(() => expect(sent(fetchMock, `${BASE}/${ID}/notes`)).toEqual([{ body: "Asked the depot." }]));
    expect(await within(panel).findByText("Ada Staff · 31 Oct 2026")).toBeInTheDocument();
  });

  it("marks an admin-only alert and uses no banned words", async () => {
    const burst: Alert = {
      ...ALERT,
      rule: "R4_INVALID_BURST",
      rule_name: "Burst of unrecognised codes",
      level: "MEDIUM",
      manufacturer_name: null,
      product_name: null,
      batch_number: null,
      area: null,
    };
    routeFetch({ "GET /api/admin/alerts?status=OPEN": { body: [burst] } });
    const { container } = renderWithQuery(<AlertsBoard base="/api/admin/alerts" />);

    expect(await screen.findByText(/Admin only \(no pack\)/)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(BANNED);
  });
});
