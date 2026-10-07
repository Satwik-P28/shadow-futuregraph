"""FastAPI surface for the future-debugging loop."""

from __future__ import annotations

import os
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from shadow.paths import repo_root
from shadow.pipeline import PlanService, build_client
from shadow.policy.openshell import candidate_policy, compare_policy
from shadow.runtime.events import EventLog
from shadow.runtime.sessions import SessionStore

ROOT = repo_root()
DIST = ROOT / "frontend" / "dist"


class PlanIn(BaseModel):
    text: str = Field(max_length=8000)
    scenario_id: str = "travel"
    seed: int = 7


class FreeformIn(BaseModel):
    text: str = Field(max_length=8000)
    demo_context_id: Literal["travel", "apartment"] | None = None
    seed: int = 7


class InjectIn(BaseModel):
    event_id: str


class AttemptIn(BaseModel):
    action_id: str


class RelaxIn(BaseModel):
    constraint_id: str


class LabIn(BaseModel):
    overrides: dict[str, float] = {}
    repair_id: str | None = None


def create_app(service: PlanService | None = None) -> FastAPI:
    app = FastAPI(title="Shadow", version="1.0.0")
    shared = service

    def factory() -> PlanService:
        if shared is not None:
            return shared
        return PlanService(EventLog("sqlite://"), build_client())

    app.state.sessions = SessionStore(factory)

    @app.middleware("http")
    async def bind_session(request: Request, call_next):
        session_id, bound, created = request.app.state.sessions.get_or_create(request.cookies.get("shadow_session"))
        bound.session_id = session_id
        if created:
            bound.watcher.restore()
        request.state.service = bound
        response = await call_next(request)
        if created or request.cookies.get("shadow_session") != session_id:
            response.set_cookie("shadow_session", session_id, httponly=True, samesite="lax", path="/", max_age=86400)
        return response

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/personal-ai/status")
    def personal_ai(request: Request) -> dict:
        return request.state.service.personal_status()

    @app.post("/api/plans/freeform")
    def freeform(body: FreeformIn, request: Request) -> dict:
        try:
            return request.state.service.analyze_freeform(body.text, body.demo_context_id, body.seed)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/plans")
    def create_plan(body: PlanIn, request: Request) -> dict[str, str]:
        return request.state.service.create(body.text, body.scenario_id, body.seed)

    @app.post("/api/plans/{plan_id}/analyze")
    def analyze(plan_id: str, request: Request) -> dict:
        _require(request, plan_id)
        return request.state.service.analyze(plan_id)

    @app.get("/api/plans/{plan_id}")
    def get_plan(plan_id: str, request: Request) -> dict:
        _require(request, plan_id)
        return request.state.service.view(plan_id)

    @app.get("/api/plans/{plan_id}/graph")
    def graph(plan_id: str, request: Request) -> dict:
        view = get_plan(plan_id, request)
        return view["graph"] or {"nodes": [], "edges": []}

    @app.get("/api/plans/{plan_id}/failures")
    def failures(plan_id: str, request: Request) -> dict:
        return {"failures": get_plan(plan_id, request)["failures"]}

    @app.get("/api/plans/{plan_id}/repairs")
    def repairs(plan_id: str, request: Request) -> dict:
        view = get_plan(plan_id, request)
        return {"repairs": view["repairs"], "recommended_repair_id": view["recommended_repair_id"]}

    @app.post("/api/plans/{plan_id}/repairs/{repair_id}/approve")
    def approve(plan_id: str, repair_id: str, request: Request) -> dict:
        _require(request, plan_id)
        try:
            return request.state.service.approve(plan_id, repair_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/plans/{plan_id}/execute")
    def execute(plan_id: str, request: Request) -> dict:
        _require(request, plan_id)
        try:
            return request.state.service.execute(plan_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/plans/{plan_id}/inject-event")
    def inject(plan_id: str, body: InjectIn, request: Request) -> dict:
        _require(request, plan_id)
        try:
            return request.state.service.inject(plan_id, body.event_id)
        except StopIteration as exc:
            raise HTTPException(status_code=404, detail="unknown event") from exc

    @app.post("/api/plans/{plan_id}/actions/attempt")
    def attempt(plan_id: str, body: AttemptIn, request: Request) -> dict:
        _require(request, plan_id)
        return request.state.service.attempt(plan_id, body.action_id)

    @app.post("/api/plans/{plan_id}/relax")
    def relax(plan_id: str, body: RelaxIn, request: Request) -> dict:
        _require(request, plan_id)
        return request.state.service.relax(plan_id, body.constraint_id)

    @app.get("/api/plans/{plan_id}/events")
    def events(plan_id: str, request: Request) -> dict:
        _require(request, plan_id)
        return {"events": [item.model_dump(mode="json") for item in request.state.service.events.list_for(plan_id)]}

    @app.get("/api/plans/{plan_id}/stream")
    def stream(plan_id: str, request: Request):
        from fastapi.responses import StreamingResponse

        view = get_plan(plan_id, request)

        def gen():
            for stage in view["stages"]:
                yield f"data: {stage['name']}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/api/futures")
    def futures(request: Request) -> dict:
        return request.state.service.list_futures()

    @app.get("/api/plans/{plan_id}/lab")
    def lab_controls(plan_id: str, request: Request) -> dict:
        _require(request, plan_id)
        try:
            return request.state.service.lab_controls(plan_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/plans/{plan_id}/lab")
    def lab_simulate(plan_id: str, body: LabIn, request: Request) -> dict:
        _require(request, plan_id)
        try:
            return request.state.service.simulate_lab(plan_id, body.overrides, body.repair_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/plans/{plan_id}/lab/nearest")
    def lab_nearest(plan_id: str, body: LabIn, request: Request) -> dict:
        _require(request, plan_id)
        try:
            return request.state.service.nearest_lab(plan_id, body.repair_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/plans/{plan_id}/receipt")
    def receipt(plan_id: str, request: Request) -> dict:
        _require(request, plan_id)
        return request.state.service.receipt(plan_id)

    @app.post("/api/demo/reset")
    def demo_reset(request: Request) -> dict:
        return request.state.service.reset_demo()

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


def _require(request: Request, plan_id: str) -> None:
    if plan_id not in request.state.service.plans:
        raise HTTPException(status_code=404, detail="unknown plan")


app = create_app()
