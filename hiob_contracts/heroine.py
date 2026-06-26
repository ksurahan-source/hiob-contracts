"""Heroine — 여성 주연 캐스팅 계약 (Janus → 전 하위 행성).

역할: 여성 주연 메타데이터 + 시각/음성 일관성 앵커. 3역할 Campbell archetype
(everyman=진정한 영웅, mentor=언니 가이드, witness=목격자 여성) 선택.
모든 하위 행성이 Heroine을 읽고 일관된 캐스팅 유지.

grounding: brief.protagonist=여 → 1개 Heroine 객체 반환.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal, Optional


HeroineArchetype = Literal["everywoman", "mentor", "witness"]


@dataclass(frozen=True)
class Heroine:
    """여성 주연 캐스팅 + 비주얼/목소리 일관성."""
    brief_protagonist: str                 # brief.protagonist (남/여/everyman)
    visual_archetype: HeroineArchetype     # 3역할 Campbell
    voice_concept: str                     # Orpheus slot (female1/female2)
    visual_style: Literal["photoreal", "cute_illustration"]  # 비주얼 스타일
    locale: str                            # "ko" | "en" (발음규칙)
    age_range: Optional[str] = None        # "20s" | "30s" | "40s+" (시각가이드)
    name: Optional[str] = None             # 캐스팅 이름

    def validate(self) -> list[str]:
        """Heroine 완전성 검증."""
        errs: list[str] = []
        if self.brief_protagonist != "여":
            errs.append(f"non-female protagonist 시도 (Heroine은 여성만): {self.brief_protagonist}")
        if self.visual_archetype not in ("everywoman", "mentor", "witness"):
            errs.append(f"미지원 archetype: {self.visual_archetype}")
        if self.voice_concept not in ("female1", "female2"):
            errs.append(f"미지원 voice_concept: {self.voice_concept}")
        if self.visual_style not in ("photoreal", "cute_illustration"):
            errs.append(f"미지원 visual_style: {self.visual_style}")
        if self.locale not in ("ko", "en"):
            errs.append(f"미지원 locale: {self.locale}")
        return errs

    @classmethod
    def from_dict(cls, d: dict) -> "Heroine":
        """dict → Heroine."""
        return cls(
            brief_protagonist=d.get("brief_protagonist") or "여",
            visual_archetype=d.get("visual_archetype") or "everywoman",
            voice_concept=d.get("voice_concept") or "female1",
            visual_style=d.get("visual_style") or "photoreal",
            locale=d.get("locale") or "ko",
            age_range=d.get("age_range"),
            name=d.get("name"),
        )

    def to_dict(self) -> dict:
        """Heroine → dict."""
        return asdict(self)
