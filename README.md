# hiob-contracts (발판)

행성끼리 주고받는 데이터의 **타입 계약**. 7스키마 파이프라인: JanusBrief → BeatPlan → {MediaArtifact, AudioClip} → EditDecisionList → CompositionSnapshot → ReelMetric.

## 핵심 규칙

- **P1 봉쇄**: voice/sfx AudioClip은 `beat_index` 필수 (무음 릴 방지).
- **gate 강화**: orphan clip (beat_index=None인 voice/sfx/media) 즉시 검출 → 렌더 금지.

## 구조

### Python 정전 소스
`hiob_contracts/` — Pydantic-like dataclass 계약들
- `janus_brief.py` — Intake13Q + JanusBrief
- `beat_plan.py` — Beat + BeatPlan
- `audio_clip.py` — AudioClip (P1 결박)
- `media_artifact.py` — MediaArtifact
- `edit_decision_list.py` — EditDecision + EditDecisionList
- `composition_snapshot.py` — CompositionSnapshot
- `reel_metric.py` — ReelMetric
- `gate.py` — RenderReadiness + assert_render_ready() (강화됨)

### TypeScript 미러
`ts/` — Zod schema (선언문서만 제공)
- `src/janus-brief.ts` ↔ `janus_brief.py`
- `src/beat-plan.ts` ↔ `beat_plan.py`
- `src/audio-clip.ts` ↔ `audio_clip.py`
- `src/media-artifact.ts` ↔ `media_artifact.py`
- `src/edit-decision-list.ts` ↔ `edit_decision_list.py`
- `src/composition-snapshot.ts` ↔ `composition_snapshot.py`
- `src/reel-metric.ts` ↔ `reel_metric.py`
- `src/gate.ts` ↔ `gate.py` (강화됨)

**⚠️ Authority**: Python 정전 소스. TypeScript는 미러일 뿐.
모든 필드·유효성·부재값 동작이 일치해야 함. 차이 발생 시 Python을 정답으로 간주.

## 설치 & 테스트

### Python
```bash
pip install -e .
pytest tests/test_contracts.py -v
```

### TypeScript
```bash
cd ts/
npm install
npm run build
npm test  # (진행 중)
```

## 사용

### Python
```python
from hiob_contracts import JanusBrief, BeatPlan, AudioClip, assert_render_ready

brief = JanusBrief(brand_slug="viewok", ...)
plan = BeatPlan.from_list([...])
audio = [AudioClip(track="voice", beat_index=0, url="..."), ...]
result = assert_render_ready(plan, audio, media)
assert result.ok, result.violations
```

### TypeScript
```typescript
import { JanusBriefSchema, BeatPlanSchema, assertRenderReady } from '@hiob/contracts';

const brief = JanusBriefSchema.parse(briefData);
const plan = BeatPlanSchema.parse(planData);
const readiness = assertRenderReady(plan, audio, media);
if (!readiness.ok) {
  throw new Error(`Render blocked: ${readiness.violations.join(', ')}`);
}
```

## 의존

- Python: stdlib only
- TypeScript: `zod` (runtime validation)
