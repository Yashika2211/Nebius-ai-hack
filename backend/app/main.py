"""BidScout API. Long-running agent steps stream their trace over Server-Sent Events."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from . import db, router, seed, trace, watch
from .agents import discover as discover_agent
from .agents import draft as draft_agent
from .agents import eligibility as eligibility_agent
from .agents import profile as profile_agent
from .config import settings
from .models import resolve_models

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="BidScout API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins + ["*"] if "*" in settings.cors_origins else settings.cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    db.init()
    seed.ensure_seeded()


def stream(label: str, work: Callable[[trace.Trace], Any]) -> EventSourceResponse:
    """Run `work` in a thread and stream trace events, tokens, and the final result."""

    async def gen():
        queue: asyncio.Queue = asyncio.Queue()
        t = trace.start(label, queue)
        task = asyncio.create_task(asyncio.to_thread(work, t))
        while True:
            getter = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait({getter, task}, return_when=asyncio.FIRST_COMPLETED)
            if getter in done:
                yield {"event": "message", "data": json.dumps(getter.result())}
                continue
            getter.cancel()
            while not queue.empty():
                yield {"event": "message", "data": json.dumps(queue.get_nowait())}
            try:
                result = task.result()
                summary = t.finish()
                yield {"event": "message", "data": json.dumps({"type": "result", "result": result})}
                yield {"event": "message", "data": json.dumps({"type": "done", "summary": {k: v for k, v in summary.items() if k != "events"}})}
            except Exception as exc:
                logging.exception("%s failed", label)
                t.finish()
                yield {"event": "message", "data": json.dumps({"type": "error", "error": str(exc)})}
            break

    return EventSourceResponse(gen(), ping=10)


# --- status ----------------------------------------------------------------

@app.get("/api/status")
def status() -> dict:
    return {
        "llm": settings.has_llm,
        "search": settings.has_search,
        "demo_mode": settings.demo_mode,
        "models": resolve_models(),
        "routes": {task: {"tier": tier, "reason": reason} for task, (tier, reason) in router.TASK_ROUTES.items()},
        "prices": settings.prices,
    }


@app.get("/api/traces")
def traces(limit: int = 50) -> list[dict]:
    return db.list_traces(limit)


@app.get("/api/stats")
def stats() -> dict:
    """Aggregate routing savings across every recorded run."""
    events = [e for t in db.list_traces(500) for e in t.get("events", [])]
    return router.savings(events)


# --- profiles --------------------------------------------------------------

class ProfileIn(BaseModel):
    website: str = ""
    notes: str = ""
    name: str = ""


@app.post("/api/profiles")
def create_profile(body: ProfileIn):
    def work(t: trace.Trace) -> dict:
        trace.use(t)
        profile = profile_agent.build_profile(body.website.strip(), body.notes, body.name)
        db.save_profile(profile)
        return profile

    return stream("onboard", work)


@app.get("/api/profiles")
def get_profiles() -> list[dict]:
    return [{k: p.get(k) for k in ("id", "name", "website", "summary", "demo")} for p in db.list_profiles()]


@app.get("/api/profiles/{profile_id}")
def get_profile(profile_id: str) -> dict:
    profile = db.get_profile(profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    return profile


class ProfilePatch(BaseModel):
    summary: str | None = None
    keywords: list[str] | None = None
    locations: list[str] | None = None


@app.patch("/api/profiles/{profile_id}")
def patch_profile(profile_id: str, body: ProfilePatch) -> dict:
    profile = get_profile(profile_id)
    profile.update({k: v for k, v in body.model_dump().items() if v is not None})
    db.save_profile(profile, profile_id)
    return profile


# --- discovery -------------------------------------------------------------

class DiscoverIn(BaseModel):
    query: str = ""
    max_opps: int = 5


@app.post("/api/profiles/{profile_id}/discover")
def run_discover(profile_id: str, body: DiscoverIn):
    profile = get_profile(profile_id)

    def work(t: trace.Trace) -> list[dict]:
        trace.use(t)
        opps = discover_agent.discover(profile, max_opps=body.max_opps, extra_query=body.query)
        out = []
        for opp in opps:
            oid, is_new = db.upsert_opportunity(profile_id, opp)
            out.append(_card(opp, is_new))
        return out

    return stream("discover", work)


def _card(opp: dict, is_new: bool | None = None) -> dict:
    """Opportunity without its (large) source text, for list views."""
    card = {k: v for k, v in opp.items() if k != "source_text"}
    if is_new is not None:
        card["is_new"] = is_new
    return card


@app.get("/api/profiles/{profile_id}/opportunities")
def opportunities(profile_id: str) -> list[dict]:
    return [_card(o) for o in db.list_opportunities(profile_id)]


@app.get("/api/opportunities/{opp_id}")
def opportunity(opp_id: str) -> dict:
    opp = db.get_opportunity(opp_id)
    if not opp:
        raise HTTPException(404, "Opportunity not found")
    return {
        **_card(opp),
        "source_excerpt": (opp.get("source_text") or "")[:4000],
        "eligibility": db.latest_analysis(opp_id, "eligibility"),
        "draft": db.latest_analysis(opp_id, "draft"),
    }


def _profile_and_opp(profile_id: str, opp_id: str) -> tuple[dict, dict]:
    opp = db.get_opportunity(opp_id)
    if not opp:
        raise HTTPException(404, "Opportunity not found")
    return get_profile(profile_id), opp


@app.post("/api/profiles/{profile_id}/opportunities/{opp_id}/eligibility")
def run_eligibility(profile_id: str, opp_id: str):
    profile, opp = _profile_and_opp(profile_id, opp_id)

    def work(t: trace.Trace) -> dict:
        trace.use(t)
        result = eligibility_agent.check(profile, opp)
        db.save_analysis(opp_id, "eligibility", result)
        return result

    return stream("eligibility", work)


@app.post("/api/profiles/{profile_id}/opportunities/{opp_id}/draft")
def run_draft(profile_id: str, opp_id: str):
    profile, opp = _profile_and_opp(profile_id, opp_id)

    def work(t: trace.Trace) -> dict:
        trace.use(t)
        result = draft_agent.draft(profile, opp, on_token=lambda d: t.publish({"type": "token", "text": d}))
        db.save_analysis(opp_id, "draft", result)
        return result

    return stream("draft", work)


# --- watch -----------------------------------------------------------------

@app.post("/api/profiles/{profile_id}/watch/run")
def run_watch(profile_id: str):
    profile = get_profile(profile_id)

    def work(t: trace.Trace) -> list[dict]:
        trace.use(t)
        return watch.run_for_profile(profile)

    return stream("watch", work)


@app.get("/api/profiles/{profile_id}/watch")
def watch_runs(profile_id: str) -> list[dict]:
    return db.list_watch_runs(profile_id)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
