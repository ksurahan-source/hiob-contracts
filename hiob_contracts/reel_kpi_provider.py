"""ReelKpiProvider — 측정→작가 루프의 DB 결합을 역전하는 입력 계약 (2026-07-05 seam).

노드맵 start_here #5: "Metis는 72%지만 previous_run_insights가 reel_kpi 테이블을 직접
읽어 DB 결합이 역전 안 됨." 이 Protocol이 그 경계다: Metis는 Supabase 클라이언트가 아니라
`ReelKpiProvider` 인터페이스에 의존한다. 기본 어댑터(Supabase)는 그 구현체일 뿐이고,
테스트/다른 소스는 다른 구현을 주입한다. 창작-피드백 해자(ROAS→작가)가 계약-타입이 된다.

역전은 비파괴: previous_run_insights(data_provider=None) → 기존 sb.table 경로(byte-identical).
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ReelKpiProvider(Protocol):
    """ROAS 상위 릴 KPI 행을 반환하는 소스 계약. Metis가 DB 대신 이 인터페이스에 의존."""

    def fetch_reel_kpi(
        self,
        *,
        brand: str,
        product: str,
        listing: str,
        cutoff: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """brand(+선택 product/listing)의 cutoff 이후 ROAS 상위 limit개 reel_kpi 행.

        각 행 최소 키: run_id, hook_text, vertical, reel_mode, journey_archetype, roas,
        leads, last_metric_date. roas 내림차순. 없으면 []. 실제 KPI만(합성 금지·표시광고법).
        """
        ...
