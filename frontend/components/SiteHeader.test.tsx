import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { demoUser, mockFetch, renderWithQuery } from "@/test/utils";
import { distributorUser } from "@/test/orderFixtures";
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

describe("SiteHeader role links", () => {
  afterEach(() => vi.unstubAllGlobals());

  it.each([
    [{ ...demoUser, is_admin: true }, "Admin", "/admin"],
    [
      {
        ...demoUser,
        membership: {
          company_id: "c1",
          company_display_name: "Demo Co",
          company_review_status: "PENDING_REVIEW",
          is_manufacturer: true,
          is_distributor: false,
          is_retailer: false,
          role: "OWNER",
        },
      },
      "My company",
      "/company",
    ],
    [demoUser, "Register company", "/company/register"],
  ])("links signed-in users to the right place", async (user, label, href) => {
    mockFetch({ status: 200, body: user });
    renderWithQuery(<SiteHeader />);

    expect(await screen.findByRole("link", { name: label })).toHaveAttribute("href", href);
    expect(screen.getByRole("link", { name: "Partners" })).toHaveAttribute("href", "/suppliers");
    expect(screen.getByRole("link", { name: "Check a pack" })).toHaveAttribute("href", "/check");
  });
});

describe("SiteHeader orders link", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("hides My orders while order requests are switched off (the default, D127)", async () => {
    mockFetch({ status: 200, body: distributorUser });
    renderWithQuery(<SiteHeader />);

    await screen.findByRole("link", { name: "My company" });
    expect(screen.queryByRole("link", { name: "My orders" })).not.toBeInTheDocument();
  });
});
