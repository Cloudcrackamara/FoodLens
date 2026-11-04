import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { screen } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DEMO_BANNER_TEXT } from "@/components/DemoDataBanner";
import { checkFixtures, DEMO_CODE } from "@/test/checkFixtures";
import { renderWithQuery, routeFetch } from "@/test/utils";
import { LinkCheck } from "./LinkCheck";

afterEach(() => vi.unstubAllGlobals());

function api() {
  return routeFetch({
    "GET /api/check/demo-cities": { status: 404, body: { detail: "off" } },
    "POST /api/check/qr": { body: checkFixtures.justSold },
  });
}

const checks = (fetchMock: ReturnType<typeof api>) =>
  fetchMock.mock.calls.filter(([url]) => url === "/api/check/qr");

describe("/p/[token]", () => {
  it("makes no request while rendering on the server (link previews)", () => {
    const fetchMock = api();
    const client = new QueryClient();

    const html = renderToString(
      <QueryClientProvider client={client}>
        <LinkCheck token={DEMO_CODE} />
      </QueryClientProvider>,
    );

    expect(fetchMock).not.toHaveBeenCalled();
    expect(html).not.toContain("Just sold");
  });

  it("checks with one POST after mount and shows the result", async () => {
    const fetchMock = api();

    renderWithQuery(<LinkCheck token={DEMO_CODE.toLowerCase()} />);

    expect(await screen.findByRole("heading", { level: 2, name: "Just sold" })).toBeInTheDocument();
    expect(screen.getByText(DEMO_BANNER_TEXT, { selector: "[role=note]" })).toBeInTheDocument();
    expect(checks(fetchMock)).toHaveLength(1);
    const [, init] = checks(fetchMock)[0];
    expect((init as RequestInit).method).toBe("POST");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      code: DEMO_CODE,
      identifier_type: "QR",
      simulated_city: null,
    });
  });

  it("does not send a link that is not a code", () => {
    const fetchMock = api();

    renderWithQuery(<LinkCheck token="menu" />);

    expect(screen.getByRole("heading", { name: "This link is not a FoodLens code" })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
