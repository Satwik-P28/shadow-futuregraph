# Security

Shadow keeps personal state on the machine that runs it. Credentials are read from the environment and are not written into the repository.

Report a vulnerability by opening a GitHub issue if the issue is not itself an exploit, or by contacting the repository owner privately if it is.

## What is in scope

- The semantic broker authorizing an action outside the approved future
- A provider retry creating a second mutation
- Retrieved text being executed as a tool or as code
- A budget bypass that sends a paid model call without a reservation
- Logs or traces that store raw prompts or secrets by default

## Defaults

- `NEBIUS_LIVE` must be `1` or the Token Factory client throws before any socket.
- `SHADOW_REAL_ACTIONS_ENABLED` defaults false. Google Calendar writes refuse without it.
- Duffel accepts only tokens that start with `duffel_test_`. Live mode responses are refused.
- Mail, when used, creates a sandbox draft. It does not send.
- Raw prompt logging requires `SHADOW_LOG_RAW_PROMPTS=true` and defaults off. The current client stores prompt hashes, token counts, and schema validity.
