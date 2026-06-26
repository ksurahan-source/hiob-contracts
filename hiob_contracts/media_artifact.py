"""MediaArtifact — 시각 계약 (Athena). 비트별 이미지/영상.

grounding: artifact(storage_key, mime, duration_ms, width, height) + slot(beat_index).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Literal

MediaKind = Literal["still", "video", "avatar", "carousel"]


@dataclass(frozen=True)
class MediaArtifact:
    kind: MediaKind
    beat_index: int                    # 비트 결박 (정렬·다양성의 앵커)
    url: Optional[str] = None
    storage_key: Optional[str] = None
    duration_ms: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    mime: Optional[str] = None
    style: Optional[str] = None         # photoreal | cute_illustration

    def validate(self) -> list[str]:
        errs: list[str] = []
        if self.kind not in ("still", "video", "avatar", "carousel"):
            errs.append(f"kind 미지원: {self.kind}")
        if self.beat_index is None:
            errs.append("beat_index 없음")
        if not (self.url or self.storage_key):
            errs.append("url/storage_key 없음")
        return errs

    @classmethod
    def from_slot_artifact(cls, slot: dict, artifact: Optional[dict]) -> "MediaArtifact":
        artifact = artifact or {}
        mime = artifact.get("mime") or ""
        kind: MediaKind = "video" if mime.startswith("video") else "still"
        attrs = artifact.get("attributes") or {}
        return cls(
            kind=attrs.get("kind") or kind,
            beat_index=slot.get("beat_index"),
            url=artifact.get("url"),
            storage_key=artifact.get("storage_key"),
            duration_ms=artifact.get("duration_ms"),
            width=artifact.get("width"),
            height=artifact.get("height"),
            mime=mime or None,
            style=attrs.get("style") or attrs.get("persona_visual_style"),
        )

    def to_dict(self) -> dict:
        return asdict(self)
