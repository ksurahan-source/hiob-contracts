"""AudioClip — 청각 계약 (Orpheus voice/music, Apollo sfx).

★ P1 봉쇄: voice·sfx 클립은 beat_index 결박이 *필수*. 계약이 강제하므로
"비트에 안 붙어 침묵"(어젯밤 음소거 슬라이드쇼)이 구조적으로 불가능해진다.
grounding: slot(track∈{voiceover,sfx,music}, beat_index) + artifact(duration_ms, storage_key).
music은 run-level 허용(slot.beat_index nullable).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Literal

Track = Literal["voice", "sfx", "music"]
# slot.track 어휘 ↔ 계약 track 정규화
_TRACK_ALIASES = {"voiceover": "voice", "voice": "voice", "sfx": "sfx", "music": "music"}


@dataclass(frozen=True)
class AudioClip:
    track: Track
    beat_index: Optional[int]          # voice/sfx=필수, music=run-level 허용
    url: Optional[str] = None          # 공개/서명 URL
    storage_key: Optional[str] = None  # R2 키 (durable 참조)
    duration_ms: Optional[int] = None
    voice_concept: Optional[str] = None
    affinity: Optional[str] = None     # 六道 affinity 등

    def validate(self) -> list[str]:
        errs: list[str] = []
        if self.track not in ("voice", "sfx", "music"):
            errs.append(f"track 미지원: {self.track}")
        # ★ P1: beat 결박 트랙은 beat_index 없으면 거부
        if self.track in ("voice", "sfx") and self.beat_index is None:
            errs.append(f"{self.track} 클립에 beat_index 없음 (P1 침묵 위험)")
        if not (self.url or self.storage_key):
            errs.append("url/storage_key 둘 다 없음 (재생 불가)")
        return errs

    @classmethod
    def from_slot_artifact(cls, slot: dict, artifact: Optional[dict]) -> "AudioClip":
        """slot row + 그 current artifact row → AudioClip (실 DB 모델 매핑)."""
        artifact = artifact or {}
        return cls(
            track=_TRACK_ALIASES.get(slot.get("track", ""), slot.get("track", "")),  # type: ignore
            beat_index=slot.get("beat_index"),
            url=artifact.get("url"),
            storage_key=artifact.get("storage_key"),
            duration_ms=artifact.get("duration_ms"),
            voice_concept=(artifact.get("attributes") or {}).get("voice_concept"),
            affinity=(artifact.get("attributes") or {}).get("affinity"),
        )

    def to_dict(self) -> dict:
        return asdict(self)
