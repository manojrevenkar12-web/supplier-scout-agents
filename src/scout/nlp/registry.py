"""The model registry: every trained reader with its card and gate verdict, and which one is in production.

models/registry.json
    {"production": "v1", "versions": {"v1": {"path": "models/v1", "card": {...}, "gate": {...}, "promoted": ...}}}

A version is promoted only if its release gate passed (scripts/gate.py); the agent loads the production entry.
"""

from __future__ import annotations

import json
from pathlib import Path

from scout.nlp.runtime import Reader
from scout.settings import ROOT

REGISTRY = ROOT / "models" / "registry.json"


def read(path: Path = REGISTRY) -> dict:
    return json.loads(path.read_text()) if path.exists() else {"production": None, "versions": {}}


def write(reg: dict, path: Path = REGISTRY) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reg, indent=2, sort_keys=True) + "\n")


def register(version: str, model_dir: Path, gate: dict | None = None, path: Path = REGISTRY) -> dict:
    reg = read(path)
    card = json.loads((model_dir / "card.json").read_text())
    reg["versions"][version] = {
        "path": str(model_dir.relative_to(ROOT)) if model_dir.is_absolute() else str(model_dir),
        "card": {k: card[k] for k in ("data", "validation", "size", "parity", "min_confidence", "temperature")},
        "gate": gate,
    }
    write(reg, path)
    return reg


def promote(version: str, path: Path = REGISTRY) -> dict:
    reg = read(path)
    entry = reg["versions"][version]
    if not (entry.get("gate") or {}).get("passed"):
        raise ValueError(f"{version} has not passed its release gate")
    reg["previous"] = reg.get("production")
    reg["production"] = version
    write(reg, path)
    return reg


def load(name: str = "production", path: Path = REGISTRY) -> Reader:
    reg = read(path)
    version = reg["production"] if name == "production" else name
    if not version:
        raise FileNotFoundError("no reader in production: train one and pass its gate (see SKILLS.md)")
    entry = reg["versions"][version]
    reader = Reader.load(ROOT / entry["path"])
    reader.card["version"] = version
    reader.card["baseline"] = (entry.get("gate") or {}).get("baseline")
    return reader
