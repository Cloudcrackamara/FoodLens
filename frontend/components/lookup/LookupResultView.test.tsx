import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { lookupResults } from "@/lib/lookup";
import { lookupFixtures } from "@/test/lookupFixtures";
import { LookupResultView } from "./LookupResultView";

const BANNED_WORDS = /\b(safe|unsafe|fake)\b/i;

describe("LookupResultView", () => {
  it.each(lookupResults)("shows the demo banner, title and disclaimer for %s", (result) => {
    const response = lookupFixtures[result];
    render(<LookupResultView response={response} />);

    const section = screen.getByRole("region", { name: response.title });
    expect(within(section).getByRole("note", { name: "Demo data notice" })).toHaveTextContent(
      "DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE",
    );
    expect(within(section).getByRole("heading", { level: 2 })).toHaveTextContent(response.title);
    expect(section).toHaveTextContent("not a NAFDAC or SON decision");
  });

  it.each(lookupResults)("never shows safe, unsafe or fake for %s", (result) => {
    const { container } = render(<LookupResultView response={lookupFixtures[result]} />);

    expect(container.textContent).not.toMatch(BANNED_WORDS);
  });

  it("shows agency, scheme, reference, status, validity and provenance", () => {
    render(<LookupResultView response={lookupFixtures.DEMO_RECORD_FOUND} />);

    const card = screen.getByRole("listitem", {
      name: "Product-level credential DEMO-NAFDAC-0001",
    });
    expect(card).toHaveTextContent("NAFDAC (simulated)");
    expect(card).toHaveTextContent("Food product registration (demo)");
    expect(card).toHaveTextContent("DEMO-NAFDAC-0001");
    expect(card).toHaveTextContent("Active in demo data");
    expect(card).toHaveTextContent("26 May 2025 to 12 Nov 2027");
    expect(card).toHaveTextContent("Not from any regulator");
    expect(card).toHaveTextContent("Last checked8 Oct 2026");
  });

  it("presents credentials as product-level, never as a batch certificate", () => {
    render(<LookupResultView response={lookupFixtures.DEMO_RECORD_FOUND} />);

    expect(
      screen.getByRole("heading", { name: "Product-level credential records" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/not to this batch, and are not a batch certificate/)).toBeInTheDocument();
    expect(screen.getByText("Product-level · Demo data")).toBeInTheDocument();
    // The batch section lists only batch facts, no credential.
    const batchHeading = screen.getByRole("heading", { name: "Batch (demo record)" });
    expect(batchHeading.parentElement).not.toHaveTextContent(/NAFDAC|MANCAP|credential/i);
  });

  it("shows expired credential status", () => {
    render(<LookupResultView response={lookupFixtures.CREDENTIAL_EXPIRED_OR_INACTIVE} />);

    expect(screen.getByText("Expired in demo data")).toBeInTheDocument();
  });

  it("names the field that differs", () => {
    render(<LookupResultView response={lookupFixtures.DETAILS_MISMATCH} />);

    expect(screen.getByText("Field that differs:").parentElement).toHaveTextContent(
      "Product code",
    );
  });

  it("lets the user choose between ambiguous products", () => {
    const choose = vi.fn();
    render(
      <LookupResultView
        response={lookupFixtures.INSUFFICIENT_OR_AMBIGUOUS}
        onChooseCandidate={choose}
      />,
    );

    fireEvent.click(screen.getAllByRole("button", { name: "Choose this product" })[1]);

    expect(choose).toHaveBeenCalledWith("DEMO-PC-0002");
  });
});
