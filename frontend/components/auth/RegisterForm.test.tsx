import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { demoUser, mockFetch, renderWithQuery } from "@/test/utils";
import { RegisterForm } from "./RegisterForm";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

describe("RegisterForm", () => {
  beforeEach(() => push.mockReset());
  afterEach(() => vi.unstubAllGlobals());

  it("rejects a short password before calling the API", () => {
    const fetchMock = mockFetch();
    renderWithQuery(<RegisterForm />);

    fill("Your name", "Ada Demo");
    fill("Email", "ada@example.com");
    fill("Password", "short");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(screen.getByText("Use at least 10 characters")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects an invalid email before calling the API", () => {
    const fetchMock = mockFetch();
    renderWithQuery(<RegisterForm />);

    fill("Your name", "Ada Demo");
    fill("Email", "not-an-email");
    fill("Password", "correct-horse-battery");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(screen.getByText("Enter a valid email address")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sends only email, password, and display name, then redirects", async () => {
    const fetchMock = mockFetch({ status: 201, body: demoUser });
    renderWithQuery(<RegisterForm />);

    fill("Your name", "Ada Demo");
    fill("Email", "ada@example.com");
    fill("Password", "correct-horse-battery");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/auth/register");
    expect(Object.keys(JSON.parse(init.body)).sort()).toEqual([
      "display_name",
      "email",
      "password",
    ]);
  });

  it("shows the server message when the email is taken", async () => {
    mockFetch({ status: 409, body: { detail: "An account with this email already exists" } });
    renderWithQuery(<RegisterForm />);

    fill("Your name", "Ada Demo");
    fill("Email", "ada@example.com");
    fill("Password", "correct-horse-battery");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "An account with this email already exists",
    );
  });
});
