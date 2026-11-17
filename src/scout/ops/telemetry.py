"""What the agent reports about each search, and the rolling checks that page someone.

A search record is one JSON log line (`scout.search`), which the log-based metrics in infra/terraform count. The
monitor keeps the last searches in memory and compares them with what the reader in production was released on:

- novel wording: the share of sentences the reader had never seen the like of (scout.nlp.runtime.Reader.novelty),
  against the share it was released with
- confidence drift: the population stability index of the reader's confidence against its release baseline
- fallbacks: model calls per search beyond the plan
- searches that end short: fewer suppliers than the shortlist size while candidates were read
- cost per search

The thresholds are in config/scout.toml [monitor].
"""

from __future__ import annotations

import json
import logging
import math
from collections import deque

log = logging.getLogger("scout.search")


def psi(expected: list[float], actual: list[float], floor: float = 1e-4) -> float:
    """Population stability index between two histograms with the same bins."""
    e_total, a_total = sum(expected) or 1, sum(actual) or 1
    out = 0.0
    for e, a in zip(expected, actual, strict=True):
        pe, pa = max(e / e_total, floor), max(a / a_total, floor)
        out += (pa - pe) * math.log(pa / pe)
    return round(out, 4)


def record(search_id: str, out: dict, usage, design: str, model: str | None, shortlist_size: int) -> dict:
    r = usage.reading
    rec = {
        "search": search_id,
        "design": design,
        "reader": model,
        "shortlist": len(out.get("shortlist", [])),
        "short": len(out.get("shortlist", [])) < shortlist_size,
        "review": len(out.get("review", [])),
        "model_calls": usage.calls,
        "usd": round(usage.usd, 5),
        "sentences": r["sentences"],
        "unsure": r["unsure"],
        "novel": r["novel"],
        "confidence_hist": r["confidence_hist"],
    }
    log.info(json.dumps({"event": "scout.search", **rec}))
    return rec


class Monitor:
    def __init__(self, settings: dict, baseline: dict | None = None):
        """`baseline` is what the reader in production was released on (registry: its gate on the dev world):
        the confidence histogram and the share of novel wording."""
        self.cfg = settings["monitor"]
        self.window: deque[dict] = deque(maxlen=self.cfg["window"])
        self.baseline = baseline or {}
        self.baseline_hist = self.baseline.get("confidence_hist")

    def add(self, rec: dict) -> None:
        self.window.append(rec)

    def summary(self) -> dict:
        w = list(self.window)
        if not w:
            return {"searches": 0, "alerts": []}
        sentences = sum(r["sentences"] for r in w) or 1
        hist = [sum(r["confidence_hist"][i] for r in w) for i in range(10)]
        s = {
            "searches": len(w),
            "novel_share": round(sum(r["novel"] for r in w) / sentences, 4),
            "unsure_share": round(sum(r["unsure"] for r in w) / sentences, 4),
            "fallback_calls_per_search": round(sum(max(r["model_calls"] - 1, 0) for r in w) / len(w), 3),
            "short_share": round(sum(r["short"] for r in w) / len(w), 4),
            "review_per_search": round(sum(r["review"] for r in w) / len(w), 3),
            "usd_per_search": round(sum(r["usd"] for r in w) / len(w), 5),
            "confidence_psi": psi(self.baseline_hist, hist) if self.baseline_hist else None,
        }
        c = self.cfg
        alerts = []
        limit = round(self.baseline.get("novel_share", 0.0) + c["novel_share_margin"], 4)
        if s["novel_share"] > limit:
            alerts.append(f"novel wording in {s['novel_share']:.1%} of sentences (limit {limit:.1%})")
        if s["confidence_psi"] is not None and s["confidence_psi"] > c["max_confidence_psi"]:
            alerts.append(f"reader confidence drifted: PSI {s['confidence_psi']} (limit {c['max_confidence_psi']})")
        if s["fallback_calls_per_search"] > c["max_fallback_calls_per_search"]:
            alerts.append(f"{s['fallback_calls_per_search']} fallback calls per search")
        if s["usd_per_search"] > c["max_usd_per_search"]:
            alerts.append(f"${s['usd_per_search']} per search")
        s["alerts"] = alerts
        s["retrain"] = bool(alerts) and any("novel" in a or "PSI" in a for a in alerts)
        return s
