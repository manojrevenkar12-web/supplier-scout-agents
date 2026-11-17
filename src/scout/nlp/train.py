"""Train the stance reader in PyTorch and export it for the NumPy runtime.

    python -m scout.nlp.train --corpus data/labels/base.jsonl [--corpus data/labels/harvested.jsonl] --out models/v1

The model is a bag of hashed word, bigram and character n-gram features (EmbeddingBag) and a small MLP. After
training: temperature scaling on the validation split, the confidence threshold below which the reader asks for
help (the smallest that keeps accepted readings at the accuracy in config/scout.toml), int8 export and a parity check
of the exported runtime against PyTorch. Everything measured goes into card.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from torch import nn

from scout import settings as settings_mod
from scout.models import STANCES
from scout.nlp.features import BUCKETS, indices
from scout.nlp.runtime import Reader, quantize_rows

LABELS = STANCES


class StanceModel(nn.Module):
    def __init__(self, dim: int, hidden: int, classes: int):
        super().__init__()
        self.emb = nn.EmbeddingBag(BUCKETS, dim, mode="mean")
        self.fc1 = nn.Linear(dim, hidden)
        self.fc2 = nn.Linear(hidden, classes)

    def forward(self, flat: torch.Tensor, offsets: torch.Tensor) -> torch.Tensor:
        return self.fc2(torch.relu(self.fc1(self.emb(flat, offsets))))


def batch(texts: list[str]) -> tuple[torch.Tensor, torch.Tensor]:
    idx = [indices(t) for t in texts]
    offsets = torch.tensor([0, *np.cumsum([len(i) for i in idx])[:-1]], dtype=torch.long)
    return torch.tensor([j for i in idx for j in i], dtype=torch.long), offsets


def read_corpus(paths: list[Path]) -> list[dict]:
    seen: dict[str, dict] = {}
    for p in paths:
        for line in p.read_text().splitlines():
            row = json.loads(line)
            seen[row["text"]] = row  # a later corpus (harvested labels) overrides an earlier one
    return [seen[k] for k in sorted(seen)]


def split(rows: list[dict], share: float) -> tuple[list[dict], list[dict]]:
    """A stable split by text hash, so the same sentence is always on the same side."""
    val = [r for r in rows if int(hashlib.sha256(r["text"].encode()).hexdigest()[:8], 16) % 1000 < share * 1000]
    keep = {r["text"] for r in val}
    return [r for r in rows if r["text"] not in keep], val


def ece(conf: np.ndarray, correct: np.ndarray, bins: int = 15) -> float:
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            total += m.mean() * abs(conf[m].mean() - correct[m].mean())
    return float(total)


def train(corpus: list[Path], out: Path, settings: dict) -> dict:
    cfg = settings["reader"]
    torch.manual_seed(cfg["seed"])
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    rows = read_corpus(corpus)
    tr, va = split(rows, cfg["validation_share"])
    y_tr = torch.tensor([LABELS.index(r["label"]) for r in tr])
    counts = Counter(r["label"] for r in tr)
    weight = torch.tensor([1.0 / np.sqrt(max(counts[label], 1)) for label in LABELS], dtype=torch.float32)
    weight = weight / weight.mean()
    model = StanceModel(cfg["dim"], cfg["hidden"], len(LABELS))
    opt = torch.optim.Adam(model.parameters(), lr=cfg["learning_rate"])
    loss_fn = nn.CrossEntropyLoss(weight=weight)
    g = torch.Generator().manual_seed(cfg["seed"])
    t0 = time.perf_counter()
    for _ in range(cfg["epochs"]):
        order = torch.randperm(len(tr), generator=g).tolist()
        for i in range(0, len(order), cfg["batch_size"]):
            ids = order[i : i + cfg["batch_size"]]
            flat, offsets = batch([tr[j]["text"] for j in ids])
            opt.zero_grad()
            loss_fn(model(flat, offsets), y_tr[ids]).backward()
            opt.step()
    train_seconds = time.perf_counter() - t0

    model.eval()
    texts = [r["text"] for r in va]
    y_va = np.array([LABELS.index(r["label"]) for r in va])
    with torch.no_grad():
        logits = model(*batch(texts)).numpy()

    def probs(t: float) -> np.ndarray:
        z = logits / t
        z = z - z.max(axis=1, keepdims=True)
        e = np.exp(z)
        return e / e.sum(axis=1, keepdims=True)

    def nll(t: float) -> float:
        return float(-np.log(probs(t)[np.arange(len(y_va)), y_va] + 1e-12).mean())

    temperature = min(np.round(np.arange(0.5, 5.01, 0.05), 2), key=nll)
    p = probs(temperature)
    conf, pred = p.max(axis=1), p.argmax(axis=1)
    correct = (pred == y_va).astype(float)
    # the smallest threshold whose accepted readings are at least as accurate as the target
    min_conf = 1.0
    for c in sorted(set(np.round(conf, 4))):
        m = conf >= c
        if m.any() and correct[m].mean() >= cfg["accept_accuracy"]:
            min_conf = float(c)
            break
    accepted = conf >= min_conf
    per_label = {}
    for k, label in enumerate(LABELS):
        if not ((y_va == k).any() or (pred == k).any()):
            continue  # a label with no validation example says nothing either way
        tp = int(((pred == k) & (y_va == k)).sum())
        fp, fn = int(((pred == k) & (y_va != k)).sum()), int(((pred != k) & (y_va == k)).sum())
        per_label[label] = round(2 * tp / max(2 * tp + fp + fn, 1), 4)

    # novelty: the share of a sentence's features the model never saw in training. Softmax confidence does not
    # fall on wording the model has never seen; this does.
    seen = np.zeros(BUCKETS, dtype=bool)
    for r in tr:
        seen[indices(r["text"])] = True
    novelty_va = np.array([1.0 - seen[indices(t)].mean() for t in texts])
    max_novelty = float(np.quantile(novelty_va, cfg["novelty_quantile"])) + cfg["novelty_margin"]

    out.mkdir(parents=True, exist_ok=True)
    emb = model.emb.weight.detach().numpy()
    q, scale = quantize_rows(emb)
    weights = {
        "emb_q": q,
        "emb_scale": scale,
        "w1": model.fc1.weight.detach().numpy(),
        "b1": model.fc1.bias.detach().numpy(),
        "w2": model.fc2.weight.detach().numpy(),
        "b2": model.fc2.bias.detach().numpy(),
        "seen": np.packbits(seen),
    }
    np.savez_compressed(out / "weights.npz", **weights)
    data_hash = hashlib.sha256("".join(f"{r['text']}\t{r['label']}\n" for r in rows).encode()).hexdigest()[:12]
    card = {
        "labels": LABELS,
        "temperature": float(temperature),
        "min_confidence": round(min_conf, 4),
        "max_novelty": round(max_novelty, 4),
        "data": {
            "corpora": [p.name for p in corpus],
            "sentences": len(rows),
            "train": len(tr),
            "validation": len(va),
            "sha256": data_hash,
            "labels": dict(sorted(counts.items())),
        },
        "params": {k: cfg[k] for k in ("dim", "hidden", "epochs", "batch_size", "learning_rate", "seed")},
        "validation": {
            "accuracy": round(float(correct.mean()), 4),
            "macro_f1": round(float(np.mean(list(per_label.values()))), 4),
            "f1": per_label,
            "ece_before_scaling": round(ece(probs(1.0).max(axis=1), correct), 4),
            "ece": round(ece(conf, correct), 4),
            "accepted_share": round(float(accepted.mean()), 4),
            "accepted_accuracy": round(float(correct[accepted].mean()), 4) if accepted.any() else 0.0,
            "novelty_p50": round(float(np.median(novelty_va)), 4),
        },
        "size": {
            "float32_bytes": int(emb.nbytes + sum(w.nbytes for k, w in weights.items() if k[0] in "wb")),
            "int8_bytes": int(
                q.nbytes + scale.nbytes + sum(w.nbytes for k, w in weights.items() if k[0] in "wb" or k == "seen")
            ),
        },
        "train_seconds": round(train_seconds, 1),
    }
    (out / "card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")

    # the exported int8 runtime must read like the PyTorch model it came from
    runtime = Reader.load(out)
    rp = runtime.probabilities(texts)
    card["parity"] = {
        "same_label": round(float((rp.argmax(axis=1) == pred).mean()), 4),
        "max_probability_gap": round(float(np.abs(rp - p).max()), 4),
    }
    (out / "card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    return card


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", action="append", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    card = train(args.corpus, args.out, settings_mod.load())
    v = card["validation"]
    print(
        f"{args.out}: accuracy {v['accuracy']:.4f}  macro-F1 {v['macro_f1']:.4f}  ECE {v['ece_before_scaling']:.3f}"
        f" -> {v['ece']:.3f}  accepts {v['accepted_share']:.1%} at >= {card['min_confidence']}"
        f" ({v['accepted_accuracy']:.2%} right)  parity {card['parity']['same_label']:.4f}"
    )


if __name__ == "__main__":
    main()
