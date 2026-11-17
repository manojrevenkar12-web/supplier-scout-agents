"""Hybrid retrieval over supplier pages: BM25 for exact terms, TF-IDF on character n-grams for spelling and
German compounds, fused by reciprocal rank."""

from __future__ import annotations

import re

import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer

from scout.models import Requirements, SupplierPage
from scout.taxonomy import CERTS, MATERIALS, PROCESSES

TOKEN = re.compile(r"[a-zäöüß0-9.]+")


def tokens(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


class HybridIndex:
    def __init__(self, pages: list[SupplierPage], rrf_k: int = 60):
        self.pages = pages
        self.rrf_k = rrf_k
        self.bm25 = BM25Okapi([tokens(p.text) for p in pages])
        self.tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True)
        self.matrix = self.tfidf.fit_transform([p.text.lower() for p in pages])
        # facets: which pages name each process and each material (whole terms), for exhaustive retrieval
        from scout.verify import materials_on

        lower = [p.text.lower() for p in pages]
        self.by_process = {
            k: {i for i, t in enumerate(lower) if any(w in t for w in ws)} for k, ws in PROCESSES.items()
        }
        self.by_material: dict[str, set[int]] = {k: set() for k in MATERIALS}
        for i, t in enumerate(lower):
            for m in materials_on(t):
                self.by_material[m].add(i)

    @staticmethod
    def query_for(req: Requirements, widen: bool = False) -> str:
        words = [*PROCESSES[req.process][: 5 if widen else 2], *MATERIALS[req.material][: 3 if widen else 1]]
        words += [CERTS[c][0] for c in req.certs]
        return " ".join(words)

    def search(self, query: str, k: int, countries: list[str] | None = None) -> list[SupplierPage]:
        """Hybrid search; `countries` filters before ranking, so the region never wastes a candidate slot."""
        bm = self.bm25.get_scores(tokens(query))
        dense = (self.matrix @ self.tfidf.transform([query.lower()]).T).toarray().ravel()
        fused = np.zeros(len(self.pages))
        for scores in (bm, dense):
            order = np.argsort(-scores, kind="stable")
            fused[order] += 1.0 / (self.rrf_k + np.arange(1, len(order) + 1))
        if countries:
            allowed = set(countries)
            fused[[i for i, p in enumerate(self.pages) if p.country not in allowed]] = -1.0
        top = [i for i in np.argsort(-fused, kind="stable")[:k] if fused[i] >= 0]
        return [self.pages[i] for i in top]

    def search_bm25(self, query: str, k: int) -> list[SupplierPage]:
        scores = self.bm25.get_scores(tokens(query))
        return [self.pages[i] for i in np.argsort(-scores, kind="stable")[:k]]

    def facets(self, req: Requirements) -> list[SupplierPage]:
        """Every page that names the process and the material, in the region: no ranking, nothing cut off.
        Affordable when reading a page costs no model call (the stance reader)."""
        hits = self.by_process[req.process] & self.by_material[req.material]
        allowed = set(req.region) if req.region else None
        return [self.pages[i] for i in sorted(hits) if allowed is None or self.pages[i].country in allowed]
