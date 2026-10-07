"""FastAPI surface for the future-debugging loop."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from shadow.pipeline import PlanService, build_client
from shadow.policy.openshell import candidate_policy, compare_policy
from shadow.runtime.events import EventLog

ROOT = Path(__file__).resolve().parents[3]
DIST = ROOT / "frontend" / "dist"


class PlanIn(BaseModel):
    text: str
    scenario_id: str = "travel"
    seed: int = 7


class InjectIn(BaseModel):
    event_id: str


class AttemptIn(BaseModel):
    action_id: str


class RelaxIn(BaseModel):
    constraint_id: str


def create_app(service: PlanService | None = None) -> FastAPI:
    app = FastAPI(title="Shadow", version="1.0.0")
    app.state.service = service or PlanService(EventLog("sqlite://"), build_client())

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/plans")
    def create_plan(body: PlanIn) -> dict[str, str]:
        return app.state.service.create(body.text, body.scenario_id, body.seed)

    @app.post("/api/plans/{plan_id}/analyze")
    def analyze(plan_id: str) -> dict:
        _require(app, plan_id)
        return app.state.service.analyze(plan_id)

    @app.get("/api/plans/{plan_id}")
    def get_plan(plan_id: str) -> dict:
        _require(app, plan_id)
        return app.state.service.view(plan_id)

    @app.get("/api/plans/{plan_id}/graph")
    def graph(plan_id: str) -> dict:
        view = get_plan(plan_id)
        return view["graph"] or {"nodes": [], "edges": []}

    @app.get("/api/plans/{plan_id}/failures")
    def failures(plan_id: str) -> dict:
        return {"failures": get_plan(plan_id)["failures"]}

    @app.get("/api/plans/{plan_id}/repairs")
    def repairs(plan_id: str) -> dict:
        view = get_plan(plan_id)
        return {"repairs": view["repairs"], "recommended_repair_id": view["recommended_repair_id"]}

    @app.post("/api/plans/{plan_id}/repairs/{repair_id}/approve")
    def approve(plan_id: str, repair_id: str) -> dict:
        _require(app, plan_id)
        try:
            return app.state.service.approve(plan_id, repair_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/plans/{plan_id}/execute")
    def execute(plan_id: str) -> dict:
        _require(app, plan_id)
        try:
            return app.state.service.execute(plan_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/plans/{plan_id}/inject-event")
    def inject(plan_id: str, body: InjectIn) -> dict:
        _require(app, plan_id)
        try:
            return app.state.service.inject(plan_id, body.event_id)
        except StopIteration as exc:
            raise HTTPException(status_code=404, detail="unknown event") from exc

    @app.post("/api/plans/{plan_id}/actions/attempt")
    def attempt(plan_id: str, body: AttemptIn) -> dict:
        _require(app, plan_id)
        return app.state.service.attempt(plan_id, body.action_id)

    @app.post("/api/plans/{plan_id}/relax")
    def relax(plan_id: str, body: RelaxIn) -> dict:
        _require(app, plan_id)
        return app.state.service.relax(plan_id, body.constraint_id)

    @app.get("/api/plans/{plan_id}/events")
    def events(plan_id: str) -> dict:
        _require(app, plan_id)
        return {"events": [item.model_dump(mode="json") for item in app.state.service.events.list_for(plan_id)]}

    @app.get("/api/plans/{plan_id}/stream")
    def stream(plan_id: str):
        from fastapi.responses import StreamingResponse

        view = get_plan(plan_id)

        def gen():
            for stage in view["stages"]:
                yield f"data: {stage['name']}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.post("/api/demo/reset")
    def demo_reset() -> dict:
        created = app.state.service.create(
            "Move my NYC trip to Friday and make sure everything still works.",
            "travel",
            7,
        )
        return app.state.service.analyze(created["id"])

    @app.get("/api/benchmarks/latest")
    def benchmarks() -> dict:
        path = ROOT / "shadowbench" / "results" / "latest" / "summary.json"
        if not path.exists():
            return {"available": False, "summary": None}
        import json

        return {"available": True, "summary": json.loads(path.read_text())}

    @app.get("/api/policy/openshell")
    def openshell() -> dict:
        hosts = ["api.tokenfactory.nebius.com"]
        if os.environ.get("TAVILY_API_KEY"):
            hosts.append("api.tavily.com")
        return compare_policy(candidate_policy(hosts))

    if DIST.exists():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

        @app.get("/{path:path}")
        def spa(path: str) -> FileResponse:
            target = DIST / path
            if path and target.exists() and target.is_file():
                return FileResponse(target)
            return FileResponse(DIST / "index.html")

    return app


def _require(app: FastAPI, plan_id: str) -> None:
    if plan_id not in app.state.service.plans:
        raise HTTPException(status_code=404, detail="unknown plan")


app = create_app()
