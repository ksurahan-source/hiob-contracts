"""AresScriptInput — Karma-refined target input for Ares (p2a edge).

This is the canonical target_input schema that Karma produces when refining
Parzifal's outputs (TargetProfile + IdentityLock + CastSheet) for Ares's
ares.script.build node. Ares consumes this as the validated, refined input
to drive script generation.

PRD §6.2–§6.3: the receipt carries this as a canonical JSON object, bound by
target_input_digest. The digest byte-parity is maintained across Python↔TS.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass(frozen=True)
class AresScriptInput:
    """Karma-refined target input for Ares script building (p2a edge receipt).

    Refined from Parzifal outputs (TargetProfile, IdentityLock, CastSheet) by
    Karma's p2a policy. Fields include:
    - Brand facts (immutable identity from Parzifal)
    - Target/protagonist facts (identity + persona derived by Parzifal)
    - VoC evidence (grounding for script claims)
    - Grounding context (product/listing)

    All fields are Optional — Karma refines what it can; missing ≠ error.
    Ares interprets missing fields as fallback to template/cached persona.
    """

    # Brand identity (from Parzifal TargetProfile)
    brand_slug: str
    brand_identity: Optional[str] = None
    brand_usp: Optional[str] = None
    brand_voice_tone: Optional[str] = None
    brand_regulation: Optional[str] = None

    # Protagonist/Target (from Parzifal IdentityLock + CastSheet)
    protagonist_id: Optional[str] = None
    protagonist_name: Optional[str] = None
    protagonist_age: Optional[int] = None
    protagonist_age_band: Optional[str] = None
    protagonist_gender: Optional[str] = None
    protagonist_region: Optional[str] = None
    protagonist_role: Optional[str] = None  # customer | expert | narrator etc.
    protagonist_voice_persona: Optional[str] = None

    # Target facts (pain, motivation, context)
    target_pain: Optional[str] = None
    target_jtbd: Optional[str] = None
    target_context: Optional[str] = None
    target_blocker: Optional[str] = None
    target_objection: Optional[str] = None

    # VoC evidence (real voice of customer for script grounding)
    voc_real_quotes: list[str] = field(default_factory=list)
    voc_core_pain: Optional[str] = None

    # Grounding (product/listing)
    product_slug: Optional[str] = None
    listing_slug: Optional[str] = None
    listing_pitch: Optional[str] = None

    # Format hints
    locale: str = "ko"
    style: Optional[str] = None  # photoreal | cute_illustration
    reel_mode: Optional[str] = None

    def validate(self) -> list[str]:
        """Completeness check. Ares expects brand_slug + protagonist_name + at least one VoC fact."""
        errs: list[str] = []
        if not self.brand_slug:
            errs.append("AresScriptInput.brand_slug 필수")
        if not self.protagonist_name:
            errs.append("AresScriptInput.protagonist_name 필수 (casting anchor)")
        # At least one VoC or pain fact
        grounding_facts = (self.voc_core_pain, self.target_pain, self.target_jtbd)
        if not any(grounding_facts):
            errs.append("AresScriptInput: 최소 1개의 grounding fact 필요 (pain/jtbd/voc_core_pain)")
        return errs

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "AresScriptInput":
        """Construct from a dict (e.g., Karma's target_input JSON)."""
        d = d or {}
        return cls(
            brand_slug=str(d.get("brand_slug") or ""),
            brand_identity=d.get("brand_identity"),
            brand_usp=d.get("brand_usp"),
            brand_voice_tone=d.get("brand_voice_tone"),
            brand_regulation=d.get("brand_regulation"),
            protagonist_id=d.get("protagonist_id"),
            protagonist_name=d.get("protagonist_name"),
            protagonist_age=int(d["protagonist_age"]) if d.get("protagonist_age") is not None else None,
            protagonist_age_band=d.get("protagonist_age_band"),
            protagonist_gender=d.get("protagonist_gender"),
            protagonist_region=d.get("protagonist_region"),
            protagonist_role=d.get("protagonist_role"),
            protagonist_voice_persona=d.get("protagonist_voice_persona"),
            target_pain=d.get("target_pain"),
            target_jtbd=d.get("target_jtbd"),
            target_context=d.get("target_context"),
            target_blocker=d.get("target_blocker"),
            target_objection=d.get("target_objection"),
            voc_real_quotes=d.get("voc_real_quotes", []),
            voc_core_pain=d.get("voc_core_pain"),
            product_slug=d.get("product_slug"),
            listing_slug=d.get("listing_slug"),
            listing_pitch=d.get("listing_pitch"),
            locale=str(d.get("locale") or "ko"),
            style=d.get("style"),
            reel_mode=d.get("reel_mode"),
        )
