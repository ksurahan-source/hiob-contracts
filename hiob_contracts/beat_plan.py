"""BeatPlan — 대본 계약 (Ares). 대본이 지휘자: 각 비트가 다운스트림(보이스/
비주얼/자막/효과음)이 소비할 필드를 *모두* 선언한다.

grounding: beat dict 키 = beat_index, text, duration_ms, caption, voice_concept,
sfx(cue), role, emotion, cta. 부재=폴백.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass(frozen=True)
class Beat:
    """단일 비트. beat_index는 전 다운스트림 결박의 앵커(필수)."""
    beat_index: int
    text: str = ""                              # 발화/나레이션 라인
    emotion: Optional[str] = None               # 六道 감정 → voice/visual 선택
    shot_type: Optional[str] = None
    voice_concept: Optional[str] = None         # Orpheus 보이스 선택 입력
    sfx_cue: Optional[str] = None               # Apollo SFX 입력
    caption: Optional[str] = None               # 자막 텍스트(전 비트 권장)
    role: Optional[str] = None                  # 영웅/가이드/목격자
    duration_ms: Optional[int] = None
    cta: Optional[dict] = None                  # CTA 비트 = 가치수학 4단

    @classmethod
    def from_dict(cls, d: dict) -> "Beat":
        return cls(
            beat_index=int(d["beat_index"]),
            text=d.get("text") or d.get("line") or d.get("narration") or "",
            emotion=d.get("emotion") or d.get("realm") or d.get("six_realm"),
            shot_type=d.get("shot_type") or d.get("shot"),
            voice_concept=d.get("voice_concept"),
            sfx_cue=d.get("sfx_cue") or d.get("sfx"),
            caption=d.get("caption"),
            role=d.get("role"),
            duration_ms=d.get("duration_ms"),
            cta=d.get("cta") if isinstance(d.get("cta"), dict) else None,
        )


@dataclass(frozen=True)
class BeatPlan:
    """비트 시퀀스. 척추 = 단일 카테고리 재프레임이 훅~CTA 관통."""
    beats: tuple[Beat, ...] = ()
    spine: Optional[str] = None                 # 관통 재프레임 한 줄

    def validate(self) -> list[str]:
        errs: list[str] = []
        idxs = [b.beat_index for b in self.beats]
        if len(idxs) != len(set(idxs)):
            errs.append("beat_index 중복")
        if idxs and sorted(idxs) != list(range(min(idxs), max(idxs) + 1)):
            errs.append("beat_index 연속성 깨짐(구멍)")
        return errs

    @classmethod
    def from_list(cls, beats: list[dict], spine: Optional[str] = None) -> "BeatPlan":
        return cls(beats=tuple(Beat.from_dict(b) for b in (beats or [])), spine=spine)

    def to_dict(self) -> dict:
        return {"spine": self.spine, "beats": [asdict(b) for b in self.beats]}
