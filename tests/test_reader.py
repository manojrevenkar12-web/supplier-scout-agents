import json
from pathlib import Path

import numpy as np
import pytest

from scout.models import Claim, Requirements, SupplierPage
from scout.nlp import registry
from scout.nlp.features import tokens
from scout.nlp.runtime import quantize_rows
from scout.ops.telemetry import Monitor, psi
from scout.verify import SENTENCE, StanceCache, read_page, verify

ROOT = Path(__file__).resolve().parents[1]
REQ = Requirements(process="cnc_milling", material="aluminium", certs=["ISO 9001"])


def page(text: str, capacity: int | None = 50_000) -> SupplierPage:
    return SupplierPage(
        supplier_id="S1", name="Alpen Präzision", domain="a.example", country="DE", capacity=capacity, text=text
    )


def test_identifiers_become_placeholders_so_the_reader_learns_the_stance():
    assert tokens("Our ISO 9001 certificate lapsed in 2024.") == [
        "our",
        "<cert>",
        "certificate",
        "lapsed",
        "in",
        "<year>",
    ]
    assert "<proc>" in tokens("Wir bieten CNC-Fräsen an") and "<mat>" in tokens("Edelstahl und Aluminium")


def test_a_certificate_number_is_not_a_sentence_end():
    parts = SENTENCE.split("Certified. ISO 9001 certificate no. 41363, valid until 03/2027. Nr. 5 gilt.")
    assert parts == ["Certified.", "ISO 9001 certificate no. 41363, valid until 03/2027.", "Nr. 5 gilt."]


def test_lapsed_in_other_words_fools_the_keyword_check_but_not_the_reader(settings, reader):
    p = page(
        "Alpen Präzision is a manufacturer with in-house production. Our core capability is cnc milling. "
        "We work with aluminium. Our ISO 9001 certificate lapsed in 2024. Located in DE."
    )
    claim = Claim(
        process=True,
        material=True,
        certs=["ISO 9001"],
        manufacturer=True,
        evidence={
            "ISO 9001": "Our ISO 9001 certificate lapsed in 2024.",
            "manufacturer": "Alpen Präzision is a manufacturer with in-house production.",
        },
    )
    assert verify(p, claim, REQ, settings).qualified  # the keyword list has no "lapsed"
    v, calls = read_page(p, REQ, reader, None, None, settings)
    assert not v.qualified and "lapsed" in v.reasons[0] and calls == 0


def test_wording_the_reader_never_saw_is_asked_twice_and_kept_once(settings, reader):
    novel = "Zwölf Roboterzellen schweißen hier rund um die Uhr, betreut von unseren Leuten vor Ort."
    assert reader.read([novel])[0].confidence == 0.0 and reader.novelty(novel) > reader.max_novelty
    p = page(f"{novel} Our core capability is cnc milling. We work with aluminium. Certified to ISO 9001.")
    asked = []

    def ask(sentence, question):
        asked.append((sentence, question))
        return "MAKES"

    cache = StanceCache()
    v, calls = read_page(p, REQ, reader, ask, cache, settings)
    assert v.qualified and calls == 2 and len({q for _, q in asked}) == 2  # two readings, framed differently
    v, calls = read_page(p, REQ, reader, ask, cache, settings)
    assert v.qualified and calls == 0  # the agreed answer is reused, not bought again


def test_readings_that_disagree_go_to_a_person(settings, reader):
    p = page(
        "Zwölf Roboterzellen schweißen hier rund um die Uhr, betreut von unseren Leuten vor Ort. "
        "Our core capability is cnc milling. "
        "We work with aluminium. Certified to ISO 9001."
    )
    answers = iter(["MAKES", "TRADES"])
    v, _ = read_page(p, REQ, reader, lambda s, q: next(answers), StanceCache(), settings)
    assert not v.qualified and v.needs_review


def test_a_certificate_named_for_someone_else_is_not_held(settings, reader):
    p = page(
        "Alpen Präzision ist ein Hersteller mit eigener Fertigung. Unsere Kernkompetenz: cnc milling. "
        "We work with aluminium. Our customers include ISO 9001 certified medical and automotive companies."
    )
    v, _ = read_page(p, REQ, reader, None, None, settings)
    assert not v.qualified and "not held" in " ".join(v.reasons)


def test_int8_rows_keep_the_embedding():
    emb = np.random.default_rng(0).normal(size=(64, 16)).astype(np.float32)
    q, scale = quantize_rows(emb)
    assert q.dtype == np.int8 and np.abs(q.astype(np.float32) * scale[:, None] - emb).max() < scale.max()


def test_training_exports_a_runtime_that_reads_like_pytorch(tmp_path, settings):
    pytest.importorskip("torch")
    from scout.nlp.train import train

    rows = [json.loads(x) for x in (ROOT / "data" / "labels" / "base.jsonl").read_text().splitlines()[::4]]
    corpus = tmp_path / "small.jsonl"
    corpus.write_text("".join(json.dumps(r) + "\n" for r in rows))
    cfg = {**settings, "reader": {**settings["reader"], "epochs": 3}}
    card = train([corpus], tmp_path / "m", cfg)
    assert card["parity"]["same_label"] >= 0.999 and card["parity"]["max_probability_gap"] < 0.02
    assert card["size"]["int8_bytes"] < card["size"]["float32_bytes"] / 3
    assert 0 < card["min_confidence"] <= 1 and card["validation"]["accepted_accuracy"] >= 0.99


def test_a_reader_reaches_production_only_through_its_gate(tmp_path):
    reg = tmp_path / "registry.json"
    reg.write_text(
        json.dumps(
            {
                "production": "v1",
                "versions": {
                    "v1": {"path": "models/v1", "gate": {"passed": True}},
                    "bad": {"path": "models/v1", "gate": {"passed": False}},
                },
            }
        )
    )
    with pytest.raises(ValueError):
        registry.promote("bad", reg)
    assert registry.promote("v1", reg)["production"] == "v1"


def test_the_monitor_raises_drift_and_novel_wording(settings):
    assert psi([10, 10, 80], [10, 10, 80]) == 0 and psi([10, 10, 80], [60, 30, 10]) > 0.5
    base = {"confidence_hist": [1, 0, 0, 0, 0, 0, 0, 0, 0, 99], "novel_share": 0.01}
    mon = Monitor(settings, base)
    for i in range(20):
        mon.add(
            {
                "search": i,
                "short": False,
                "review": 1,
                "model_calls": 6,
                "usd": 0.004,
                "sentences": 100,
                "unsure": 30,
                "novel": 25,
                "confidence_hist": [30, 0, 0, 0, 0, 0, 0, 0, 0, 70],
            }
        )
    s = mon.summary()
    assert s["retrain"] and any("novel wording" in a for a in s["alerts"]) and any("PSI" in a for a in s["alerts"])


def test_the_service_image_needs_no_pytorch():
    import ast

    for path in (ROOT / "src" / "scout").rglob("*.py"):
        if path.name == "train.py":
            continue  # training runs in the trainer image
        names = {
            n.names[0].name.split(".")[0] for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, ast.Import)
        } | {
            n.module.split(".")[0]
            for n in ast.walk(ast.parse(path.read_text()))
            if isinstance(n, ast.ImportFrom) and n.module
        }
        assert "torch" not in names, path
