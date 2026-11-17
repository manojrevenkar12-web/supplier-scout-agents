"""Run every RFQ of a world through each design and compare the shortlists with the truth.

    python3 scripts/evaluate.py                    dev world (config/world.toml)
    python3 scripts/evaluate.py --world drift      six months later: new wording (config/drift.toml)
    python3 scripts/evaluate.py --world heldout    held-out world, once (writes config/heldout.lock)

A search fails if its shortlist holds a supplier that cannot really supply, holds one company twice, or is
shorter than it had to be. This script and src/scout/world/ are the only code that reads the truth.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scout import settings as settings_mod  # noqa: E402
from scout.graph import DESIGNS, build  # noqa: E402
from scout.index import HybridIndex  # noqa: E402
from scout.llm import Usage  # noqa: E402
from scout.nlp import registry  # noqa: E402
from scout.verify import StanceCache  # noqa: E402
from scout.world.sim import SimLLM, World  # noqa: E402


def q(xs: list[float], p: float) -> float:
    return round(sorted(xs)[min(len(xs) - 1, int(p * len(xs)))], 4) if xs else 0.0


def measure(world: World, index: HybridIndex, design: str, settings: dict, reader=None) -> dict:
    llm = SimLLM(world)
    cache = StanceCache()
    k = settings["search"]["shortlist_size"]
    reasons: Counter = Counter()
    fails, precisions, recalls, costs, calls, ms, examples = 0, [], [], [], [], [], []
    injected = 0
    reviews = []
    reading = {"sentences": 0, "unsure": 0, "novel": 0, "confidence_hist": [0] * 10}
    for rfq in world.rfqs:
        truth = set(world.truth[rfq.id]["qualified"])
        graph, usage = build(index, llm, settings, design, usage=Usage(settings["cost"]), reader=reader, cache=cache)
        t0 = time.perf_counter()
        try:
            out = graph.invoke({"rfq": rfq})
            ids = [world.page_company[v.supplier_id] for v in out["shortlist"]]
        except Exception as e:  # noqa: BLE001 - a crash is a failed search
            ids, out = [], {"trace": [{"node": "error", "error": repr(e)}]}
            reasons["crashed"] += 1
        ms.append((time.perf_counter() - t0) * 1000)
        wrong = [c for c in ids if c not in truth]
        dup = len(ids) != len(set(ids))
        need = min(k, len(truth))
        short = len(set(ids) - set(wrong)) < need
        injected += any(world.companies[c].injection for c in wrong)
        for c in wrong:
            comp = world.companies[c]
            req = world.truth[rfq.id]["req"]
            why = (
                "trader or distributor"
                if comp.distributor
                else "certificate missing or expired"
                if any(x not in comp.certs or x in comp.expired for x in req.certs)
                else "process no longer offered"
                if req.process in comp.discontinued
                else "capacity"
                if req.min_capacity and (comp.capacity or 0) < req.min_capacity
                else "other"
            )
            reasons[f"unqualified supplier: {why}"] += 1
        if dup:
            reasons["same company twice"] += 1
        if short:
            reasons["shortlist shorter than it had to be"] += 1
        failed = bool(wrong or dup or short)
        fails += failed
        if failed and len(examples) < 3:
            examples.append({"rfq": rfq.text, "wrong": len(wrong), "duplicate": dup, "short": short})
        precisions.append(1 - len(wrong) / len(ids) if ids else (1.0 if not truth else 0.0))
        recalls.append(len(set(ids) - set(wrong)) / need if need else 1.0)
        costs.append(usage.usd)
        reviews.append(len(out.get("review", [])) if isinstance(out, dict) else 0)
        calls.append(usage.calls)
        for key in ("sentences", "unsure", "novel"):
            reading[key] += usage.reading[key]
        reading["confidence_hist"] = [
            a + b for a, b in zip(reading["confidence_hist"], usage.reading["confidence_hist"], strict=True)
        ]
    n = len(world.rfqs)
    return {
        "design": design,
        "searches": n,
        "failed": fails,
        "failure_rate": round(fails / n, 4),
        "precision": round(statistics.mean(precisions), 4),
        "recall_at_k": round(statistics.mean(recalls), 4),
        "usd_per_search": round(statistics.mean(costs), 4),
        "model_calls_per_search": round(statistics.mean(calls), 1),
        "p95_ms": round(q(ms, 0.95)),
        "review_per_search": round(statistics.mean(reviews), 2),
        "injected_suppliers_shortlisted": injected,
        "sentences_asked": cache.asked,
        "reading": reading,
        "failure_reasons": dict(reasons.most_common()),
        "examples": examples,
    }


WORLDS = {"dev": "world.toml", "drift": "drift.toml", "heldout": "heldout.toml"}


def run(world_name: str, designs: list[str], model: str, settings: dict, rfqs: int = 0) -> dict:
    world = World.load(ROOT / "config" / WORLDS[world_name])
    if rfqs:
        world.rfqs = world.rfqs[:rfqs]  # a quick run (the Argo smoke test in CI)
    index = HybridIndex(world.pages, settings["search"]["rrf_k"])
    reader = registry.load(model)
    report = {
        "world": world_name,
        "pages": len(world.pages),
        "companies": len(world.companies),
        "rfqs": len(world.rfqs),
        "target_failure_rate": settings["quality"]["target_failure_rate"],
        "reader": model if model != "production" else registry.read()["production"],
    }
    for d in designs:
        report[d] = measure(world, index, d, settings, reader if DESIGNS[d].get("reader") else None)
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", choices=list(WORLDS), default="dev")
    ap.add_argument("--model", default="production", help="registry version of the reader")
    ap.add_argument("--designs", default=",".join(DESIGNS))
    ap.add_argument("--out", type=Path, help="where to write the report (default reports/<world>.json)")
    args = ap.parse_args()
    lock = ROOT / "config" / "heldout.lock"
    if args.world == "heldout" and lock.exists():
        sys.exit(f"the held-out world already ran ({lock.read_text().strip()}); see AGENTS.md")
    settings = settings_mod.load()
    designs = args.designs.split(",")
    report = run(args.world, designs, args.model, settings)
    timing = {d: report[d].pop("p95_ms") for d in designs}  # wall time varies by machine: printed, not committed
    out = args.out or ROOT / "reports" / f"{args.world}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.world == "heldout":
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
        lock.write_text(f"ran at commit {commit} with reader {report['reader']}\n")
    for d in designs:
        r = report[d]
        print(
            f"{d:18} fail {r['failure_rate']:.2%}  prec {r['precision']:.3f}  recall {r['recall_at_k']:.3f}  "
            f"${r['usd_per_search']:.4f}  calls {r['model_calls_per_search']}  review {r['review_per_search']}  "
            f"asked {r['sentences_asked']}  p95 {timing[d]} ms  {r['failure_reasons']}"
        )


if __name__ == "__main__":
    main()
