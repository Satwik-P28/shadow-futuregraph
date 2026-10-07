import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { bugCount, Issues } from "../src/features/Issues";

describe("Issues", () => {
  it("counts future bugs without inventing a probability", () => {
    const failures = [
      {
        id: "f1",
        violated_constraints: ["c_dinner"],
        normalized_distance: 0.42,
        causal_trace: ["Flight delay", "Arrival at dinner"],
        perturbations: [],
      },
    ];
    expect(bugCount(failures)).toBe(1);
    render(<Issues failures={failures} onSelect={() => undefined} />);
    expect(screen.getByRole("heading", { name: "1 future bug found" })).toBeTruthy();
    expect(screen.getByText(/Nearest discovered failure/)).toBeTruthy();
  });
});
