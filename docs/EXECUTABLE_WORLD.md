# Executable world

The deterministic engine evaluates `Expr` values. It does not evaluate strings. `backend/shadow/world/executable.py` is the route that builds those expressions from records.

Supported sentence forms, and only these:

- `Name ends at 9:00 AM.`
- `Name arrives at 5:05 PM.`
- `Name starts at 10:00 AM and cannot move.`
- `Name to Other takes 20-40 minutes.`
- `Name can start at 2:00 PM instead.`
- `Name costs $400.`
- `Name costs $400 and cannot cancel.`
- `Available budget is at most $600.`

A chain is compiled only when a timed departure, a stated duration, and a timed start are all present. A stated range becomes an exogenous variable whose nominal value is the low end. The search may use the high end. No distribution is invented beyond that stated range.

If two times are present and the duration between them is not, the result is `NEEDS_INFORMATION`. A travel time is not filled in.

If two records give different values for the same field and neither record supersedes the other, the result is `CONTRADICTORY`. A later timestamp alone does not win.

A model may propose the same schema through `compile_executable`. The validator drops proposals that cite a missing source, use a number that is not in the cited text, use an operator outside `var/const/add/sub`, or name an action type outside `plan.keep`, `plan.drop_purchase`, and `plan.select_option`. A derived value is not marked `VERIFIED`.

This route does not read `example_world.py` or `fixtures/travel/world.json`. The NYC sandbox still uses that example table and is labeled as such. The public demo does not call Nemotron.

`shadowbench/primitive-holdout/` is a grammar holdout. The generator writes the forms above. It is not evidence about arbitrary prose.

Google Calendar credentials are not configured. No live calendar read or write is claimed.
