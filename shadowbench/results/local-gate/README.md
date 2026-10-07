# local-gate

30 procedural worlds, seeds 1000 through 1029, families travel / scheduling / purchase cycling by seed.

Model column is a scripted stand-in. Token Factory spend on this run is $0. The generator and the metrics do not use an LLM judge.

Full Shadow is the only system that selects the repair by nearest-discovered failure radius. The other four commit to the cheapest nominally feasible plan.

These worlds share one monotone structure: a cheap margin fails the oracle probe set, and a larger margin covers it. The perfect split is evidence that the search implements that distinction. It is not a field estimate of personal-plan accuracy. See `docs/KNOWN_LIMITATIONS.md`.
