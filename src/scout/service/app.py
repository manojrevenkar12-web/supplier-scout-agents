"""FastAPI: buyers submit an RFQ, a worker runs the agent from Pub/Sub, results and traces come back by id.
A search whose shortlist needs a person pauses (LangGraph interrupt) until the buyer answers."""

from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException
from langgraph.types import Command
from pydantic import BaseModel

from scout.graph import build
from scout.index import HybridIndex
from scout.llm import LLM, Usage
from scout.models import Rfq
from scout.ops.telemetry import Monitor, record
from scout.service.bus import Bus
from scout.verify import StanceCache

TOPIC = SUBSCRIPTION = "supplier-searches"


class SearchIn(BaseModel):
    text: str


class ReviewIn(BaseModel):
    approved: list[str]


class Searches:
    """Runs searches and keeps their state; in production the state is in Firestore (see infra/)."""

    def __init__(self, index: HybridIndex, llm: LLM, settings: dict, bus: Bus, reader=None, design: str | None = None):
        self.index, self.llm, self.settings, self.bus = index, llm, settings, bus
        self.reader = reader
        self.design = design or settings["service"]["design"]
        self.model = (reader.card.get("version") if reader is not None else None) or ("reader" if reader else None)
        self.cache = StanceCache()  # in production: a Firestore collection shared by the workers
        self.monitor = Monitor(settings, reader.card.get("baseline") if reader is not None else None)
        self.results: dict[str, dict] = {}

    def _build(self, usage: Usage):
        return build(
            self.index,
            self.llm,
            self.settings,
            self.design,
            review=True,
            usage=usage,
            reader=self.reader,
            cache=self.cache,
        )[0]

    def submit(self, text: str) -> str:
        sid = f"search-{uuid.uuid4().hex[:12]}"
        self.results[sid] = {"status": "queued"}
        self.bus.publish(TOPIC, {"id": sid, "text": text})
        return sid

    def work(self, max_messages: int = 10) -> int:
        done = 0
        for ack_id, msg in self.bus.pull(SUBSCRIPTION, max_messages):
            if self.results.get(msg["id"], {}).get("status") not in ("queued", None):
                self.bus.ack(SUBSCRIPTION, [ack_id])  # a redelivered message for a search already run
                continue
            usage = Usage(self.settings["cost"])
            graph = self._build(usage)
            cfg = {"configurable": {"thread_id": msg["id"]}}
            out = graph.invoke({"rfq": Rfq(id=msg["id"], text=msg["text"])}, cfg)
            size = self.settings["search"]["shortlist_size"]
            self.monitor.add(record(msg["id"], out, usage, self.design, self.model, size))
            self.results[msg["id"]] = self._view(out, usage, graph, cfg)
            self.bus.ack(SUBSCRIPTION, [ack_id])
            done += 1
        return done

    def answer(self, sid: str, approved: list[str]) -> dict:
        r = self.results.get(sid)
        if not r or r["status"] != "needs_review":
            raise KeyError(sid)
        graph, cfg = r.pop("_graph"), {"configurable": {"thread_id": sid}}
        out = graph.invoke(Command(resume={"approved": approved}), cfg)
        self.results[sid] = self._view(out, r["_usage"], graph, cfg)
        return self.results[sid]

    @staticmethod
    def _view(out: dict, usage: Usage, graph, cfg) -> dict:
        if "__interrupt__" in out:
            return {"status": "needs_review", "ask": out["__interrupt__"][0].value, "_graph": graph, "_usage": usage}
        return {
            "status": "done",
            "shortlist": [v.model_dump() for v in out["shortlist"]],
            "review": [v.model_dump() for v in out.get("review", [])],
            "usd": round(usage.usd, 4),
            "model_calls": usage.calls,
            "trace": out["trace"],
        }


def create_app(searches: Searches) -> FastAPI:
    app = FastAPI(title="Supplier search", version="1.0.0")

    @app.post("/searches", status_code=202)
    def submit(body: SearchIn):
        return {"id": searches.submit(body.text)}

    @app.get("/searches/{sid}")
    def get(sid: str):
        r = searches.results.get(sid)
        if r is None:
            raise HTTPException(404, "no such search")
        return {k: v for k, v in r.items() if not k.startswith("_")}

    @app.get("/metrics")
    def metrics():
        """The rolling checks over the last searches: novel wording, confidence drift, fallbacks, cost."""
        return searches.monitor.summary()

    @app.post("/searches/{sid}/review")
    def review(sid: str, body: ReviewIn):
        try:
            r = searches.answer(sid, body.approved)
        except KeyError as e:
            raise HTTPException(409, "this search is not waiting for a review") from e
        return {k: v for k, v in r.items() if not k.startswith("_")}

    return app
