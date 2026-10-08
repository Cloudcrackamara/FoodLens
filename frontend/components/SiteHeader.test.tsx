import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { demoUser, mockFetch, renderWithQuery } from "@/test/utils";
import { SiteHeader } from "./SiteHeader";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

describe("SiteHeader", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("offers sign in and registration when signed out", async () => {
    mockFetch({ status: 401, body: { detail: "Not signed in" } });
    renderWithQuery(<SiteHeader />);

    expect(await screen.findByRole("link", { name: "Sign in" })).toHaveAttribute(
      "href",
      "/login",
    );
    expect(screen.getByRole("link", { name: "Create account" })).toHaveAttribute(
      "href",
      "/register",
    );
  });

  it("shows the user's name and a sign-out button when signed in", async () => {
    mockFetch({ status: 200, body: demoUser });
    renderWithQuery(<SiteHeader />);

    expect(await screen.findByText("Ada Demo")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Sign in" })).not.toBeInTheDocument();
  });
});
