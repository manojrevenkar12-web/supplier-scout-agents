"""Sentence features shared by training (PyTorch) and serving (NumPy): the same text gives the same indices.

Names of processes, materials and certificates are replaced by placeholders before hashing, so the reader learns how
a sentence stands (offered or stopped, valid or lapsed, made or bought) and not which certificate it names. Which
certificate a sentence is about is read by code from the taxonomy: identifiers decide, the model reads the stance.
"""

from __future__ import annotations

import re
import zlib

from scout.taxonomy import CERTS, MATERIALS, PROCESSES

BUCKETS = 1 << 15

_TERMS = sorted(
    [(w, "<cert>") for ws in CERTS.values() for w in ws]
    + [(w, "<proc>") for ws in PROCESSES.values() for w in ws]
    + [(w, "<mat>") for ws in MATERIALS.values() for w in ws if len(w) > 3],
    key=lambda x: -len(x[0]),
)
_TERM_RE = re.compile("|".join(re.escape(w) for w, _ in _TERMS))
_TERM_OF = dict(_TERMS)
_YEAR = re.compile(r"\b(19|20)\d\d\b")
_NUM = re.compile(r"\d[\d.,]*")
_WORD = re.compile(r"<\w+>|[a-zäöüß]+", re.UNICODE)


def mask(text: str) -> str:
    t = text.lower()
    t = _TERM_RE.sub(lambda m: f" {_TERM_OF[m.group(0)]} ", t)
    t = _YEAR.sub(" <year> ", t)
    return _NUM.sub(" <num> ", t)


def tokens(text: str) -> list[str]:
    return _WORD.findall(mask(text))


def features(text: str) -> list[str]:
    toks = tokens(text)
    out = [f"w:{t}" for t in toks]
    out += [f"b:{a}_{b}" for a, b in zip(toks, toks[1:], strict=False)]
    for t in toks:
        if t.startswith("<"):
            continue
        padded = f"<{t}>"
        out += [f"c:{padded[i : i + n]}" for n in (3, 4) for i in range(len(padded) - n + 1)]
    return out or ["w:<empty>"]


def indices(text: str) -> list[int]:
    return [zlib.crc32(f.encode()) % BUCKETS for f in features(text)]
