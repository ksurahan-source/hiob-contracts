"""DefectSignalProvider — Metis→Artemis per-beat 편집 피드백의 입력 계약 (2026-07-05 seam).

행성간 와이어링 감사(P2): DefectSignal 계약은 있으나 Artemis가 어디서·어떻게 로드할지
어댑터가 없어 소비 경계가 비어 있었다(좀비). ReelKpiProvider 패턴을 미러 — Artemis는
Supabase 클라이언트가 아니라 `DefectSignalProvider` 인터페이스에 의존한다. Metis가 그 구현체.

역전은 비파괴: provider=None이면 Artemis editorial_layers는 정적 임계값(BOREDOM_MS 등)만
쓴다(byte-identical). provider 주입 시 실 성과(per-beat CTR/watch3s/drop_off)로 결정을 바이어스.
Metis generate_defect_signals()가 이 인터페이스를 구현하면 루프가 닫힌다(D-57).
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DefectSignalProvider(Protocol):
    """run의 per-beat 편집 결함/성과 신호(DefectSignal dict)를 반환하는 소스 계약.

    Artemis 화룡점정 오케가 DB 대신 이 인터페이스에 의존 — Metis가 구현체를 주입.
    """

    def fetch_defect_signals(
        self,
        *,
        run_id: str,
        min_confidence: float = 0.75,
    ) -> list[dict[str, Any]]:
        """run_id의 per-beat DefectSignal 행(dict). 각 행 최소 키: run_id, beat_index, metric,
        value, arc_pct, treatment, hint, confidence. min_confidence 미만은 제외(잡음 방지).
        없으면 []. 실 측정만(합성 금지). DefectSignal.from_dict로 파싱 가능한 형태.
        """
        ...
