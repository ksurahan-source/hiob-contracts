"""KlingVideo — 여성 아바타 입술싱크 계약 (Athena → Hephaestus).

역할: Kling 모델 생성 여성 주연 아바타 영상. BeatPlan.voice_concept + emotion 기반
입술싱크 생성. beat_index 결박 필수(비트 정렬).

grounding: beat.voice_concept(female1/female2) + beat.emotion(六道)
→ Kling API → KlingVideo 배열 → Remotion timeline 삽입.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Literal


@dataclass(frozen=True)
class KlingVideo:
    """Kling 모델 생성 여성 아바타 영상."""
    beat_index: int                        # 비트 결박 필수(정렬 앵커)
    style: Literal["photoreal", "cute_illustration"]  # 비주얼 스타일
    script_line: str                       # 발화 텍스트(Kling에 전달)
    emotion: Optional[str] = None          # 六道 감정 context
    duration_ms: Optional[int] = None      # 영상 길이
    url: Optional[str] = None              # 공개/서명 URL
    storage_key: Optional[str] = None      # R2 키(durable 참조)
    lip_sync_confidence: Optional[float] = None  # 0-1 입술싱크 신뢰도

    def validate(self) -> list[str]:
        """KlingVideo 완전성 검증."""
        errs: list[str] = []
        if self.beat_index is None:
            errs.append("beat_index 없음 (비트 결박 필수)")
        if not self.script_line or not self.script_line.strip():
            errs.append("script_line 빈 문자열 (발화 필수)")
        if self.style not in ("photoreal", "cute_illustration"):
            errs.append(f"style 미지원: {self.style}")
        if not (self.url or self.storage_key):
            errs.append("url/storage_key 둘 다 없음 (재생 불가)")
        if self.lip_sync_confidence is not None and not (0 <= self.lip_sync_confidence <= 1):
            errs.append(f"lip_sync_confidence 범위 오류: {self.lip_sync_confidence}")
        return errs

    @classmethod
    def from_dict(cls, d: dict) -> "KlingVideo":
        """dict → KlingVideo."""
        return cls(
            beat_index=int(d["beat_index"]),
            style=d.get("style") or "photoreal",
            script_line=d.get("script_line") or "",
            emotion=d.get("emotion") or d.get("realm"),
            duration_ms=d.get("duration_ms"),
            url=d.get("url"),
            storage_key=d.get("storage_key"),
            lip_sync_confidence=d.get("lip_sync_confidence"),
        )

    def to_dict(self) -> dict:
        """KlingVideo → dict."""
        return asdict(self)
