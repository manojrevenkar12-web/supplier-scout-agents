"""Write the labelled sentence corpus the reader is trained on, from the training world.

    python3 scripts/export_labels.py            -> data/labels/base.jsonl

This stands in for an annotation team: procurement analysts who read supplier pages and mark what each sentence
says. It reads the training world's truth (other companies than the dev and held-out worlds, no novel phrasing),
so it lives with the evaluation scripts, not in src/scout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scout.world.sim import World  # noqa: E402


def main() -> None:
    world = World.load(ROOT / "config" / "train_world.toml")
    rows: dict[str, dict] = {}
    for said in world.page_sentences.values():
        for text, label, _tier in said:
            rows[text] = {"text": text, "label": label}
    out = ROOT / "data" / "labels" / "base.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(rows[k], ensure_ascii=False) + "\n" for k in sorted(rows)))
    print(f"{out.relative_to(ROOT)}: {len(rows)} sentences from {len(world.pages)} pages")


if __name__ == "__main__":
    main()
