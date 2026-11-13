from pathlib import Path

import pytest

from scout import settings as settings_mod
from scout.index import HybridIndex
from scout.world.sim import World

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def world():
    import tomllib

    cfg = tomllib.loads((ROOT / "config" / "world.toml").read_text())
    cfg.update(suppliers=400, rfqs=40)
    return World(cfg)


@pytest.fixture(scope="session")
def settings():
    return settings_mod.load()


@pytest.fixture(scope="session")
def index(world, settings):
    return HybridIndex(world.pages, settings["search"]["rrf_k"])
