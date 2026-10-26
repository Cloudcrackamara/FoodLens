import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DEMO_BANNER_TEXT } from "@/components/DemoDataBanner";
import { checkFixtures, DEMO_CODE } from "@/test/checkFixtures";
import { mockFetch, renderWithQuery } from "@/test/utils";
import { CheckResultView } from "./CheckResultView";

const BANNED = /\b(original|genuine|authentic|safe|unsafe|fake|adulteration)\b|verified by nafdac/i;

afterEach(() => vi.unstubAllGlobals());

describe("CheckResultView", () => {
  it.each(Object.entries(checkFixtures))("%s shows the demo banner and no banned words", (_, result) => {
    const { container } = renderWithQuery(<CheckResultView result={result} code={DEMO_CODE} />);

    expect(screen.getByText(DEMO_BANNER_TEXT)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: result.title })).toBeInTheDocument();
    expect(container.textContent).not.toMatch(BANNED);
    // Only the last 4 characters of the code are shown.
    expect(container.textContent).not.toContain(DEMO_CODE.slice(0, 8));
  });

  it("shows the pay tip, and the purchase note changes nothing", () => {
    const fetchMock = mockFetch();
    renderWithQuery(<CheckResultView result={checkFixtures.notSold} code={DEMO_CODE} />);

    expect(screen.getByText(/Scan again after you pay/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "I've bought this" }));

    expect(screen.getByRole("status")).toHaveTextContent(
      "No sale recorded yet. Some shops don't record sales on FoodLens yet. This isn't a warning by itself.",
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("offers the purchase note only when no sale is recorded", () => {
    renderWithQuery(<CheckResultView result={checkFixtures.justSold} code={DEMO_CODE} />);

    expect(screen.queryByRole("button", { name: "I've bought this" })).not.toBeInTheDocument();
    expect(screen.getByText(/last 6 hours/)).toBeInTheDocument();
  });

  it("labels recorded facts and possible patterns separately", () => {
    renderWithQuery(<CheckResultView result={checkFixtures.suspicious} code={DEMO_CODE} />);

    const facts = screen.getByRole("region", { name: "Recorded facts" });
    const patterns = screen.getByRole("region", { name: "Possible patterns" });
    expect(within(facts).getByText(/Code issued by/)).toBeInTheDocument();
    expect(within(patterns).getByText(/too far apart/)).toBeInTheDocument();
    expect(within(facts).queryByText(/too far apart/)).not.toBeInTheDocument();
  });

  it("marks a suspicious result as a warning about a possible copy", () => {
    renderWithQuery(<CheckResultView result={checkFixtures.suspicious} code={DEMO_CODE} />);

    expect(screen.getByText("Warning")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "This code may have been copied" })).toBeInTheDocument();
  });

  it("labels company recalls as not reviewed by FoodLens", () => {
    renderWithQuery(<CheckResultView result={checkFixtures.recall} code={DEMO_CODE} />);

    const recall = screen.getByRole("region", { name: "Recall" });
    expect(within(recall).getByText("Message from the company — not reviewed by FoodLens")).toBeInTheDocument();
  });

  it("shows the NAFDAC number as information only", () => {
    renderWithQuery(<CheckResultView result={checkFixtures.notSold} code={DEMO_CODE} />);

    expect(screen.getByText("NAFDAC number (as printed)")).toBeInTheDocument();
    expect(screen.getByText(/does not check it with NAFDAC/)).toBeInTheDocument();
  });

  it("sends an anonymous report with the code and the chosen concern", async () => {
    const fetchMock = mockFetch({
      status: 201,
      body: { data_mode: "DEMO", disclaimer: "DEMO DATA", message: "Thank you. Your report was sent." },
    });
    renderWithQuery(<CheckResultView result={checkFixtures.previouslySold} code={DEMO_CODE} />);

    fireEvent.click(screen.getByRole("button", { name: "Report a concern" }));
    fireEvent.change(screen.getByLabelText("Tell us what happened"), { target: { value: "Shop said it was new." } });
    fireEvent.click(screen.getByRole("button", { name: "Send report" }));

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Thank you"));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/check/report");
    expect(JSON.parse(init.body)).toEqual({
      code: DEMO_CODE,
      concern_type: "PREVIOUSLY_SOLD",
      description: "Shop said it was new.",
      simulated_city: null,
    });
  });
});
