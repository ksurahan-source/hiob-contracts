"""JanusBrief — 인테이크 계약 (Janus → 전 행성의 단일 입력).

grounding: route.js campaign-reels 13Q(identity..proof) + brief 직교축
(locale/vertical_mode/protagonist/style/reel_mode). 부재 필드 = None 폴백.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass(frozen=True)
class Intake13Q:
    """세일즈 인테이크 13문항 (Brand 6 + Customer 7). 전부 선택 — 부재=폴백."""
    # Brand 6
    identity: Optional[str] = None
    usp: Optional[str] = None
    voice_tone: Optional[str] = None
    regulation: Optional[str] = None
    price: Optional[str] = None
    history: Optional[str] = None
    # Customer 7
    audience: Optional[str] = None
    jtbd: Optional[str] = None
    pain: Optional[str] = None
    blocker: Optional[str] = None
    price_sensitivity: Optional[str] = None
    objection: Optional[str] = None
    proof: Optional[str] = None

    FIELDS = (
        "identity", "usp", "voice_tone", "regulation", "price", "history",
        "audience", "jtbd", "pain", "blocker", "price_sensitivity", "objection", "proof",
    )

    @property
    def answered_count(self) -> int:
        return sum(1 for f in self.FIELDS if (getattr(self, f) or "").strip())

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "Intake13Q":
        d = d or {}
        return cls(**{f: d.get(f) for f in cls.FIELDS})


@dataclass(frozen=True)
class JanusBrief:
    """Janus가 생산하는 단일 입력 객체. 모든 하위 행성이 변형 없이 소비한다."""
    brand_slug: str
    intake: Intake13Q = field(default_factory=Intake13Q)
    # 직교축 (새 축 만들지 말고 데이터로 — 부재=byte-identical 폴백)
    locale: str = "ko"
    vertical_mode: Optional[str] = None
    protagonist: Optional[str] = None          # 남/여/everyman 등
    style: Optional[str] = None                 # photoreal | cute_illustration
    reel_mode: Optional[str] = None             # PROOF | SERIES | None(legacy)
    # 제품/리스팅 그라운딩 (1층 = 캠페인: 무엇을 광고하나)
    product: Optional[str] = None
    listing_slug: Optional[str] = None
    source_url: Optional[str] = None            # URL 출처 보존(스키마 경계에서 유실 방지)
    request_text: Optional[str] = None
    request_interpretation: dict = field(default_factory=dict)
    # VoC (2층 = 광고 소재: 어떻게 말하나 — 리스팅별 진짜 후기·페인, Ares가 소비)
    # shape: {source_url, core_pain, target_audience, pain_points[], real_reviews[], brand_identity{}}
    voc: dict = field(default_factory=dict)

    def validate(self) -> list[str]:
        """완전성 점검. Janus의 책임 = brief의 완전성·일관성."""
        errs: list[str] = []
        if not self.brand_slug:
            errs.append("brand_slug 필수")
        if self.style and self.style not in ("photoreal", "cute_illustration"):
            errs.append(f"style 미지원: {self.style}")
        return errs

    @classmethod
    def from_dict(cls, d: dict) -> "JanusBrief":
        d = dict(d or {})
        return cls(
            brand_slug=d.get("brand_slug") or d.get("brand") or "",
            intake=Intake13Q.from_dict(d.get("intake") or d.get("intake_answers") or d),
            locale=d.get("locale", "ko"),
            vertical_mode=d.get("vertical_mode"),
            protagonist=d.get("protagonist"),
            style=d.get("style") or d.get("persona_visual_style"),
            reel_mode=d.get("reel_mode"),
            product=d.get("product"),
            listing_slug=d.get("listing_slug"),
            source_url=d.get("source_url"),
            request_text=d.get("request_text"),
            request_interpretation=d.get("request_interpretation") or {},
            voc=d.get("voc") or {},
        )

    def to_dict(self) -> dict:
        return asdict(self)
