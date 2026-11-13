"""Entry points. `uvicorn scout.service.main:app` serves the API and works the queue in a background thread;
`python -m scout.service.worker` works the queue only. Supplier pages come from SUPPLIER_PAGES (JSON lines)."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from scout import settings as settings_mod
from scout.index import HybridIndex
from scout.llm import AnthropicLLM
from scout.models import SupplierPage
from scout.service.app import Searches, create_app
from scout.service.bus import GcpPubSub, MemoryBus


def searches() -> Searches:
    s = settings_mod.load()
    pages = [SupplierPage.model_validate(json.loads(line))
             for line in Path(os.environ["SUPPLIER_PAGES"]).read_text().splitlines() if line.strip()]
    bus = GcpPubSub(os.environ["GCP_PROJECT"]) if os.environ.get("GCP_PROJECT") else MemoryBus()
    llm = AnthropicLLM(s["model"]["anthropic_model"], os.environ["ANTHROPIC_API_KEY"])
    return Searches(HybridIndex(pages, s["search"]["rrf_k"]), llm, s, bus)


def work_forever(sr: Searches, idle_seconds: float = 1.0) -> None:
    while True:
        if not sr.work():
            time.sleep(idle_seconds)


if os.environ.get("SUPPLIER_PAGES"):
    _searches = searches()
    threading.Thread(target=work_forever, args=(_searches,), daemon=True).start()
    app = create_app(_searches)
