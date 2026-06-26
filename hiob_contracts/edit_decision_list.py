"""EditDecisionList — 편집 계약 (Artemis). 비트별 컷·전환·자막·타이밍.

Editor가 페이싱·다양성·자막완전성을 책임 → Atropos가 그대로 렌더.
seam: ≤800ms 서브컷·N이미지 회전·전 비트 자막(P2/P13).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass(frozen=True)
class EditDecision:
    """단일 비트의 편집 결정."""
    beat_index: int
    cuts_ms: tuple[int, ...] = ()           # 서브컷 경계(비트 내 분할)
    transitions: tuple[str, ...] = ()
    captions: tuple[str, ...] = ()          # 표시 자막(전 비트 권장)
    start_ms: Optional[int] = None
    duration_ms: Optional[int] = None

    def validate(self) -> list[str]:
        errs: list[str] = []
        if self.beat_index is None:
            errs.append("beat_index 없음")
        # 페이싱 규칙: 서브컷이 있으면 ≤800ms 권장(경고는 gate에서)
        return errs


@dataclass(frozen=True)
class EditDecisionList:
    decisions: tuple[EditDecision, ...] = ()

    def validate(self) -> list[str]:
        errs: list[str] = []
        idxs = [d.beat_index for d in self.decisions]
        if len(idxs) != len(set(idxs)):
            errs.append("EditDecision beat_index 중복")
        return errs

    @classmethod
    def from_list(cls, items: list[dict]) -> "EditDecisionList":
        return cls(decisions=tuple(
            EditDecision(
                beat_index=int(d["beat_index"]),
                cuts_ms=tuple(d.get("cuts_ms") or ()),
                transitions=tuple(d.get("transitions") or ()),
                captions=tuple(d.get("captions") or ()),
                start_ms=d.get("start_ms"),
                duration_ms=d.get("duration_ms"),
            ) for d in (items or [])
        ))

    def to_dict(self) -> dict:
        return {"decisions": [asdict(d) for d in self.decisions]}
