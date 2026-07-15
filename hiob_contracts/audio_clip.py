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
    bpm: Optional[int] = None          # music tempo (optional; LP5-1)
    beat_markers: Optional[list] = None  # ms offsets or beat timestamps (optional)

    def validate(self) -> list[str]:
        errs: list[str] = []
        if self.track not in ("voice", "sfx", "music"):
            errs.append(f"track 미지원: {self.track}")
        # ★ P1: beat 결박 트랙은 beat_index 없으면 거부
        if self.track in ("voice", "sfx") and self.beat_index is None:
            errs.append(f"{self.track} 클립에 beat_index 없음 (P1 침묵 위험)")
        if not (self.url or self.storage_key):
            errs.append("url/storage_key 둘 다 없음 (재생 불가)")
        if self.bpm is not None and self.bpm <= 0:
            errs.append(f"bpm must be > 0 when set (got {self.bpm})")
        return errs

    @classmethod
    def from_slot_artifact(cls, slot: dict, artifact: Optional[dict]) -> "AudioClip":
        """slot row + 그 current artifact row → AudioClip (실 DB 모델 매핑)."""
        artifact = artifact or {}
        attrs = artifact.get("attributes") or {}
        # Prefer top-level artifact keys, fall back to attributes (DB JSONB).
        bpm = artifact.get("bpm", attrs.get("bpm"))
        beat_markers = artifact.get("beat_markers", attrs.get("beat_markers"))
        return cls(
            track=_TRACK_ALIASES.get(slot.get("track", ""), slot.get("track", "")),  # type: ignore
            beat_index=slot.get("beat_index"),
            url=artifact.get("url"),
            storage_key=artifact.get("storage_key"),
            duration_ms=artifact.get("duration_ms"),
            voice_concept=attrs.get("voice_concept"),
            affinity=attrs.get("affinity"),
            bpm=bpm,
            beat_markers=list(beat_markers) if beat_markers is not None else None,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "AudioClip":
        """dict → AudioClip (envelope_validation path; not DB slot mapping)."""
        d = d or {}
        track = d.get("track", "")
        track = _TRACK_ALIASES.get(track, track)  # type: ignore[arg-type]
        beat_markers = d.get("beat_markers")
        return cls(
            track=track,  # type: ignore[arg-type]
            beat_index=d.get("beat_index"),
            url=d.get("url"),
            storage_key=d.get("storage_key"),
            duration_ms=d.get("duration_ms"),
            voice_concept=d.get("voice_concept"),
            affinity=d.get("affinity"),
            bpm=d.get("bpm"),
            beat_markers=list(beat_markers) if beat_markers is not None else None,
        )
