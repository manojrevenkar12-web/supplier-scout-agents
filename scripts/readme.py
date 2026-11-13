"""README results and dashboard data from reports/. Nothing here is typed by hand."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGNS = ["single_shot", "agent_unverified", "agent"]
NAMES = {"single_shot": "Single-shot RAG", "agent_unverified": "Agent, claims trusted", "agent": "Agent, claims checked"}


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def rows(rep: dict) -> list[dict]:
    def row(label, note, f):
        return {"label": label, "note": note, "values": [f(rep[d]) for d in DESIGNS]}

    reason = lambda d, key: sum(v for k, v in d["failure_reasons"].items() if key in k)  # noqa: E731
    return [
        row("Searches that failed", f"of {rep['agent']['searches']} RFQs; target under {pct(rep['target_failure_rate'])}",
            lambda d: pct(d["failure_rate"])),
        row("Shortlisted suppliers that really qualify", "precision of the shortlist", lambda d: pct(d["precision"])),
        row("Qualified suppliers found", "of the shortlist size, or of all that exist when fewer",
            lambda d: pct(d["recall_at_k"])),
        row("Shortlisted suppliers that cannot supply", "expired certificates, traders, discontinued processes, capacity",
            lambda d: str(reason(d, "unqualified"))),
        row("The same company twice in a shortlist", "one company under two domains or spellings",
            lambda d: str(reason(d, "same company"))),
        row("Suppliers shortlisted because their page told the AI to", "pages addressing AI assistants",
            lambda d: str(d["injected_suppliers_shortlisted"])),
        row("Model calls per search", "one for the plan, one per page qualified", lambda d: f"{d['model_calls_per_search']}"),
        row("Cost per search", "Sonnet-class list prices, from token counts", lambda d: f"${d['usd_per_search']:.3f}"),
    ]


def table(dev: dict, held: dict | None) -> str:
    r, h = rows(dev), rows(held) if held else None
    head = "| | " + " | ".join(NAMES[d] for d in DESIGNS) + " |" + (" Checked, held-out | Trusted, held-out |" if h else "")
    out = [head, "|---|" + "---:|" * (3 + (2 if h else 0))]
    for i, x in enumerate(r):
        line = f"| {x['label']} <br><sub>{x['note']}</sub> | {x['values'][0]} | {x['values'][1]} | **{x['values'][2]}** |"
        if h:
            line += f" **{h[i]['values'][2]}** | {h[i]['values'][1]} |"
        out.append(line)
    return "\n".join(out)


def main() -> None:
    dev = json.loads((ROOT / "reports/dev.json").read_text())
    hp = ROOT / "reports/heldout.json"
    held = json.loads(hp.read_text()) if hp.exists() else None
    a = dev["agent"]
    facts = (f"- **World:** {dev['companies']:,} companies on {dev['pages']:,} pages (some under two domains), in English "
             f"and German; {a['searches']} RFQs with the truth about who can supply each.\n"
             f"- **Sent to a person:** {a['review_per_search']} suppliers per search on average, where capacity or "
             "own production is not stated; they are asked about, not shortlisted.")
    readme = ROOT / "README.md"
    text = re.sub(r"<!-- results:start -->.*<!-- results:end -->",
                  lambda _: f"<!-- results:start -->\n{table(dev, held)}\n\n{facts}\n<!-- results:end -->",
                  readme.read_text(), flags=re.S)
    readme.write_text(text)
    out = ROOT / "web/public/data/console.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generated_from": "reports/dev.json", "designs": [NAMES[d] for d in DESIGNS], "ledger": rows(dev),
        "reasons": {NAMES[d]: dev[d]["failure_reasons"] for d in DESIGNS},
        "target": dev["target_failure_rate"],
    }, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
