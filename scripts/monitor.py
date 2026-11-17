"""What on-call would have seen: the rolling checks over three windows of searches.

    python3 scripts/monitor.py   -> reports/monitor.json

1. a normal week: the dev world with the first reader (v1)
2. the week the wording drifted: the drift world, still on v1; the alerts that start the retraining workflow
3. after retraining: the drift world on v2, harvested and promoted through the gate

The checks are scout.ops.telemetry.Monitor, the same code the service runs behind GET /metrics.
"""

from __future__ import annotations

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
from scout.ops.telemetry import Monitor, record  # noqa: E402
from scout.verify import StanceCache  # noqa: E402
from scout.world.sim import SimLLM, World  # noqa: E402

WINDOWS = [
    ("normal week", "world.toml", "v1"),
    ("wording drifted", "drift.toml", "v1"),
    ("after retraining", "drift.toml", "v2"),
]


def window(cfg: str, model: str, settings: dict) -> dict:
    world = World.load(ROOT / "config" / cfg)
    index = HybridIndex(world.pages, settings["search"]["rrf_k"])
    reader, llm, cache = registry.load(model), SimLLM(world), StanceCache()
    mon = Monitor(settings, reader.card["baseline"])  # what the reader in use was released on
    for rfq in world.rfqs[: settings["monitor"]["window"]]:
        usage = Usage(settings["cost"])
        graph, _ = build(index, llm, settings, "agent_reader", usage=usage, reader=reader, cache=cache)
        out = graph.invoke({"rfq": rfq})
        mon.add(record(rfq.id, out, usage, "agent_reader", model, settings["search"]["shortlist_size"]))
    return mon.summary()


def main() -> None:
    settings = settings_mod.load()
    report = []
    for name, cfg, model in WINDOWS:
        s = window(cfg, model, settings)
        report.append({"window": name, "world": cfg.removesuffix(".toml"), "reader": model, **s})
        print(
            f"{name:18} {model}  novel {s['novel_share']:.2%}  PSI {s['confidence_psi']}  "
            f"fallback {s['fallback_calls_per_search']}  ${s['usd_per_search']}  alerts {s['alerts']}"
        )
    (ROOT / "reports" / "monitor.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
