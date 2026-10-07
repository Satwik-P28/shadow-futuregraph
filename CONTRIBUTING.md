# Contributing

Run `make setup`, then `make test` and `make benchmark-local`.

Do not commit `.env`, API keys, or real personal data. Fixtures stay synthetic.

The failure search, constraint evaluator, broker, and budget ledger are the parts that must stay deterministic. Model output is a proposal. It does not rank repairs or authorize actions.

Pull requests should include a test when they change those paths. CI must not call a paid API.
