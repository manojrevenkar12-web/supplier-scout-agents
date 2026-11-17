"""The reader at serving time: NumPy only, int8 embeddings, no PyTorch in the service image.

A model directory holds `weights.npz` (int8 embedding rows with a scale per row, small float layers) and `card.json`
(labels, temperature, the confidence below which the reader asks for help, and the metrics it was released on).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from scout.nlp.features import indices


@dataclass
class Reading:
    label: str
    confidence: float
    novelty: float = 0.0


class Reader:
    def __init__(self, weights: dict[str, np.ndarray], card: dict):
        self.emb_q = weights["emb_q"]
        self.emb_scale = weights["emb_scale"]
        self.w1, self.b1 = weights["w1"], weights["b1"]
        self.w2, self.b2 = weights["w2"], weights["b2"]
        self.card = card
        self.labels: list[str] = card["labels"]
        self.temperature = float(card["temperature"])
        self.min_confidence = float(card["min_confidence"])
        self.max_novelty = float(card.get("max_novelty", 1.0))
        self.seen = np.unpackbits(weights["seen"]).astype(bool) if "seen" in weights else None

    @classmethod
    def load(cls, directory: Path) -> Reader:
        with np.load(directory / "weights.npz") as z:
            weights = {k: z[k] for k in z.files}
        return cls(weights, json.loads((directory / "card.json").read_text()))

    def probabilities(self, sentences: list[str]) -> np.ndarray:
        rows = np.zeros((len(sentences), self.emb_q.shape[1]), dtype=np.float32)
        for i, s in enumerate(sentences):
            idx = np.asarray(indices(s))
            rows[i] = (self.emb_q[idx].astype(np.float32) * self.emb_scale[idx, None]).mean(axis=0)
        h = np.maximum(rows @ self.w1.T + self.b1, 0.0)
        logits = (h @ self.w2.T + self.b2) / self.temperature
        logits -= logits.max(axis=1, keepdims=True)
        p = np.exp(logits)
        return p / p.sum(axis=1, keepdims=True)

    def novelty(self, sentence: str) -> float:
        if self.seen is None:
            return 0.0
        return float(1.0 - self.seen[indices(sentence)].mean())

    def read(self, sentences: list[str]) -> list[Reading]:
        """A reading of each sentence. Wording the model never saw in training gets confidence 0, whatever the
        softmax says, so the agent does not trust it."""
        if not sentences:
            return []
        p = self.probabilities(sentences)
        out = []
        for k, i in enumerate(p.argmax(axis=1)):
            nov = self.novelty(sentences[k])
            conf = float(p[k, i]) if nov <= self.max_novelty else 0.0
            out.append(Reading(self.labels[int(i)], conf, round(nov, 4)))
        return out


def quantize_rows(emb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Symmetric int8 per row: each embedding row keeps its own scale."""
    scale = np.abs(emb).max(axis=1) / 127.0
    scale[scale == 0] = 1.0
    q = np.clip(np.round(emb / scale[:, None]), -127, 127).astype(np.int8)
    return q, scale.astype(np.float32)
