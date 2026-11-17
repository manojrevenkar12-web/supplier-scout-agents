"""The data the agents pass around. Supplier pages are data, never instructions."""

from __future__ import annotations

from pydantic import BaseModel, Field

# What one sentence on a supplier page can say. The reader predicts these; the world labels its sentences with them.
STANCES = ["MAKES", "TRADES", "PROC_ON", "PROC_OFF", "CERT_ON", "CERT_OFF", "CERT_OTHERS", "INSTRUCTION", "OTHER"]


class Rfq(BaseModel):
    id: str
    text: str  # what the buyer wrote


class Requirements(BaseModel):
    process: str
    material: str
    certs: list[str] = []
    region: list[str] = []  # allowed countries; empty = anywhere
    min_capacity: int = 0  # parts a year
    manufacturer_only: bool = True


class SupplierPage(BaseModel):
    supplier_id: str
    name: str
    domain: str
    country: str
    capacity: int | None = None
    text: str


class Claim(BaseModel):
    """What the model says a page supports, each with the quote it relies on."""

    process: bool = False
    material: bool = False
    certs: list[str] = []
    manufacturer: bool = True
    evidence: dict[str, str] = Field(default_factory=dict)  # field -> quote from the page
    score: float = 0.0  # the model's own ranking score; code does not rank by it


class Verdict(BaseModel):
    supplier_id: str
    name: str
    qualified: bool
    reasons: list[str] = []  # why not, or what a person should look at
    needs_review: bool = False
    fit: float = 0.0
