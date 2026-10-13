import { fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { demoUser, mockFetch, renderWithQuery } from "@/test/utils";
import { manufacturerUser, wholesalerUser } from "@/test/orderFixtures";
import { SiteHeader } from "./SiteHeader";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/check",
}));

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
          company_type: "MANUFACTURER",
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
    expect(screen.getByRole("link", { name: "Suppliers" })).toHaveAttribute("href", "/suppliers");
  });
});

describe("SiteHeader orders link", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows My orders only to approved wholesaler members", async () => {
    mockFetch({ status: 200, body: wholesalerUser });
    const { unmount } = renderWithQuery(<SiteHeader />);
    expect(await screen.findByRole("link", { name: "My orders" })).toHaveAttribute("href", "/orders");
    unmount();

    mockFetch({ status: 200, body: manufacturerUser });
    renderWithQuery(<SiteHeader />);
    await screen.findByRole("link", { name: "My company" });
    expect(screen.queryByRole("link", { name: "My orders" })).not.toBeInTheDocument();
  });
});

describe("SiteHeader phone menu", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("toggles the menu button and marks the current page", async () => {
    mockFetch({ status: 401, body: { detail: "Not signed in" } });
    renderWithQuery(<SiteHeader />);

    const button = screen.getByRole("button", { name: "Menu" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveAttribute("aria-controls", "site-menu");
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");

    expect(await screen.findByRole("link", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Check a number" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Suppliers" })).not.toHaveAttribute("aria-current");
  });
});
