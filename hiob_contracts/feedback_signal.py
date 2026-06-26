"""FeedbackSignal — 측정 루프 피드백 계약 (Metis → Janus/Ares).

역할: ROAS 기반 창작 피드백 신호. ReelMetric(BigQuery) → FeedbackSignal 변환.
Janus/Ares가 다음 brief/script seed에 학습된 제약조건 반영.

grounding: ReelMetric(run_id, roas, ctr) → BigQuery 일배치 → FeedbackSignal 생산.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass(frozen=True)
class FeedbackSignal:
    """ROAS 기반 창작 피드백 신호."""
    run_id: str                            # 릴 식별자
    metric_date: str                       # YYYY-MM-DD (측정 기준일)
    roas: float                            # ReelMetric에서 파생 (₩ spent → revenue)
    ctr: float                             # 클릭율
    learned_constraints: dict = field(default_factory=dict)  # 다음 brief seed

    # 예: {
    #   "hook_emotion": "urgency",       # 가장 효율 높은 감정
    #   "tone_preference": "direct",     # 권장 톤
    #   "product_category": "wellness",  # 제품군 친화도
    #   "demographic_affinity": "female_20s",  # 오디언스 추정
    # }
    # Janus가 request_interpretation seed로 사용
    # Ares가 BeatPlan.emotion 선택에 반영

    spend_krw: Optional[float] = None      # Meta 광고비 (검증용)
    impressions: Optional[int] = None      # 노출수
    conversions: Optional[int] = None      # 전환수

    def validate(self) -> list[str]:
        """FeedbackSignal 완전성 검증."""
        import re

        errs: list[str] = []
        if not self.run_id:
            errs.append("run_id 필수")
        if not self.metric_date or not re.match(r"^\d{4}-\d{2}-\d{2}$", self.metric_date):
            errs.append(f"metric_date 형식 오류 (YYYY-MM-DD): {self.metric_date}")
        if self.roas < 0:
            errs.append(f"roas < 0 (음수 불가): {self.roas}")
        if self.ctr < 0 or self.ctr > 1:
            errs.append(f"ctr 범위 오류 (0-1): {self.ctr}")
        if self.spend_krw is not None and self.spend_krw < 0:
            errs.append(f"spend_krw < 0 (음수 불가): {self.spend_krw}")
        return errs

    @classmethod
    def from_dict(cls, d: dict) -> "FeedbackSignal":
        """dict → FeedbackSignal."""
        return cls(
            run_id=d.get("run_id") or "",
            metric_date=d.get("metric_date") or "",
            roas=float(d.get("roas") or 0.0),
            ctr=float(d.get("ctr") or 0.0),
            learned_constraints=d.get("learned_constraints") or {},
            spend_krw=d.get("spend_krw"),
            impressions=d.get("impressions"),
            conversions=d.get("conversions"),
        )

    def to_dict(self) -> dict:
        """FeedbackSignal → dict."""
        return asdict(self)
