import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import type { FreeformResponse, PlanView } from "../src/api/types";

vi.mock("../src/graph/FutureCanvas", () => ({
  FutureCanvas: () => <div>Future Graph</div>,
}));

const TRIP = "Move my NYC trip to Friday and make sure everything still works.";
const MOVE = "I'm thinking about moving apartments next month. Does this plan actually work?";

function statusResponse(): Response {
  return new Response(JSON.stringify({
    connected_tools: { calendar: "SANDBOX", mail: "SANDBOX", travel: "SANDBOX", search: "OFF" },
  }), { status: 200, headers: { "Content-Type": "application/json" } });
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const supportedPlan: PlanView = {
  id: "p1",
  text: TRIP,
  scenario_id: "travel",
  status: "ANALYZED",
  provider_mode: "SANDBOX",
  stages: [{ name: "SEARCHING_FAILURES" }],
  coverage: { summary: "Known unknowns remain.", unknown: 1, percentage: null },
  graph: { nodes: [], edges: [] },
  naive_repair_id: "b1440",
  recommended_repair_id: "b1120",
  repairs: [],
  failures: [],
  diff: null,
  reconciliation: null,
  observability: { model_calls: 0, worlds_simulated: 1, repairs_tested: 2 },
  no_feasible_message: null,
  contract: null,
  watch: {
    monitoring: false,
    approved_futures: 0,
    last_checked_at: null,
    drift_status: null,
    message: null,
    skill_name: null,
  },
};

function installFetch(reply: (text: string, demo: string | null) => unknown) {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/api/personal-ai/status")) return statusResponse();
    const body = JSON.parse(String(init?.body)) as { text: string; demo_context_id: string | null };
    return jsonResponse(reply(body.text, body.demo_context_id));
  }));
}

describe("freeform planning", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends the exact textarea text", async () => {
    const seen: string[] = [];
    installFetch((text, demo) => {
      seen.push(`${text}|${demo}`);
      return { modelability: { status: "UNSUPPORTED", reason: "I don't have enough grounded information or executable structure to model this as a future.", missing_information: [], compiled_constraints: [], compiled_dependencies: [], available_actions: [], selected_skill: null, provenance: "world compiler" }, plan: null } satisfies FreeformResponse;
    });
    render(<App />);
    const custom = "Should I marry this person?";
    fireEvent.change(screen.getByLabelText("What are you planning?"), { target: { value: custom } });
    fireEvent.click(screen.getByRole("button", { name: "Analyze my future" }));
    await waitFor(() => expect(seen).toEqual([`${custom}|null`]));
  });

  it("fills the NYC example without analyzing it", () => {
    installFetch(() => {
      throw new Error("example chip must not analyze");
    });
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "NYC trip" }));
    expect(screen.getByLabelText("What are you planning?")).toHaveProperty("value", TRIP);
    expect(screen.getByText("EXAMPLE CONTEXT")).toBeTruthy();
  });

  it("does not overwrite an edit unless the example is clicked again", async () => {
    const seen: string[] = [];
    installFetch((text) => {
      seen.push(text);
      return { modelability: { status: "NEEDS_INFORMATION", reason: "I can model this plan, but I need more grounded information first.", missing_information: ["your maximum extra budget"], compiled_constraints: [], compiled_dependencies: [], available_actions: [], selected_skill: "Reschedule Trip", provenance: "world compiler" }, plan: null };
    });
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "NYC trip" }));
    const edited = `${TRIP} Keep dinner.`;
    fireEvent.change(screen.getByLabelText("What are you planning?"), { target: { value: edited } });
    expect(screen.queryByText("EXAMPLE CONTEXT")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Analyze my future" }));
    await waitFor(() => expect(seen).toEqual([edited]));
    expect(screen.getByLabelText("What are you planning?")).toHaveProperty("value", edited);
  });

  it("fills the apartment example", () => {
    installFetch(() => ({ modelability: null, plan: null }));
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Apartment move" }));
    expect(screen.getByLabelText("What are you planning?")).toHaveProperty("value", MOVE);
  });

  it("renders missing information", async () => {
    installFetch(() => ({
      modelability: {
        status: "NEEDS_INFORMATION",
        reason: "I can model this plan, but I need more grounded information first.",
        missing_information: ["the times of the commitments that must not be disturbed", "the calendar record for the event you want to move"],
        compiled_constraints: [],
        compiled_dependencies: [],
        available_actions: [],
        selected_skill: "Coordinate Schedule",
        provenance: "world compiler",
      },
      plan: null,
    }));
    render(<App />);
    fireEvent.change(screen.getByLabelText("What are you planning?"), { target: { value: "Move my dentist appointment to Thursday without interfering with class." } });
    fireEvent.click(screen.getByRole("button", { name: "Analyze my future" }));
    expect(await screen.findByText("Missing information")).toBeTruthy();
    expect(screen.getByText("the calendar record for the event you want to move")).toBeTruthy();
    expect(screen.queryByText("Future Graph")).toBeNull();
  });

  it("renders an honest unsupported message", async () => {
    installFetch(() => ({
      modelability: {
        status: "UNSUPPORTED",
        reason: "I don't have enough grounded information or executable structure to model this as a future.",
        missing_information: [],
        compiled_constraints: [],
        compiled_dependencies: [],
        available_actions: [],
        selected_skill: null,
        provenance: "world compiler",
      },
      plan: null,
    }));
    render(<App />);
    fireEvent.change(screen.getByLabelText("What are you planning?"), { target: { value: "Should I marry this person?" } });
    fireEvent.click(screen.getByRole("button", { name: "Analyze my future" }));
    expect(await screen.findByText(/I don't have enough grounded information/)).toBeTruthy();
    expect(screen.getByText(/I won't pretend to simulate it/)).toBeTruthy();
    expect(screen.queryByText("Future Graph")).toBeNull();
  });

  it("reaches the future graph for a supported example", async () => {
    installFetch((_text, demo) => {
      expect(demo).toBe("travel");
      return { modelability: { status: "SUPPORTED", reason: "An example context supplies the grounded records for this plan.", missing_information: [], compiled_constraints: ["Friday dinner"], compiled_dependencies: [], available_actions: [], selected_skill: "Reschedule Trip", provenance: "world compiler plus explicit example context" }, plan: supportedPlan };
    });
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "NYC trip" }));
    fireEvent.click(screen.getByRole("button", { name: "Analyze my future" }));
    expect(await screen.findByText("Future Graph")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Approve future" })).toBeTruthy();
    expect(screen.getByLabelText("Connected context").textContent).toContain("Search: OFF");
    expect(screen.getByLabelText("Shadow Watch").textContent).toContain("No approved future being monitored");
  });
});
