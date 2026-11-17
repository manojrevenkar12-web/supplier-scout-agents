"""README results and dashboard data from reports/ and the model registry. Nothing here is typed by hand.

Each generated block sits between <!-- name:start --> and <!-- name:end --> in README.md.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGNS = ["single_shot", "agent_unverified", "agent", "agent_reader", "reader_only"]
OURS = DESIGNS.index("agent_reader")
NAMES = {
    "single_shot": "Single-shot RAG",
    "agent_unverified": "Agent, claims trusted",
    "agent": "Agent, keyword checks",
    "agent_reader": "Agent, stance reader + model fallback",
    "reader_only": "Stance reader, no fallback",
}


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def load(name: str) -> dict | list | None:
    p = ROOT / "reports" / name
    return json.loads(p.read_text()) if p.exists() else None


def reason(d: dict, key: str) -> int:
    return sum(v for k, v in d["failure_reasons"].items() if key in k)


def rows(rep: dict, designs: list[str]) -> list[dict]:
    def row(label, note, f):
        return {"label": label, "note": note, "values": [f(rep[d]) for d in designs]}

    n = rep[designs[0]]["searches"]
    return [
        row(
            "Searches that failed",
            f"of {n} RFQs; target under {pct(rep['target_failure_rate'])}",
            lambda d: pct(d["failure_rate"]),
        ),
        row("Shortlisted suppliers that really qualify", "precision of the shortlist", lambda d: pct(d["precision"])),
        row(
            "Qualified suppliers found",
            "of the shortlist size, or of all that exist when fewer",
            lambda d: pct(d["recall_at_k"]),
        ),
        row(
            "Shortlisted suppliers that cannot supply",
            "lapsed certificates, traders, processes sold, capacity",
            lambda d: str(reason(d, "unqualified")),
        ),
        row(
            "The same company twice in a shortlist",
            "one company under two domains or spellings",
            lambda d: str(reason(d, "same company")),
        ),
        row(
            "Suppliers shortlisted because their page told the AI to",
            "pages addressing AI assistants",
            lambda d: str(d["injected_suppliers_shortlisted"]),
        ),
        row(
            "Model calls per search",
            "the plan, then one per page, or only for sentences the reader is unsure of",
            lambda d: f"{d['model_calls_per_search']}",
        ),
        row("Cost per search", "Sonnet-class list prices, from token counts", lambda d: f"${d['usd_per_search']:.4f}"),
        row(
            "Suppliers sent to a person per search",
            "a deciding sentence unclear, or capacity not stated",
            lambda d: f"{d['review_per_search']}",
        ),
    ]


def table(rs: list[dict], heads: list[str], ours: int | None) -> str:
    out = ["| | " + " | ".join(heads) + " |", "|---|" + "---:|" * len(heads)]
    for r in rs:
        vals = [f"**{v}**" if i == ours else v for i, v in enumerate(r["values"])]
        note = f" <br><sub>{r['note']}</sub>" if r["note"] else ""
        out.append(f"| {r['label']}{note} | " + " | ".join(vals) + " |")
    return "\n".join(out)


def results_block(dev: dict) -> str:
    a = dev["agent_reader"]
    facts = (
        f"- **World:** {dev['companies']:,} companies on {dev['pages']:,} pages (some under two domains), in English "
        f"and German, a third of the facts worded in ways the keyword checks were not written for; {a['searches']} "
        f"RFQs with the truth about who can supply each.\n"
        f"- **Reader:** `{dev['reader']}` from the registry; it read {a['reading']['sentences']:,} sentences and was "
        f"unsure of {100 * a['reading']['unsure'] / max(a['reading']['sentences'], 1):.2f}%; "
        f"{a['sentences_asked']} distinct {'sentence' if a['sentences_asked'] == 1 else 'sentences'} went to the "
        "model (two readings each)."
    )
    return f"{table(rows(dev, DESIGNS), [NAMES[d] for d in DESIGNS], OURS)}\n\n{facts}"


def drift_rows(drift: dict, gate2: dict | None) -> tuple[list[dict], list[str]]:
    cols, heads = [drift["agent"]], [NAMES["agent"]]
    if gate2:
        v1 = gate2["worlds"]["drift"]["baseline"]
        cols.append(v1)
        heads.append(f"Stance reader {gate2['production']} + fallback")
    cols += [drift["agent_reader"], drift["reader_only"]]
    heads += [f"Stance reader {drift['reader']} + fallback", f"Stance reader {drift['reader']}, no fallback"]
    keep = [
        ("Searches that failed", "failure_rate", pct),
        ("Shortlisted suppliers that really qualify", "precision", pct),
        ("Model calls per search", "model_calls_per_search", str),
        ("Cost per search", "usd_per_search", lambda x: f"${x:.4f}"),
        ("Suppliers sent to a person per search", "review_per_search", str),
    ]
    return [{"label": label, "note": "", "values": [f(c[k]) for c in cols]} for label, k, f in keep], heads


def monitor_block(mon: list) -> str:
    out = [
        "| Window | Reader | Novel wording | Confidence PSI | Fallback calls per search | Cost per search | Alerts |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for w in mon:
        alerts = "<br>".join(w["alerts"]) or "none"
        out.append(
            f"| {w['window']} | `{w['reader']}` | {pct(w['novel_share'])} | {w['confidence_psi']} | "
            f"{w['fallback_calls_per_search']} | ${w['usd_per_search']:.4f} | {alerts} |"
        )
    return "\n".join(out)


def releases(reg: dict) -> list[dict]:
    out = []
    for v, e in sorted(reg["versions"].items()):
        c, gate = e["card"], load(Path(e["gate"]["report"]).name) if e.get("gate", {}).get("report") else None
        out.append(
            {
                "version": v,
                "production": v == reg["production"],
                "corpora": c["data"]["corpora"],
                "sentences": c["data"]["sentences"],
                "accuracy": c["validation"]["accuracy"],
                "macro_f1": c["validation"]["macro_f1"],
                "ece": c["validation"]["ece"],
                "min_confidence": c["min_confidence"],
                "int8_kb": round(c["size"]["int8_bytes"] / 1024),
                "float32_kb": round(c["size"]["float32_bytes"] / 1024),
                "parity": c["parity"]["same_label"],
                "passed": bool(e["gate"]["passed"]),
                "checks": gate["checks"] if gate else [],
            }
        )
    return out


def releases_block(rel: list[dict]) -> str:
    out = [
        "| Reader | Trained on | Validation accuracy | Calibration error | Size int8 (float32) | int8 = PyTorch "
        "| Gate |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for r in rel:
        tag = " (production)" if r["production"] else ""
        out.append(
            f"| `{r['version']}`{tag} | {' + '.join(r['corpora'])}, {r['sentences']:,} sentences | "
            f"{pct(r['accuracy'])} | {r['ece']} | {r['int8_kb']:,} KB ({r['float32_kb']:,} KB) | "
            f"{pct(r['parity'])} | {'passed' if r['passed'] else 'failed'} |"
        )
    last = rel[-1]
    out += ["", f"Gate of `{last['version']}`:", ""]
    out += [f"- {'pass' if c['passed'] else 'FAIL'}: {c['check']}: {c['value']} ({c['limit']})" for c in last["checks"]]
    return "\n".join(out)


def heldout_block(held: dict | None) -> str:
    if not held:
        return "Not run yet: `python3 scripts/evaluate.py --world heldout`, once (see AGENTS.md)."
    designs = [d for d in DESIGNS if d in held]
    return (
        f"Seed and companies not seen before, a quarter of the facts in the drifted wording, reader "
        f"`{held['reader']}`, run once at the commit in `config/heldout.lock`.\n\n"
        + table(rows(held, designs), [NAMES[d] for d in designs], designs.index("agent_reader"))
    )


def put(text: str, name: str, block: str) -> str:
    return re.sub(
        rf"<!-- {name}:start -->.*<!-- {name}:end -->",
        lambda _: f"<!-- {name}:start -->\n{block}\n<!-- {name}:end -->",
        text,
        flags=re.S,
    )


def main() -> None:
    dev, drift, mon, held = load("dev.json"), load("drift.json"), load("monitor.json"), load("heldout.json")
    reg = json.loads((ROOT / "models" / "registry.json").read_text())
    gate2 = load(f"gate-{reg['production']}.json")
    drs, dheads = drift_rows(drift, gate2)
    rel = releases(reg)
    readme = ROOT / "README.md"
    text = readme.read_text()
    text = put(text, "results", results_block(dev))
    text = put(text, "drift", table(drs, dheads, len(dheads) - 2))
    text = put(text, "monitor", monitor_block(mon))
    text = put(text, "releases", releases_block(rel))
    text = put(text, "heldout", heldout_block(held))
    readme.write_text(text)
    out = ROOT / "web/public/data/console.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "generated_from": "reports/ and models/registry.json",
                "designs": [NAMES[d] for d in DESIGNS],
                "ours": OURS,
                "ledger": rows(dev, DESIGNS),
                "reasons": {NAMES[d]: dev[d]["failure_reasons"] for d in DESIGNS},
                "target": dev["target_failure_rate"],
                "drift": {"designs": dheads, "ours": len(dheads) - 2, "rows": drs},
                "monitor": mon,
                "releases": rel,
            },
            indent=1,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
