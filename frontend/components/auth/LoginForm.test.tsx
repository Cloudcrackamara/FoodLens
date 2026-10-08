import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { demoUser, mockFetch, renderWithQuery } from "@/test/utils";
import { LoginForm } from "./LoginForm";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

describe("LoginForm", () => {
  beforeEach(() => push.mockReset());
  afterEach(() => vi.unstubAllGlobals());

  it("shows field errors and does not call the API when empty", () => {
    const fetchMock = mockFetch();
    renderWithQuery(<LoginForm />);

    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(screen.getByText("Enter your email")).toBeInTheDocument();
    expect(screen.getByText("Enter your password")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows the server message for a wrong password", async () => {
    mockFetch({ status: 401, body: { detail: "Invalid email or password" } });
    renderWithQuery(<LoginForm />);

    fill("Email", "ada@example.com");
    fill("Password", "wrong-password-1");
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password");
    expect(push).not.toHaveBeenCalled();
  });

  it("shows a friendly per-network message when rate limited", async () => {
    mockFetch({
      status: 429,
      body: { detail: "Too many requests from your network. Try again in 12 seconds." },
      headers: { "Retry-After": "12" },
    });
    renderWithQuery(<LoginForm />);

    fill("Email", "ada@example.com");
    fill("Password", "wrong-password-1");
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/shared by everyone on the same network/);
    expect(alert).toHaveTextContent(/try again in about 12 seconds/i);
  });

  it("posts credentials to the API and redirects on success", async () => {
    const fetchMock = mockFetch({ status: 200, body: demoUser });
    renderWithQuery(<LoginForm />);

    fill("Email", "ada@example.com");
    fill("Password", "correct-horse-battery");
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/auth/login");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("same-origin");
    expect(JSON.parse(init.body)).toEqual({
      email: "ada@example.com",
      password: "correct-horse-battery",
    });
  });
});
