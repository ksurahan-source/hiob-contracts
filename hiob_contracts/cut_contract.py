"""ARTEMIS 리듬 계약 (2026-07-02, D-43 제3조).

Artemis 리듬 엔진(A1)이 산출하고 에디터 제안 카드(A2)가 소비하는 타입의 단일 진실.
원칙: 제안은 타임라인(진실)을 절대 직접 쓰지 않는다 — 사람이 적용해야만 클립 PATCH.

혈통: apps/autocut/worker/autocut/models.py 의 CutSegment/CutList(독립 오토컷)와
같은 어휘를 쓰되, 릴 파이프에서는 clip_id 기준 제안으로 표현한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# 제안 종류 — MECE
SUGGESTION_KINDS = (
    "snap_word",      # 컷 경계를 단어 경계로 스냅 (Orpheus word 타이밍)
    "snap_beat",      # 컷 경계를 BGM 비트로 스냅 (Apollo bpm 그리드)
    "split_long",     # 긴 비트 분할 제안 (구 렌더 서브샷의 정식 자리)
    "trim_silence",   # 침묵 트림 (업로드/생성 영상)
    "pace",           # 전체 리듬 조정 (예: 훅 구간 압축)
)


@dataclass
class ClipEdit:
    """단일 클립에 대한 원자 제안 — 적용하면 그대로 PATCH 필드가 된다."""

    clip_id: str = ""
    start_ms: Optional[int] = None      # None = 변경 없음
    duration_ms: Optional[int] = None
    in_ms: Optional[int] = None
    split_at_ms: Optional[int] = None   # 있으면 분할 제안 (POST /api/clips/[id]/split)

    def to_patch(self) -> dict:
        out: dict = {}
        if self.start_ms is not None:
            out["start_ms"] = int(self.start_ms)
        if self.duration_ms is not None:
            out["duration_ms"] = int(self.duration_ms)
        if self.in_ms is not None:
            out["in_ms"] = int(self.in_ms)
        return out


@dataclass
class RhythmSuggestion:
    """에디터 제안 카드 1장 — 사람이 읽고 판단할 수 있어야 한다."""

    id: str = ""                        # 안정 식별자 (run 내 유니크)
    kind: str = ""                      # SUGGESTION_KINDS
    title: str = ""                     # 카드 제목 (예: "비트3 컷을 단어 경계로 -120ms")
    reason: str = ""                    # 왜 — 근거 데이터 인용
    delta_ms: int = 0                   # 대표 이동량 (미리보기용)
    edits: list = field(default_factory=list)  # list[ClipEdit]
    confidence: float = 0.5             # 0~1 — 정렬 근거 강도

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "RhythmSuggestion":
        d = d or {}
        edits = [
            ClipEdit(
                clip_id=str(e.get("clip_id") or ""),
                start_ms=e.get("start_ms"),
                duration_ms=e.get("duration_ms"),
                in_ms=e.get("in_ms"),
                split_at_ms=e.get("split_at_ms"),
            )
            for e in (d.get("edits") or [])
            if isinstance(e, dict)
        ]
        return cls(
            id=str(d.get("id") or ""),
            kind=str(d.get("kind") or ""),
            title=str(d.get("title") or ""),
            reason=str(d.get("reason") or ""),
            delta_ms=int(d.get("delta_ms") or 0),
            edits=edits,
            confidence=float(d.get("confidence") or 0.5),
        )
