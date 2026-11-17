"""Copy a gated reader and the registry to the models bucket the API pods load from.

    python3 scripts/publish.py --version v3 --bucket my-project-scout-models

Without --bucket (a local or CI run) it only prints what it would publish.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--bucket", default="")
    args = ap.parse_args()
    reg = json.loads((ROOT / "models" / "registry.json").read_text())
    entry = reg["versions"][args.version]
    files = [
        ROOT / entry["path"] / "weights.npz",
        ROOT / entry["path"] / "card.json",
        ROOT / "models" / "registry.json",
    ]
    print(json.dumps({"version": args.version, "production": reg["production"], "gate": entry["gate"]["passed"]}))
    if not args.bucket:
        print("no bucket: nothing published")
        return
    if not entry["gate"]["passed"]:
        sys.exit(f"{args.version} did not pass its gate; not published")
    from google.cloud import storage

    bucket = storage.Client().bucket(args.bucket)
    for f in files:
        bucket.blob(f"models/{f.relative_to(ROOT / 'models')}").upload_from_filename(f)
        print(f"gs://{args.bucket}/models/{f.relative_to(ROOT / 'models')}")


if __name__ == "__main__":
    main()
