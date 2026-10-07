# Devpost submission

## What Shadow is

Shadow is a private personal AI that turns a plan into a bounded graph of material futures, finds minimal ways that future can fail, repairs it, and executes only the approved future under a semantic contract.

Tagline: Find bugs in your future before you commit to it.

## Problem

Assistants treat a plan as a list of tool calls. They book the option that looks fine on the nominal schedule. They do not show the smallest perturbation that breaks a hard constraint, and they do not ask you to approve a future instead of a tool trace.

## Why existing agents are insufficient

A planner that checks the happy path will take the cheaper Friday flight that arrives at 17:05 and still miss dinner once a modest delay stacks with traffic. A critic that only re-reads the nominal world has the same blind spot. Debating agents do not change that if the decision is still a language-model vote.

## What is novel

The user approves a repaired future. Authority is the contract for that future, not a general calendar or travel scope. Failure search returns a minimal perturbation set and a nearest discovered radius. The model may propose repairs. It cannot declare one successful.

This is not a claim that no other system searches counterfactual plans. It is a claim about this loop: material graph, minimal failure sets, counterfactual evaluation, future-scoped execution, and an event ledger that can revoke authority when an assumption breaks.

## How it works

See `docs/ARCHITECTURE.md`. The hero fixture is synthetic. The afternoon flight is selected because it is the lowest-cost bundle that passes every hard constraint at baseline. The earlier flight wins later because its failure radius is larger. Neither choice is a hardcoded branch in the search.

## NVIDIA / Nebius use

The semantic calls go to Nebius Token Factory, OpenAI-compatible, model `nvidia/Nemotron-3_5-Lightning`, thinking disabled. Prices live in one file, checked 2026-10-07. A budget ledger reserves the worst case before a request and reconciles actual usage after. Super and Ultra are off unless explicit environment flags are set. Ultra is not used.

The local benchmark does not spend tokens. It shows that the search, not a larger model, is what detects the planted failure mode.

## Tavily use

Tavily is the live external-evidence adapter: disruptions and other facts that can invalidate an assumption, stored with query, source, time, and claim. Without a key, a fixture search provider is used and labeled sandbox.

## Privacy

World state is local SQLite and fixture files. The model context is a compact typed extract. Raw source bodies are stripped. Prompts are not logged by default.

## Benchmark evidence

`shadowbench/results/local-gate`, 30 worlds, seeds 1000–1029.

| System | Task completion | Undetected failures | Repair success |
| --- | --- | --- | --- |
| direct | 0/30 | 30/30 | 0/30 |
| planner | 0/30 | 30/30 | 0/30 |
| planner_critic | 0/30 | 30/30 | 0/30 |
| shadow_no_search | 0/30 | 30/30 | 0/30 |
| shadow | 30/30 | 0/30 | 30/30 |

Cost of this run: $0. Model calls in the table are scripted counts, not billed tokens. The generator is monotone; do not read the interval as a general accuracy rate. Details are in `docs/KNOWN_LIMITATIONS.md`.

## Known limitations

See `docs/KNOWN_LIMITATIONS.md`.

## Setup and tests

`make setup`, `make dev`, `make test`, `make benchmark-local`. The sandbox demo needs no API keys.
