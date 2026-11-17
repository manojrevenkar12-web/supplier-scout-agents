"""Retrain the readers in the registry from their corpora and compare with the committed model cards.

    python3 scripts/check_training.py [--tolerance 0.005]

Weights are not compared: PyTorch on another CPU or version may differ in the last bits. What must hold is what the
release was decided on: validation accuracy, accepted share and accuracy, the confidence threshold and the parity of
the int8 runtime, each within the tolerance.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scout import settings as settings_mod  # noqa: E402
from scout.nlp import registry  # noqa: E402
from scout.nlp.train import train  # noqa: E402

KEYS = [
    ("validation", "accuracy"),
    ("validation", "accepted_share"),
    ("validation", "accepted_accuracy"),
    ("parity", "same_label"),
    ("min_confidence",),
    ("max_novelty",),
]


def get(card: dict, path: tuple) -> float:
    for k in path:
        card = card[k]
    return float(card)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tolerance", type=float, default=0.005)
    ap.add_argument("--threshold-tolerance", type=float, default=0.15)
    args = ap.parse_args()
    settings = settings_mod.load()
    bad = []
    for version, entry in sorted(registry.read()["versions"].items()):
        committed = json.loads((ROOT / entry["path"] / "card.json").read_text())
        corpora = [ROOT / "data" / "labels" / name for name in committed["data"]["corpora"]]
        with tempfile.TemporaryDirectory() as tmp:
            card = train(corpora, Path(tmp) / version, settings)
        if card["data"]["sha256"] != committed["data"]["sha256"]:
            bad.append(f"{version}: the corpus changed ({card['data']['sha256']} vs {committed['data']['sha256']})")
        for path in KEYS:
            a, b = get(card, path), get(committed, path)
            tol = args.threshold_tolerance if path[0] in ("min_confidence", "max_novelty") else args.tolerance
            ok = abs(a - b) <= tol
            print(f"{'ok ' if ok else 'BAD'} {version} {'.'.join(path)}: {a} (committed {b})")
            if not ok:
                bad.append(f"{version} {'.'.join(path)}: {a} vs {b}")
    if bad:
        sys.exit("\n".join(bad))


if __name__ == "__main__":
    main()
