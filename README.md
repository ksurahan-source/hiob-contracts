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

비트는 보이스와 자막을 각각 봉인하는 16개 의미 단위이고, 장면은 영상 생성 단위이다. 연속한 여러 비트가 하나의 장면을 공유할 수 있으므로 최종 영상 호출 수는 1~16개이며, 각 장면은 첫 카드의 승인된 이미지·프롬프트·프레이밍·모션만 사용한다. 나머지 카드의 보이스·자막은 독립된 타임라인 진실로 유지되며 제공자 프롬프트에 합쳐지지 않는다.

유료 실행 권한은 현재 USD 원가 프로필까지 검증한 `FactoryPaidBudgetResolutionV2`만 발급한다. 새 호출은 비직렬화 요청 권한, 완료된 호출의 장애 복구는 서버 전용 historical evidence로만 검증한다. 장면 영상 영수증은 사전검증된 4초·24fps·720×1280·무음 요청 전체를 포함하고, 장면 세트→자막·음성 팬인→최종 영수증까지 같은 증거 사슬을 대조한다.

전체 Phase A/장면/팬인 영수증은 서버 전용이다. `StarReelsView.v3`에는 비용 상한, 16→N 장면 투영, 최종 HTTPS 결과만 담은 redacted summary를 노출한다. 이 저장소는 계약 SOURCE를 제공하며, provider 결과 outbox·DB resolver·실행 어댑터 연결은 별도 WIRED/LIVE 증거가 필요하다.

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
