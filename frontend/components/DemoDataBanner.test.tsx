import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DEMO_BANNER_TEXT, DemoDataBanner } from "./DemoDataBanner";

describe("DemoDataBanner", () => {
  it("shows the exact demo-data notice", () => {
    render(<DemoDataBanner />);

    const banner = screen.getByRole("note", { name: "Demo data notice" });
    expect(banner).toHaveTextContent("DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE");
    expect(DEMO_BANNER_TEXT).toBe("DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE");
  });
});
