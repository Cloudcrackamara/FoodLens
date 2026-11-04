import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { buttonClass } from "@/lib/ui";
import { Card } from "./Card";
import { ConsumerHeader } from "./ConsumerHeader";
import { EmptyPanel, ErrorPanel, InlineError, LoadingPanel } from "./Panels";
import { StatusCard } from "./StatusCard";
import { StatusPill } from "./StatusPill";

describe("StatusPill", () => {
  it("shows its words with the tone colours", () => {
    render(<StatusPill tone="warn">Pending review</StatusPill>);

    const pill = screen.getByText("Pending review");
    expect(pill).toHaveClass("bg-warn-bg", "text-warn");
  });
});

describe("StatusCard", () => {
  it("renders the label and the headline as a level-2 heading", () => {
    render(<StatusCard tone="ok" label="Recorded" title="In circulation, not yet sold" titleId="t" />);

    expect(screen.getByText("Recorded")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "In circulation, not yet sold" })).toHaveAttribute("id", "t");
  });

  it("uses the solid red card for the bad tone", () => {
    render(<StatusCard tone="bad" label="Warning" title="Headline" />);

    expect(screen.getByRole("heading", { level: 2 }).closest("section")).toHaveClass("bg-bad-line", "text-white");
  });
});

describe("Card", () => {
  it("is a labelled region when given a label", () => {
    render(<Card aria-label="Product">Body</Card>);

    expect(screen.getByRole("region", { name: "Product" })).toHaveClass("rounded-[16px]", "bg-white");
  });

  it("has the workspace look on request", () => {
    render(
      <Card aria-label="Batches" variant="workspace">
        Body
      </Card>,
    );

    expect(screen.getByRole("region", { name: "Batches" })).toHaveClass("rounded-[12px]", "shadow-card");
  });
});

describe("ConsumerHeader", () => {
  it("has a named back link and the title", () => {
    render(<ConsumerHeader title="Check result" backHref="/check" backLabel="Back to the check" />);

    expect(screen.getByRole("link", { name: "Back to the check" })).toHaveAttribute("href", "/check");
    expect(screen.getByText("Check result")).toBeInTheDocument();
  });
});

describe("panels", () => {
  it("EmptyPanel shows the title and the next step", () => {
    render(<EmptyPanel title="No products yet." action={<a href="/x">Add a product</a>} />);

    expect(screen.getByText("No products yet.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add a product" })).toBeInTheDocument();
  });

  it("LoadingPanel is busy and keeps its text for screen readers", () => {
    render(<LoadingPanel />);

    expect(screen.getByLabelText("Loading")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("ErrorPanel is an alert and offers Try again only when it can retry", () => {
    const { rerender } = render(<ErrorPanel>Could not load.</ErrorPanel>);
    expect(screen.getByRole("alert")).toHaveTextContent("Could not load.");
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();

    const retry = vi.fn();
    rerender(<ErrorPanel onRetry={retry}>Could not load.</ErrorPanel>);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("InlineError is announced", () => {
    render(<InlineError>Wrong password.</InlineError>);

    expect(screen.getByRole("alert")).toHaveTextContent("Wrong password.");
  });
});

describe("buttonClass", () => {
  it("gives consumer primary buttons the 54px pill", () => {
    expect(buttonClass("primary", "lg")).toContain("min-h-[54px]");
    expect(buttonClass("primary", "lg")).toContain("rounded-full");
    expect(buttonClass("secondary", "md")).toContain("border-brand");
  });
});
