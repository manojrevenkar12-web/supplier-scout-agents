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


def mentions(text: str, words: list[str]) -> int:
    t = text.lower()
    return min((t.find(w) for w in words if w in t), default=-1)


SENTENCE = re.compile(r"(?<=[.!?])\s+")


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
