"""DefectSignal — per-beat 편집 결함/성과 신호 (Metis → Artemis editorial loop, 2026-07-05).

per-reel FeedbackSignal(Metis→Janus/Ares, 창작 seed)과 달리 **beat_index 단위**의 편집 신호다.
Artemis 화룡점정 오케스트레이터가 소비해 다음 릴의 editorial_hint(페이싱/컷/컬러 조정)를 만든다.
해자=성과→편집 피드백 루프. 잡음 방지 위해 confidence≥0.75(2+ 데이터포인트·동일 처리)만 학습 반영.

grounding: sGTM(3초 시청·CTR·전환)→BigQuery per-beat 집계→DefectSignal. Artemis가 과거 결함/
자동보정과 merge해 editorial_hint 산출('narrator 클로즈업 저성과 → B롤 다양성 or 모션 강화').
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DefectSignal:
    """per-beat 편집 결함/성과 신호. Artemis editorial_hint의 입력."""

    run_id: str
    beat_index: int
    metric: str               # ctr | watch3s | roas | drop_off | retention
    value: float
    arc_pct: float = 0.0       # 0~1 감정 곡선 위치(페이싱 결정에 사용)
    treatment: str = ""        # 시각 처리 태그(narrator_closeup·broll·proof_card·product_shot)
    hint: str = ""             # editorial_hint (다음 릴 조정 문구)
    confidence: float = 0.0    # signal_confidence — 학습 반영 게이트

    # 클래스 상수(dataclass 필드 아님 — 어노테이션 없음)
    ALLOWED_METRICS = ("ctr", "watch3s", "roas", "drop_off", "retention")
    CONFIDENCE_THRESHOLD = 0.75

    def validate(self) -> list[str]:
        errs: list[str] = []
        if not self.run_id:
            errs.append("run_id 필수")
        if self.beat_index < 0:
            errs.append(f"beat_index 음수: {self.beat_index}")
        if self.metric not in self.ALLOWED_METRICS:
            errs.append(f"metric 미지원: {self.metric!r} (허용 {self.ALLOWED_METRICS})")
        if not (0.0 <= self.confidence <= 1.0):
            errs.append(f"confidence 0~1 벗어남: {self.confidence}")
        if not (0.0 <= self.arc_pct <= 1.0):
            errs.append(f"arc_pct 0~1 벗어남: {self.arc_pct}")
        return errs

    @property
    def actionable(self) -> bool:
        """학습 루프에 반영할 만큼 신뢰도 충분한가(잡음 방지 게이트)."""
        return self.confidence >= self.CONFIDENCE_THRESHOLD and not self.validate()

    @classmethod
    def from_dict(cls, d: dict) -> "DefectSignal":
        return cls(
            run_id=str(d.get("run_id", "")),
            beat_index=int(d.get("beat_index", 0) or 0),
            metric=str(d.get("metric", "")),
            value=float(d.get("value", 0.0) or 0.0),
            arc_pct=float(d.get("arc_pct", 0.0) or 0.0),
            treatment=str(d.get("treatment", "") or ""),
            hint=str(d.get("hint", "") or ""),
            confidence=float(d.get("confidence", 0.0) or 0.0),
        )
