"""One company, one row: suppliers that appear under several domains and spellings are merged."""

from __future__ import annotations

import re
import unicodedata

LEGAL = {
    "gmbh",
    "ag",
    "kg",
    "co",
    "sp",
    "z",
    "oo",
    "sro",
    "spa",
    "srl",
    "ltd",
    "inc",
    "kft",
    "lda",
    "sas",
    "sl",
    "bv",
    "as",
    "pvt",
    "group",
    "gruppe",
    "holding",
    "und",
    "and",
}
UMLAUT = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
EN_DE = {"precision": "praezision", "metal": "metall", "technology": "technik", "plastics": "kunststoff"}


def key(name: str) -> str:
    s = name.lower()
    for a, b in UMLAUT.items():
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[.,&]", "", s)  # "Sp. z o.o." -> "sp z oo", "Co., Ltd." -> "co ltd"
    words = [EN_DE.get(w, w) for w in re.findall(r"[a-z0-9]+", s) if w not in LEGAL]
    return " ".join(words)


def dedupe(items: list, name_of) -> tuple[list, int]:
    seen: set[str] = set()
    out, merged = [], 0
    for it in items:
        k = key(name_of(it))
        if k in seen:
            merged += 1
            continue
        seen.add(k)
        out.append(it)
    return out, merged
