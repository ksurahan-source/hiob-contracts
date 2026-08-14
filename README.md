# hiob-contracts

HIOB 행성간 **타입 계약** (Phase 0.1, D-15 폴리레포). 행성은 서로 import 하지 않고 이 계약 객체로만 협업한다.

## 계약 체인
```
JanusBrief → BeatPlan[] → {MediaArtifact, AudioClip}[]
          → CompositionSnapshot → ReelMetric
```

### 2단계 스토리보드 생산

```text
Phase A 유료 승인 → 대본 1개 + 스틸 이미지 16개
  → 에디터 확인·재배치·장면 그룹화 → 현재 초안 승인
  → Phase B 유료 승인 → 장면 수만큼 영상 + 비트 보이스 16개 + 렌더 1개
```

비트는 대본·보이스·자막의 16개 의미 단위이고, 장면은 영상 생성 단위이다. 연속한 여러 비트가 하나의 장면을 공유할 수 있으므로 최종 영상 호출 수는 1~16개이며, 각 장면은 첫 카드의 승인된 이미지·프롬프트·프레이밍·모션만 사용한다. 나머지 카드의 텍스트는 음성과 자막 정보로 유지되며 제공자 프롬프트에 합쳐지지 않는다.

| 계약 | 생산 행성 | 핵심 |
|---|---|---|
| `JanusBrief` | Janus | 13Q + 직교축(locale/vertical/protagonist/style/reel_mode) |
| `BeatPlan`/`Beat` | Ares | 대본이 지휘 — 비트가 다운스트림 전 필드 선언 |
| `MediaArtifact` | Athena | 비트 결박 이미지/영상(still/video/avatar/carousel) |
| `AudioClip` | Orpheus/Apollo | **voice/sfx = beat_index 결박 필수 (P1 봉쇄)** |
| `CompositionSnapshot` | Atropos | selection + output_url + gate_passed 증명 |
| `ReelMetric` | Metis | ROAS/CTR 파생 → 창작 피드백(해자) |

> **SUNSET (D-66):** typed `EditDecisionList` deleted. Live editorial = `run.attributes.editing_decisions` / gated `artemis_autocut` dicts. Artemis live node = `references.snapshot` only.

## 설계 원칙
- **불변(frozen)** — 새 객체 생성, 변형 금지.
- **부재 필드 = None 폴백** (byte-identical). 단 결박 필수 필드는 `validate()`가 강제.
- **`assert_render_ready()`** = 렌더前 invariant gate. 전 비트 보이스(P1)·비주얼·자막(P13) 증명 못하면 block → 어젯밤 "음소거 슬라이드쇼" 구조 차단.
- `from_dict`/`from_row`/`from_slot_artifact` = 기존 dict/DB row와 backwards-compat.

## grounding
필드는 실제 DB 스키마(`infra/migrations`: slot.beat_index·artifact·composition_snapshot·reel_metrics) + beat dict 키에서 추출. 데이터 모델: `run → slot(track+beat_index) → artifact → clip → composition_snapshot`.

## 상태
Phase 0.1 — 모노레포 안 신규 패키지. 기존 코드 미수정(backwards-compat). 다음: hiob-core 추출 → hiob-data governor → god-file 분해 → 물리 분리.
