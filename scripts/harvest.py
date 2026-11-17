"""Harvest the labels production already paid for.

    python3 scripts/harvest.py [--model production]   -> data/labels/harvested.jsonl

Every sentence the reader was unsure about was read twice by the model, and the answer was kept when both readings
agreed (scout.verify.StanceCache). Those answers are labels: this script runs a week of traffic (config/traffic.toml)
through the agent and writes the agreed answers, which the next reader is trained on. Disagreements went to a person
and are not harvested.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scout import settings as settings_mod  # noqa: E402
from scout.graph import build  # noqa: E402
from scout.index import HybridIndex  # noqa: E402
from scout.llm import Usage  # noqa: E402
from scout.nlp import registry  # noqa: E402
from scout.verify import StanceCache  # noqa: E402
from scout.world.sim import SimLLM, World  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="production")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "labels" / "harvested.jsonl")
    ap.add_argument("--rfqs", type=int, default=0, help="limit the searches (a quick run; 0 = all)")
    args = ap.parse_args()
    settings = settings_mod.load()
    world = World.load(ROOT / "config" / "traffic.toml")
    index = HybridIndex(world.pages, settings["search"]["rrf_k"])
    reader, llm, cache = registry.load(args.model), SimLLM(world), StanceCache()
    for rfq in world.rfqs[: args.rfqs or None]:
        graph, _ = build(
            index, llm, settings, "agent_reader", usage=Usage(settings["cost"]), reader=reader, cache=cache
        )
        graph.invoke({"rfq": rfq})
    agreed = {k: v for k, v in cache.answers.items() if v is not None}
    # the cache keys are normalised sentences; keep the text as the reader will see it
    rows = [{"text": k, "label": v, "source": "model, two readings agreed"} for k, v in sorted(agreed.items())]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(
        f"{args.out}: {len(rows)} labelled sentences from {len(world.rfqs[: args.rfqs or None])} searches "
        f"({len(cache.answers) - len(agreed)} disagreements went to a person)"
    )


if __name__ == "__main__":
    main()
