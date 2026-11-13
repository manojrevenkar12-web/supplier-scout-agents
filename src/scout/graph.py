"""The search agent as a LangGraph graph: plan -> retrieve -> qualify -> reflect (loop) -> shortlist -> review.

Designs switch parts on and off so they can be compared on the same RFQs:
  single_shot       BM25 top-k, the model qualifies and ranks, no checks, no loop
  agent_unverified  the full graph, but the model's claims are taken as they are
  agent             the full graph with code verification, instruction stripping and code ranking
"""

from __future__ import annotations

import time
from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from scout.entities import dedupe
from scout.index import HybridIndex
from scout.llm import LLM, Usage
from scout.models import Requirements, Rfq, SupplierPage, Verdict
from scout.taxonomy import CERTS, MATERIALS, PROCESSES
from scout.verify import strip_instructions, trust, verify

DESIGNS = {
    "single_shot": dict(
        verify=False, hybrid=False, reflect=False, dedupe=False, strip=False, prefilter=False, rank="model"
    ),
    "agent_unverified": dict(
        verify=False, hybrid=True, reflect=True, dedupe=True, strip=False, prefilter=True, rank="model"
    ),
    "agent": dict(verify=True, hybrid=True, reflect=True, dedupe=True, strip=True, prefilter=True, rank="fit"),
}


class State(TypedDict, total=False):
    rfq: Rfq
    req: Requirements
    seen: list[str]
    verdicts: dict[str, Verdict]
    pages: dict[str, SupplierPage]
    reflections: int
    shortlist: list[Verdict]
    review: list[Verdict]
    trace: list[dict]
    stopped: str


def lexicon_requirements(text: str) -> dict[str, list[str]]:
    """What code can read from an RFQ by itself: used to check the model's plan, never to replace it."""
    t = text.lower()
    return {
        "process": [k for k, ws in PROCESSES.items() if any(w in t for w in ws)],
        "material": [k for k, ws in MATERIALS.items() if any(w in t for w in ws)],
        "certs": [k for k, ws in CERTS.items() if any(w in t for w in ws)],
    }


def build(
    index: HybridIndex,
    llm: LLM,
    settings: dict,
    design: str = "agent",
    review: bool = False,
    usage: Usage | None = None,
):
    flags = DESIGNS[design]
    s = settings["search"]
    usage = usage or Usage(settings["cost"])

    def log(state: State, node: str, **kw: Any) -> list[dict]:
        return [*state.get("trace", []), {"node": node, "t": round(time.perf_counter(), 4), **kw}]

    def plan(state: State) -> dict:
        rfq = state["rfq"]
        req = llm.plan(rfq)
        usage.add(len(rfq.text) + 600, 300)
        repaired = []
        if flags["verify"]:
            lex = lexicon_requirements(rfq.text)
            for cert in lex["certs"]:
                if cert not in req.certs:
                    req.certs.append(cert)
                    repaired.append(cert)
        return {
            "req": req,
            "seen": [],
            "verdicts": {},
            "pages": {},
            "reflections": 0,
            "trace": log(state, "plan", req=req.model_dump(), repaired=repaired),
        }

    def retrieve(state: State) -> dict:
        req, n = state["req"], state["reflections"]
        widen = n > 0
        query = index.query_for(req, widen=widen)
        k = s["first_pass_candidates"] * s["widen_factor"] ** n
        hits = index.search(query, k, req.region) if flags["hybrid"] else index.search_bm25(query, k)
        new = [p for p in hits if p.supplier_id not in state["seen"]]
        if flags["prefilter"]:  # code drops pages that cannot qualify before paying for a model call
            text_has = lambda p: any(w in p.text.lower() for w in PROCESSES[req.process])  # noqa: E731
            new = [p for p in new if text_has(p) and (not req.region or p.country in req.region)]
        pages = {**state["pages"], **{p.supplier_id: p for p in new}}
        return {
            "seen": [*state["seen"], *[p.supplier_id for p in hits]],
            "pages": pages,
            "trace": log(state, "retrieve", query=query, hits=len(hits), new=len(new)),
        }

    def qualify(state: State) -> dict:
        req, verdicts = state["req"], dict(state["verdicts"])
        stopped = state.get("stopped", "")
        for sid, page in state["pages"].items():
            if sid in verdicts:
                continue  # cached: a reflection never pays twice for a page
            if usage.usd >= settings["cost"]["max_usd_per_search"]:
                stopped = "budget"
                break
            text = strip_instructions(page.text) if flags["strip"] else page.text
            claim = llm.qualify(text, page, req)
            usage.add(len(text) + 900, 400)
            verdicts[sid] = verify(page, claim, req, settings) if flags["verify"] else trust(page, claim, req)
            if not flags["verify"]:
                verdicts[sid].fit = claim.score
        n_ok = sum(v.qualified for v in verdicts.values())
        return {
            "verdicts": verdicts,
            "stopped": stopped,
            "trace": log(state, "qualify", judged=len(verdicts), qualified=n_ok, usd=round(usage.usd, 4)),
        }

    def enough(state: State) -> str:
        qualified = [v for v in state["verdicts"].values() if v.qualified]
        ok = len(dedupe(qualified, lambda v: v.name)[0]) if flags["dedupe"] else len(qualified)
        if (
            flags["reflect"]
            and ok < s["shortlist_size"]
            and state["reflections"] < s["max_reflections"]
            and state.get("stopped") != "budget"
        ):
            return "reflect"
        return "shortlist"

    def reflect(state: State) -> dict:
        return {
            "reflections": state["reflections"] + 1,
            "trace": log(state, "reflect", reason="fewer qualified suppliers than the shortlist needs"),
        }

    def shortlist(state: State) -> dict:
        ok = sorted((v for v in state["verdicts"].values() if v.qualified), key=lambda v: (-v.fit, v.supplier_id))
        merged = 0
        if flags["dedupe"]:
            ok, merged = dedupe(ok, lambda v: v.name)
        review_list = [v for v in state["verdicts"].values() if v.needs_review]
        return {
            "shortlist": ok[: s["shortlist_size"]],
            "review": review_list,
            "trace": log(state, "shortlist", qualified=len(ok), merged_duplicates=merged, review=len(review_list)),
        }

    def human_review(state: State) -> dict:
        if not review or not state["review"] or len(state["shortlist"]) >= s["shortlist_size"]:
            return {"trace": log(state, "human_review", asked=0)}
        answer = interrupt({"rfq": state["rfq"].id, "ask": [v.model_dump() for v in state["review"]]})
        approved = [v for v in state["review"] if v.supplier_id in set(answer.get("approved", []))]
        room = s["shortlist_size"] - len(state["shortlist"])
        return {
            "shortlist": [*state["shortlist"], *approved[:room]],
            "trace": log(state, "human_review", approved=len(approved)),
        }

    g = StateGraph(State)
    for name, fn in [
        ("plan", plan),
        ("retrieve", retrieve),
        ("qualify", qualify),
        ("reflect", reflect),
        ("shortlist", shortlist),
        ("human_review", human_review),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "plan")
    g.add_edge("plan", "retrieve")
    g.add_edge("retrieve", "qualify")
    g.add_conditional_edges("qualify", enough, {"reflect": "reflect", "shortlist": "shortlist"})
    g.add_edge("reflect", "retrieve")
    g.add_edge("shortlist", "human_review")
    g.add_edge("human_review", END)
    return g.compile(checkpointer=InMemorySaver() if review else None), usage
