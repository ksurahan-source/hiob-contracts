# hiob-contracts

HIOB 행성간 **타입 계약** (Phase 0.1, D-15 폴리레포). 행성은 서로 import 하지 않고 이 계약 객체로만 협업한다.

## 계약 체인
```
JanusBrief → BeatPlan[] → {MediaArtifact, AudioClip}[] → EditDecisionList
          → CompositionSnapshot → ReelMetric
```

| 계약 | 생산 행성 | 핵심 |
|---|---|---|
| `JanusBrief` | Janus | 13Q + 직교축(locale/vertical/protagonist/style/reel_mode) |
| `BeatPlan`/`Beat` | Ares | 대본이 지휘 — 비트가 다운스트림 전 필드 선언 |
| `MediaArtifact` | Athena | 비트 결박 이미지/영상(still/video/avatar/carousel) |
| `AudioClip` | Orpheus/Apollo | **voice/sfx = beat_index 결박 필수 (P1 봉쇄)** |
| `EditDecisionList` | Artemis | 비트별 컷·전환·자막·타이밍 |
| `CompositionSnapshot` | Atropos | selection + output_url + gate_passed 증명 |
| `ReelMetric` | Metis | ROAS/CTR 파생 → 창작 피드백(해자) |

## 설계 원칙
- **불변(frozen)** — 새 객체 생성, 변형 금지.
- **부재 필드 = None 폴백** (byte-identical). 단 결박 필수 필드는 `validate()`가 강제.
- **`assert_render_ready()`** = 렌더前 invariant gate. 전 비트 보이스(P1)·비주얼·자막(P13) 증명 못하면 block → 어젯밤 "음소거 슬라이드쇼" 구조 차단.
- `from_dict`/`from_row`/`from_slot_artifact` = 기존 dict/DB row와 backwards-compat.

## grounding
필드는 실제 DB 스키마(`infra/migrations`: slot.beat_index·artifact·composition_snapshot·reel_metrics) + beat dict 키에서 추출. 데이터 모델: `run → slot(track+beat_index) → artifact → clip → composition_snapshot`.

## 상태
Phase 0.1 — 모노레포 안 신규 패키지. 기존 코드 미수정(backwards-compat). 다음: hiob-core 추출 → hiob-data governor → god-file 분해 → 물리 분리.
