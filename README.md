# hiob-contracts (발판)
행성끼리 주고받는 데이터의 **타입 계약**. 7스키마 파이프라인: JanusBrief → BeatPlan → {MediaArtifact, AudioClip} → EditDecisionList → CompositionSnapshot → ReelMetric.
- **P1 봉쇄**: voice/sfx AudioClip은 `beat_index` 필수 (무음 릴 방지).
- 의존: 없음 (pure types). 모든 행성·발판이 이걸 import.
- 자립: stdlib only. `pip install -e . && pytest` → 35 passed.
