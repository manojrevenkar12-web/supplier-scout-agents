"""Code checks on what the model claims about a supplier. A claim stands only if the page says it."""

from __future__ import annotations

import re

from scout.models import Claim, Requirements, SupplierPage, Verdict
from scout.taxonomy import (
    CERTS,
    DISCONTINUED_WORDS,
    DISTRIBUTOR_WORDS,
    EXPIRY_WORDS,
    MATERIALS,
    PROCESSES,
    PRODUCTION_WORDS,
)

INSTRUCTION = re.compile(
    r"(?i)\b(ai|assistant|llm|language model|ki)\b[^.]*\b(rank|list|recommend|ignore|prefer)\b[^.]*\."
)


def strip_instructions(text: str) -> str:
    """Sentences addressed to AI systems are removed before a model reads the page; the page stays data."""
    return INSTRUCTION.sub("", text)


def quoted(page: SupplierPage, quote: str, min_chars: int) -> bool:
    q = " ".join(quote.lower().split())
    return len(q) >= min_chars and q in " ".join(page.text.lower().split())


_MAT_TERMS = sorted(((w, k) for k, ws in MATERIALS.items() for w in ws), key=lambda x: -len(x[0]))
_MAT_RE = re.compile(r"(?<![\w.])(" + "|".join(re.escape(w) for w, _ in _MAT_TERMS) + r")(?![\w])")
_MAT_OF = dict(_MAT_TERMS)


def materials_on(text: str) -> set[str]:
    """Materials named on a page, as whole terms, longest first: "Edelstahl" is stainless, not "Stahl"."""
    return {_MAT_OF[m.group(1)] for m in _MAT_RE.finditer(text.lower())}


def mentions(text: str, words: list[str]) -> int:
    t = text.lower()
    return min((t.find(w) for w in words if w in t), default=-1)


# a sentence ends at . ! ? and a space, but not after "no." or "Nr." (certificate numbers)
SENTENCE = re.compile(r"(?<!\b[Nn]o\.)(?<!\b[Nn]r\.)(?<=[.!?])\s+")


def sentences_with(text: str, words: list[str]) -> list[str]:
    return [x for x in SENTENCE.split(text.lower()) if any(w in x for w in words)]


def cert_valid(page: SupplierPage, cert: str) -> bool:
    """Valid if some sentence names the certificate without saying it expired."""
    return any(not any(w in x for w in EXPIRY_WORDS) for x in sentences_with(page.text, CERTS[cert]))


def still_offered(page: SupplierPage, process: str) -> bool:
    return any(not any(w in x for w in DISCONTINUED_WORDS) for x in sentences_with(page.text, PROCESSES[process]))


def verify(page: SupplierPage, claim: Claim, req: Requirements, settings: dict) -> Verdict:
    v = settings["verify"]
    reasons: list[str] = []
    text = page.text.lower()
    if not (claim.process and mentions(text, PROCESSES[req.process]) >= 0):
        reasons.append(f"process {req.process} not on the page")
    elif not still_offered(page, req.process):
        reasons.append(f"page says {req.process} is no longer offered")
    if not (claim.material and mentions(text, MATERIALS[req.material]) >= 0):
        reasons.append(f"material {req.material} not on the page")
    for cert in req.certs:
        if cert not in claim.certs:
            reasons.append(f"{cert} not claimed")
        elif not quoted(page, claim.evidence.get(cert, ""), v["evidence_min_chars"]):
            reasons.append(f"{cert}: the quoted evidence is not on the page")
        elif not cert_valid(page, cert):
            reasons.append(f"{cert}: the page says it expired")
    needs_review = False
    if req.manufacturer_only and (not claim.manufacturer or any(w in text for w in DISTRIBUTOR_WORDS)):
        reasons.append("not a manufacturer")
    elif req.manufacturer_only:
        quote = claim.evidence.get("manufacturer", "")
        if not (quoted(page, quote, v["evidence_min_chars"]) and any(w in quote.lower() for w in PRODUCTION_WORDS)):
            needs_review = True  # no sentence says they make it themselves: a person asks
    if req.region and page.country not in req.region:
        reasons.append(f"located in {page.country}, outside the region")
    if req.min_capacity:
        if page.capacity is None:
            needs_review = True  # a person asks; the page does not say
        elif page.capacity < req.min_capacity:
            reasons.append(f"capacity {page.capacity:,} below {req.min_capacity:,}")
    fit = 0.0 if reasons else 1.0 + (min(page.capacity or 0, 4 * req.min_capacity) / max(req.min_capacity, 1)) / 10
    return Verdict(
        supplier_id=page.supplier_id,
        name=page.name,
        qualified=not reasons and not needs_review,
        reasons=reasons or (["capacity or own production not stated"] if needs_review else []),
        needs_review=needs_review and not reasons,
        fit=round(fit, 4),
    )


def trust(page: SupplierPage, claim: Claim, req: Requirements) -> Verdict:
    """The unverified designs: the model's claim is taken as it is."""
    ok = (
        claim.process
        and claim.material
        and all(c in claim.certs for c in req.certs)
        and (claim.manufacturer or not req.manufacturer_only)
        and (not req.region or page.country in req.region)
        and (not req.min_capacity or (page.capacity or 0) >= req.min_capacity or page.capacity is None)
    )
    return Verdict(supplier_id=page.supplier_id, name=page.name, qualified=ok, fit=claim.score)


# ---- the reader: a trained model reads the stance of each sentence, code decides ---------------------------------
class StanceCache:
    """What a sentence says does not depend on the RFQ: an answer bought from the model is kept and reused, and it
    is what the retraining loop harvests (scripts/harvest.py)."""

    def __init__(self) -> None:
        self.answers: dict[str, str] = {}
        self.asked = 0

    def key(self, sentence: str) -> str:
        return " ".join(sentence.lower().split())


def read_page(
    page: SupplierPage,
    req: Requirements,
    reader,
    ask,
    cache: StanceCache | None,
    settings: dict,
    stats: dict | None = None,
):
    """Decide a page from the stance of its sentences.

    `reader` reads every sentence (NumPy, no model call). A sentence that decides a requirement and that the reader
    is not sure about goes to `ask` (the LLM, one short call) or, when `ask` is None, the supplier goes to a person.
    Returns the verdict and the number of model calls it took.
    """
    text = strip_instructions(page.text)
    sents = [x for x in SENTENCE.split(text) if x.strip()]
    readings = reader.read(sents)
    if stats is not None:
        stats["sentences"] += len(readings)
        stats["unsure"] += sum(r.confidence < reader.min_confidence for r in readings)
        stats["novel"] += sum(r.novelty > reader.max_novelty for r in readings)
        for r in readings:
            stats["confidence_hist"][min(int(r.confidence * 10), 9)] += 1
    calls = 0
    unresolved = False

    def stance(i: int, question: str) -> str | None:
        nonlocal calls, unresolved
        r = readings[i]
        if r.confidence >= reader.min_confidence:
            return r.label
        k = cache.key(sents[i]) if cache else None
        if cache and k in cache.answers:
            label = cache.answers[k]
        elif ask is None:
            label = None
        else:
            # an answer is reused on every page that says the same thing, so it is bought with two readings that
            # must agree; when they do not, a person decides
            first, second = ask(sents[i], question), ask(sents[i], f"{question} (second reading)")
            calls += 2
            label = first if first == second else None
            if cache:
                cache.answers[k] = label
                cache.asked += 1
        if label is None:
            unresolved = True
        return label

    lower = [x.lower() for x in sents]
    about = lambda words: [i for i, x in enumerate(lower) if any(w in x for w in words)]  # noqa: E731
    reasons: list[str] = []
    needs_review = False

    proc = about(PROCESSES[req.process])
    proc_stances = [stance(i, "process") for i in proc]
    if not proc:
        reasons.append(f"process {req.process} not on the page")
    elif "PROC_OFF" in proc_stances:
        reasons.append(f"page says {req.process} is no longer offered")
    elif "PROC_ON" not in proc_stances:
        needs_review = True
    if req.material not in materials_on(text):
        reasons.append(f"material {req.material} not on the page")
    for cert in req.certs:
        idx = about(CERTS[cert])
        st = [stance(i, f"certificate {cert}") for i in idx]
        if not idx:
            reasons.append(f"{cert} not on the page")
        elif "CERT_OFF" in st:
            reasons.append(f"{cert}: the page says it lapsed")
        elif "CERT_ON" not in st:
            if None in st:
                needs_review = True
            else:
                reasons.append(f"{cert}: named, but not held by this company")
    if req.manufacturer_only:
        st = [r.label if r.confidence >= reader.min_confidence else None for r in readings]
        if "TRADES" in st:
            reasons.append("not a manufacturer")
        else:
            st = [stance(i, "who makes the parts") if s is None else s for i, s in enumerate(st)]
            if "TRADES" in st:
                reasons.append("not a manufacturer")
            elif "MAKES" not in st:
                needs_review = True
    if req.region and page.country not in req.region:
        reasons.append(f"located in {page.country}, outside the region")
    if req.min_capacity:
        if page.capacity is None:
            needs_review = True
        elif page.capacity < req.min_capacity:
            reasons.append(f"capacity {page.capacity:,} below {req.min_capacity:,}")
    needs_review = (needs_review or unresolved) and not reasons
    fit = 0.0 if reasons else 1.0 + (min(page.capacity or 0, 4 * req.min_capacity) / max(req.min_capacity, 1)) / 10
    verdict = Verdict(
        supplier_id=page.supplier_id,
        name=page.name,
        qualified=not reasons and not needs_review,
        reasons=reasons or (["a deciding sentence is unclear, or capacity is not stated"] if needs_review else []),
        needs_review=needs_review,
        fit=round(fit, 4),
    )
    return verdict, calls
