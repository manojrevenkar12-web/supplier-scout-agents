import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(path: Path | None = None) -> dict:
    return tomllib.loads((path or ROOT / "config" / "scout.toml").read_text())
