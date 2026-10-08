import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { vi } from "vitest";

export function renderWithQuery(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

/** Stub global fetch with a queue of JSON responses, returned in order. */
export function mockFetch(
  ...responses: { status: number; body?: unknown; headers?: Record<string, string> }[]
) {
  const fetchMock = vi.fn();
  for (const { status, body, headers } of responses) {
    fetchMock.mockResolvedValueOnce(
      new Response(body === undefined ? null : JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json", ...headers },
      }),
    );
  }
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export const demoUser = {
  user_id: "11111111-1111-1111-1111-111111111111",
  email: "ada@example.com",
  display_name: "Ada Demo",
  is_admin: false,
  membership: null,
};
