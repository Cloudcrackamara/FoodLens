import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { lookupResults } from "@/lib/lookup";
import { lookupFixtures } from "@/test/lookupFixtures";
import { LookupResultView } from "./LookupResultView";

const BANNED = /\b(safe|unsafe|fake|genuine)\b|verified by nafdac/i;

describe("LookupResultView", () => {
  it.each(lookupResults)("shows the demo banner, title and disclaimer for %s", (result) => {
    const response = lookupFixtures[result];
    render(<LookupResultView response={response} />);

    const section = screen.getByRole("region", { name: response.title });
    expect(within(section).getByRole("note", { name: "Demo data notice" })).toHaveTextContent(
      "DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE",
    );
    expect(within(section).getByRole("heading", { level: 2 })).toHaveTextContent(response.title);
    expect(section).toHaveTextContent("not NAFDAC's or SON's own system");
  });

  it.each(lookupResults)("never says safe, unsafe, fake, genuine or verified for %s", (result) => {
    const { container } = render(<LookupResultView response={lookupFixtures[result]} />);

    expect(container.textContent).not.toMatch(BANNED);
  });

  it("shows the simulated register record for the consumer to compare with the pack", () => {
    render(<LookupResultView response={lookupFixtures.REGISTERED_ACTIVE} />);

    const card = screen.getByLabelText("Simulated register record");
    expect(card).toHaveTextContent("Simulated register record · Demo data");
    expect(card).toHaveTextContent("NAFDAC (simulated)");
    expect(card).toHaveTextContent("DEMO-NAFDAC-0001");
    expect(card).toHaveTextContent("Registered productSample Palm Oil");
    expect(card).toHaveTextContent("Registered companyDemo Harvest Foods (fictional) Ltd");
    expect(card).toHaveTextContent("Active in the simulated register");
    expect(card).toHaveTextContent("Expires13 Nov 2027");
    expect(card).toHaveTextContent("Not from NAFDAC or SON");
  });

  it("explains a mismatch and shows both the register record and the catalogue product", () => {
    render(<LookupResultView response={lookupFixtures.REGISTRATION_MISMATCH} />);

    expect(screen.getByText(/names a different product or company/)).toBeInTheDocument();
    expect(screen.getByLabelText("Simulated register record")).toHaveTextContent("Sample Chin Chin");
    expect(
      screen.getByRole("heading", { name: "Product this batch belongs to (FoodLens catalogue)" })
        .parentElement,
    ).toHaveTextContent("Sample Honey");
  });

  it("shows expired register status", () => {
    render(<LookupResultView response={lookupFixtures.REGISTRATION_EXPIRED_OR_INACTIVE} />);

    expect(screen.getByText("Expired in the simulated register")).toBeInTheDocument();
  });

  it("shows no register record when the number is not found", () => {
    render(<LookupResultView response={lookupFixtures.REGISTRATION_NOT_FOUND} />);

    expect(screen.queryByLabelText("Simulated register record")).not.toBeInTheDocument();
  });
});
