"""ReelMetric — 측정 계약 (Metis). 성과 → 창작 피드백 루프(해자).

grounding: reel_metrics(brand_slug, run_id, source, metric_date, utm_content,
impressions, clicks, spend_krw, thruplays, leads, purchases, revenue_krw).
roas/ctr는 파생. 라이브러리·인테이크가 소비(과거 승자 훅을 brief에 seed).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass(frozen=True)
class ReelMetric:
    brand_slug: str
    run_id: str
    source: str = "meta"
    metric_date: Optional[str] = None
    utm_content: Optional[str] = None
    impressions: int = 0
    clicks: int = 0
    spend_krw: float = 0.0
    thruplays: int = 0
    leads: int = 0
    purchases: int = 0
    revenue_krw: float = 0.0

    @property
    def roas(self) -> Optional[float]:
        if self.spend_krw <= 0:
            return None
        return round(self.revenue_krw / self.spend_krw, 3)

    @property
    def ctr(self) -> Optional[float]:
        if self.impressions <= 0:
            return None
        return round(self.clicks / self.impressions, 4)

    def validate(self) -> list[str]:
        errs: list[str] = []
        if not self.brand_slug:
            errs.append("brand_slug 없음")
        if not self.run_id:
            errs.append("run_id 없음")
        # 인과 날조 금지: 데이터 없이 ROAS 주장 불가 (spend 0 → roas None)
        return errs

    @classmethod
    def from_row(cls, row: dict) -> "ReelMetric":
        return cls(
            brand_slug=row.get("brand_slug", ""),
            run_id=row.get("run_id", ""),
            source=row.get("source", "meta"),
            metric_date=str(row["metric_date"]) if row.get("metric_date") else None,
            utm_content=row.get("utm_content"),
            impressions=int(row.get("impressions", 0)),
            clicks=int(row.get("clicks", 0)),
            spend_krw=float(row.get("spend_krw", 0) or 0),
            thruplays=int(row.get("thruplays", 0)),
            leads=int(row.get("leads", 0)),
            purchases=int(row.get("purchases", 0)),
            revenue_krw=float(row.get("revenue_krw", 0) or 0),
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "ReelMetric":
        """dict → ReelMetric (envelope_validation alias of from_row)."""
        return cls.from_row(d or {})
