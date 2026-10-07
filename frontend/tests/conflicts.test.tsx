import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FuturesHome } from "../src/components/FuturesHome";

describe("cross-plan conflict view", () => {
  it("opens the conflict the analyzer returned", () => {
    render(
      <FuturesHome
        futures={[
          { future_id: "demo-airport", plan_id: "demo-airport", name: "NYC airport window", status: "HEALTHY", material_unknowns: 0, nearest_failure: "" },
          { future_id: "demo-opening", plan_id: "demo-opening", name: "Gallery opening", status: "HEALTHY", material_unknowns: 0, nearest_failure: "" },
        ]}
        conflicts={[
          {
            conflict_id: "PROTECTED_RESOURCE:alex:demo-opening:demo-airport",
            future_ids: ["demo-opening", "demo-airport"],
            future_names: ["Gallery opening", "NYC airport window"],
            conflict_type: "PROTECTED_RESOURCE",
            resource_id: "alex",
            description: "These futures are individually valid but incompatible together.",
            violated_constraint: "Gallery opening is protected and overlaps Airport travel",
            severity: "hard",
            repairable: true,
          },
        ]}
        onOpen={() => undefined}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "1 cross-plan conflict" }));
    expect(screen.getByText("These futures are individually valid but incompatible together.")).toBeTruthy();
    expect(screen.getByText("This plan works alone, but conflicts with another future.")).toBeTruthy();
    expect(screen.getByText(/Shared resource: alex/)).toBeTruthy();
  });
});
