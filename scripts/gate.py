"""The release gate for a stance reader.

    python3 scripts/gate.py --candidate v2 [--promote]

Checks the candidate's model card, runs the agent with it on the dev world and on the drift world, runs the reader in
production on the same worlds (or, for the first reader, the keyword-checked agent), and writes
reports/gate-<candidate>.json. The candidate is registered with the verdict; with --promote it goes to production
only if every check passed. Thresholds are in config/release.toml.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate import run  # noqa: E402

from scout import settings as settings_mod  # noqa: E402
from scout.nlp import registry  # noqa: E402

KEEP = (
    "failure_rate",
    "precision",
    "recall_at_k",
    "usd_per_search",
    "model_calls_per_search",
    "review_per_search",
    "sentences_asked",
    "reading",
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--promote", action="store_true")
    ap.add_argument("--rfqs", type=int, default=0, help="limit RFQs per world (a quick run; 0 = all)")
    ap.add_argument("--out", type=Path, help="report path (default reports/gate-<candidate>.json)")
    args = ap.parse_args()
    rel = tomllib.loads((ROOT / "config" / "release.toml").read_text())
    settings = settings_mod.load()
    reg = registry.read()
    cand_dir = ROOT / "models" / args.candidate
    card = json.loads((cand_dir / "card.json").read_text())
    if args.candidate not in reg["versions"]:
        registry.register(args.candidate, cand_dir)
    prod = reg.get("production")

    def agent(world: str, model: str) -> dict:
        r = run(world, ["agent_reader"], model, settings, args.rfqs)["agent_reader"]
        return {k: r[k] for k in KEEP}

    result = {"candidate": args.candidate, "production": prod, "worlds": {}}
    for world in ("dev", "drift"):
        cand = agent(world, args.candidate)
        if prod and prod != args.candidate:
            base = agent(world, prod)
        else:  # the first reader is compared with the keyword-checked agent it replaces
            r = run(world, ["agent"], args.candidate, settings, args.rfqs)["agent"]
            base = {k: r[k] for k in KEEP if k in r}
        result["worlds"][world] = {"candidate": cand, "baseline": base}

    c, a = rel["card"], rel["agent"]
    dev, drift = result["worlds"]["dev"], result["worlds"]["drift"]
    checks = [
        (
            "validation accuracy",
            card["validation"]["accuracy"],
            f">= {c['min_validation_accuracy']}",
            card["validation"]["accuracy"] >= c["min_validation_accuracy"],
        ),
        (
            "int8 runtime agrees with PyTorch",
            card["parity"]["same_label"],
            f">= {c['min_parity_same_label']}",
            card["parity"]["same_label"] >= c["min_parity_same_label"],
        ),
        (
            "largest probability gap, int8 vs PyTorch",
            card["parity"]["max_probability_gap"],
            f"<= {c['max_parity_probability_gap']}",
            card["parity"]["max_probability_gap"] <= c["max_parity_probability_gap"],
        ),
        (
            "dev: searches that fail",
            dev["candidate"]["failure_rate"],
            f"<= {a['max_dev_failure_rate']}",
            dev["candidate"]["failure_rate"] <= a["max_dev_failure_rate"],
        ),
        (
            "dev: cost per search",
            dev["candidate"]["usd_per_search"],
            f"<= {a['max_usd_per_search']}",
            dev["candidate"]["usd_per_search"] <= a["max_usd_per_search"],
        ),
        (
            "drift: searches that fail",
            drift["candidate"]["failure_rate"],
            f"<= {drift['baseline']['failure_rate']} (production)",
            drift["candidate"]["failure_rate"] <= drift["baseline"]["failure_rate"],
        ),
        (
            "dev: suppliers sent to a person per search",
            dev["candidate"]["review_per_search"],
            f"<= {round(dev['baseline']['review_per_search'] + a['max_review_increase'], 2)}",
            dev["candidate"]["review_per_search"] <= dev["baseline"]["review_per_search"] + a["max_review_increase"],
        ),
    ]
    result["checks"] = [{"check": n, "value": v, "limit": lim, "passed": bool(ok)} for n, v, lim, ok in checks]
    result["passed"] = all(x["passed"] for x in result["checks"])
    out = args.out or ROOT / "reports" / f"gate-{args.candidate}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    registry.register(
        args.candidate,
        cand_dir,
        {
            "passed": result["passed"],
            "report": str(out.relative_to(ROOT)) if out.is_relative_to(ROOT) else str(out),
            "baseline": {
                "confidence_hist": dev["candidate"]["reading"]["confidence_hist"],
                "novel_share": round(
                    dev["candidate"]["reading"]["novel"] / max(dev["candidate"]["reading"]["sentences"], 1), 4
                ),
            },
        },
    )
    for x in result["checks"]:
        print(f"{'pass' if x['passed'] else 'FAIL'}  {x['check']}: {x['value']} ({x['limit']})")
    if args.promote:
        if not result["passed"]:
            sys.exit(f"{args.candidate} did not pass its gate; production stays {prod}")
        registry.promote(args.candidate)
        print(f"{args.candidate} is in production (was {prod})")


if __name__ == "__main__":
    main()
