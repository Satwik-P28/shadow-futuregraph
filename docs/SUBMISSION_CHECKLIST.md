# Submission checklist

This checklist records what is implemented in the repository and what still requires a human or deployment action.

## Engineering

- [x] Public sandbox route is documented and uses `SANDBOX` mode by default.
- [x] Prepared NYC example remains deterministic and is labeled synthetic.
- [x] Future Graph, failure search, repair evaluation, approval contract, broker, execution, reconciliation, and Shadow Watch are covered by backend tests.
- [x] Nemotron client is budgeted and refuses live calls unless `NEBIUS_LIVE=1`.
- [x] Provenance and completeness checks prevent incomplete worlds from being approved.
- [x] Unrelated actions are rejected by the scoped broker.
- [x] Repository secret scan and CI configuration are present.
- [x] Current local source commit: `69497302f0a0b10d83808230097e3d11867bf037`.
- [ ] Push the validated local commits to `origin/main` and record the resulting remote SHA.
- [ ] Record the exact deployed source SHA after the next deployment.

## Validation

- [x] Backend Ruff check passes.
- [x] Backend tests pass (104 tests).
- [x] Backend coverage report passes (89%).
- [x] Frontend Vitest tests pass (9 tests).
- [x] Frontend TypeScript typecheck passes.
- [x] Frontend production build passes.
- [ ] Playwright run completed against the deployed public service.
- [ ] Live Nemotron workflow independently rerun and recorded.
- [ ] Deployment health and critical flows verified after the final push.

## Product and integrations

- [x] Public sandbox demo: https://shadow-futuregraph.onrender.com
- [x] Persistent local SQLite session path is implemented.
- [x] Public hosted durability is not claimed; Render's default disk is ephemeral.
- [x] Calendar, Duffel, and Tavily adapters are implemented but unconfigured.
- [x] Calendar and Tavily are not represented as live in the public demo.
- [x] Injected Shadow Watch changes are explicitly labeled sandbox events.
- [ ] Configure a dedicated Google Calendar test account and perform a real read/write/read-back run.
- [ ] Configure Tavily only if a relevant external-evidence use case is available.
- [ ] Test recovery after an actual process restart using the configured persistence path.

## Competition delivery

- [x] Final demo script: [FINAL_DEMO_SCRIPT.md](./FINAL_DEMO_SCRIPT.md)
- [x] Existing detailed demo script: [DEMO_SCRIPT.md](./DEMO_SCRIPT.md)
- [x] Architecture and limitations are documented.
- [ ] Record the demo video (target 2:40–2:55).
- [ ] Review every spoken claim against the execution mode shown on screen.
- [ ] Upload the video and submission materials to Devpost.
- [ ] Complete the Devpost feedback field.

## Do not claim yet

- A live Google Calendar mutation.
- Hosted durable personal memory.
- Continuous external monitoring.
- A completed demo recording or Devpost submission.
- Live Nemotron behavior on the public sandbox route.
