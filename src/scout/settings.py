import os
import tomllib
from pathlib import Path

# The checkout, or where an image keeps config/ and models/ (SCOUT_HOME=/app in the images)
ROOT = Path(os.environ.get("SCOUT_HOME", Path(__file__).resolve().parents[2]))


def load(path: Path | None = None) -> dict:
    return tomllib.loads((path or ROOT / "config" / "scout.toml").read_text())
