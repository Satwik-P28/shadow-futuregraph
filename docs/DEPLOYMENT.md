# Deployment

The production image builds the frontend, then serves it from FastAPI.

```bash
docker build -t shadow-futuregraph .
docker run --rm -p 8000:8000 -e PORT=8000 shadow-futuregraph
```

The process binds `0.0.0.0:$PORT`. `GET /healthz` returns `{"status":"ok"}`.

The container filesystem is ephemeral. SQLite files under `data/` disappear on restart. For anything that must survive, mount a volume at `/app/data` or replace the local ledger with an external database. Do not bake API keys into the image. Pass `NEBIUS_API_KEY` and the other variables from `.env.example` at runtime.

`NEBIUS_LIVE` defaults off inside the image unless you set it. The sandbox demo works with no keys.

`render.yaml` builds the Dockerfile and leaves `NEBIUS_LIVE` unset so the public demo stays in the sandbox. `render` is installed, and `~/.render/cli.yaml` exists, but the CLI token was expired (`Error: your token is expired; run render login`). Render MCP was unauthenticated. After `render login`:

```bash
render login
# create a web service from this repo's Dockerfile, or:
docker build -t shadow-futuregraph .
```

Deploy the image on any container host that can set environment variables and reach the health check. Leave `NEBIUS_LIVE` unset so judges need no API key. The badge stays SANDBOX. Nebius Serverless Jobs, if you have credentials, can run `python -m shadow.benchmark.run` as a batch evaluation. That path is for simulation, not for hosting the website. The local gate does not require it.

NemoClaw is not wired in. OpenShell is the system and network boundary. Adding a second agent sandbox would duplicate that role without changing the semantic broker, which is the part that knows which calendar event was approved.
