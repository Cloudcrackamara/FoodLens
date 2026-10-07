import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Home from "./page";

describe("Landing page", () => {
  it("explains the demo-data limitation", () => {
    render(<Home />);

    expect(screen.getByRole("heading", { level: 1, name: "FoodLens" })).toBeInTheDocument();
    expect(screen.getByText(/not a laboratory test/i)).toBeInTheDocument();
    expect(screen.getByText(/not NAFDAC, SON, or any other regulator/i)).toBeInTheDocument();
  });

  it("never uses safety wording", () => {
    const { container } = render(<Home />);

    expect(container.textContent).not.toMatch(/\b(safe|unsafe|fake)\b/i);
  });
});
