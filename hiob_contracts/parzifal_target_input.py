"""ParzifalTargetInput — Karma-refined target input for Parzifal (j2p edge).

This is the canonical target_input schema that Karma produces when refining
JanusBrief for Parzifal's parzifal.target.consolidate node. Parzifal consumes
this as the refined evidence to drive target/identity derivation.

PRD §6.2–§6.3: the receipt carries this as a canonical JSON object, bound by
target_input_digest. The digest byte-parity is maintained across Python↔TS.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass(frozen=True)
class ParzifalTargetInput:
    """Karma-refined target input for Parzifal consolidation (j2p edge receipt).

    Refined from JanusBrief by Karma's j2p policy. Fields are:
    - Brand facts (from Intake 13Q)
    - Customer/target facts
    - VoC evidence (real voices of customer)
    - Grounding context (what product/listing to anchor to)

    All fields are Optional — Karma refines what it can; missing ≠ error.
    """

    # Brand identity (from Intake 13Q)
    brand_slug: str
    brand_identity: Optional[str] = None
    brand_usp: Optional[str] = None
    brand_voice_tone: Optional[str] = None
    brand_regulation: Optional[str] = None
    brand_price: Optional[str] = None
    brand_history: Optional[str] = None

    # Target / Customer (from Intake 13Q)
    target_audience: Optional[str] = None
    target_jtbd: Optional[str] = None
    target_pain: Optional[str] = None
    target_blocker: Optional[str] = None
    target_price_sensitivity: Optional[str] = None
    target_objection: Optional[str] = None

    # VoC evidence (real voices, derived from Intake + external research)
    voc_core_pain: Optional[str] = None
    voc_real_reviews: list[str] = field(default_factory=list)
    voc_evidence_source: Optional[str] = None

    # Grounding (product/listing anchor)
    product_slug: Optional[str] = None
    listing_slug: Optional[str] = None
    listing_url: Optional[str] = None

    # Format hints (from JanusBrief orthogonal axes)
    locale: str = "ko"
    vertical_mode: Optional[str] = None
    protagonist: Optional[str] = None  # male | female | everyman
    style: Optional[str] = None  # photoreal | cute_illustration
    reel_mode: Optional[str] = None

    def validate(self) -> list[str]:
        """Completeness check. Parzifal expects brand_slug + at least one target fact."""
        errs: list[str] = []
        if not self.brand_slug:
            errs.append("ParzifalTargetInput.brand_slug 필수")
        # At least one target fact should be present
        target_facts = (
            self.target_audience, self.target_jtbd, self.target_pain,
            self.target_blocker, self.voc_core_pain
        )
        if not any(target_facts):
            errs.append("ParzifalTargetInput: 최소 1개의 target fact 필요 (audience/jtbd/pain/blocker/voc_core_pain)")
        return errs

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "ParzifalTargetInput":
        """Construct from a dict (e.g., Karma's target_input JSON)."""
        d = d or {}
        return cls(
            brand_slug=str(d.get("brand_slug") or ""),
            brand_identity=d.get("brand_identity"),
            brand_usp=d.get("brand_usp"),
            brand_voice_tone=d.get("brand_voice_tone"),
            brand_regulation=d.get("brand_regulation"),
            brand_price=d.get("brand_price"),
            brand_history=d.get("brand_history"),
            target_audience=d.get("target_audience"),
            target_jtbd=d.get("target_jtbd"),
            target_pain=d.get("target_pain"),
            target_blocker=d.get("target_blocker"),
            target_price_sensitivity=d.get("target_price_sensitivity"),
            target_objection=d.get("target_objection"),
            voc_core_pain=d.get("voc_core_pain"),
            voc_real_reviews=d.get("voc_real_reviews", []),
            voc_evidence_source=d.get("voc_evidence_source"),
            product_slug=d.get("product_slug"),
            listing_slug=d.get("listing_slug"),
            listing_url=d.get("listing_url"),
            locale=str(d.get("locale") or "ko"),
            vertical_mode=d.get("vertical_mode"),
            protagonist=d.get("protagonist"),
            style=d.get("style"),
            reel_mode=d.get("reel_mode"),
        )
