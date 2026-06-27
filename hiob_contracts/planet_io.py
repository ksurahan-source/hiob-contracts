"""행성 I/O 정형화 레지스트리 — 단일 진실 (machine-readable).

핵심 룰(founder): 모든 행성의 인풋·아웃풋이 정형화(타입 계약)돼야 한다.
각 행성 = n8n DSL 노드: 타입계약 In → 타입계약 Out 순수함수.

이 레지스트리는 "어느 행성이 무엇을 받아 무엇을 내놓는가"의 계약 명세다. 잼미니 DSL
인터프리터(DynamicPipelineWorkflow)가 노드를 배선할 때 이 표를 읽는다. 산문 버전 =
`infra/polyrepo/PLANET_IO_CONTRACTS.md`.

`exists=True`  → 입/출력 계약 타입이 `hiob_contracts`에 이미 있음.
`exists=False` → ✳ 신규 정의 필요(아직 envelope 타입 부재).
`status`       → 현 코드의 정형화 수준 (전부 DB_COUPLED = run_id+Supabase, 순수 아님).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Conformance(str, Enum):
    TYPED_FULL = "typed_full"        # In·Out 둘 다 타입 계약, DB 결합 없음 (DSL 노드 준비됨)
    TYPED_PARTIAL = "typed_partial"  # 한쪽만 타입 / 행성층만 타입
    DB_COUPLED = "db_coupled"        # run_id 받아 Supabase서 컨텍스트 재구성 (현 전 행성)


@dataclass(frozen=True)
class PlanetIO:
    """한 행성의 정형 I/O 계약."""
    planet: str
    role: str
    input_contract: str       # hiob_contracts 타입명 (또는 ✳신규)
    output_contract: str
    input_exists: bool        # 입력 계약이 hiob_contracts에 이미 있나
    output_exists: bool
    conformance: Conformance  # 현 코드 실태
    entry: str                # DSL 노드가 호출할 진입점 (file:line)
    note: str = ""


# ── 정형 계약 체인 (Janus → … → Metis). 2026-06-27 10행성 감사 실측. ──
PLANET_IO: tuple[PlanetIO, ...] = (
    PlanetIO("janus", "인테이크", "Intake13Q", "JanusBrief", True, True,
             Conformance.DB_COUPLED, "workers/intake_clarify.py:28",
             "✅ build_janus_brief(raw→JanusBrief) 순수노드+테스트 green. 메인 worker(intake_clarify)는 DB셸. 스키마 중복 단일화는 잔여"),
    PlanetIO("ares", "스크립트", "JanusBrief", "BeatPlan", True, True,
             Conformance.DB_COUPLED, "hiob_ares/critic.py:28",
             "✅ build_script_kit(JanusBrief→스크립트킷)+critic_review_typed 순수노드+테스트 green. 최종 BeatPlan은 LLM 셸(hook 밴딧 sb 포함)"),
    PlanetIO("athena", "비주얼", "VisualRequest", "MediaArtifact", True, True,
             Conformance.DB_COUPLED, "workers/visual.py:2912",
             "✅ plan_visuals(VisualRequest→MediaArtifact[] 계획)+safe_prompt 순수노드+테스트 green. 이미지 생성은 worker 셸"),
    PlanetIO("orpheus", "보이스/음악", "AudioRequest", "AudioClip", True, True,
             Conformance.DB_COUPLED, "hiob_orpheus/voiceover_profile.py:65",
             "✅ select_music(AudioRequest→AudioClip)+resolve_voice 순수노드+테스트 green. TTS 합성은 worker 셸"),
    PlanetIO("apollo", "SFX", "SFXRequest", "AudioClip", True, True,
             Conformance.DB_COUPLED, "workers/sfx.py:541",
             "✅ select_sfx(SFXRequest→AudioClip[]) 순수노드+테스트 green. cue별 beat결박. worker(sfx.py)=자산 fetch 셸"),
    PlanetIO("atropos", "조립", "MediaArtifact+AudioClip", "CompositionSnapshot", True, True,
             Conformance.DB_COUPLED, "hiob_atropos/composer_v2.py:321",
             "✅ assemble_snapshot(media+audio→CompositionSnapshot) 순수노드+테스트 green. 8테이블 쿼리·렌더는 worker 셸"),
    PlanetIO("hephaestus", "렌더", "RenderJobRequest", "RenderJobResponse", True, True,
             Conformance.DB_COUPLED, "app.py:845",
             "✅ RenderJobRequest.to_dispatch()+RenderJobResponse.from_render_result() 순수노드+테스트 green. Lambda 렌더는 app.py 셸. 패키지 분리는 잔여"),
    PlanetIO("hermes", "발행", "CAPIEvent", "CAPIPayload", True, True,
             Conformance.TYPED_PARTIAL, "hiob_hermes/gateway.py:23",
             "✅ 레퍼런스 — process_capi_event(CAPIEvent→CAPIPayload) 순수코어+테스트 7 green. worker(capi_gateway.py)만 DB셸 = 정형화 패턴의 기준점"),
    PlanetIO("metis", "측정", "ProcessInsightsRequest", "ReelMetric|FeedbackSignal", True, True,
             Conformance.DB_COUPLED, "hiob_metis/__init__.py:22",
             "✅ process_insights(ProcessInsightsRequest→ReelMetric[]) 순수노드+테스트 green. sb 없음. DB upsert는 worker 셸"),
)

_BY_PLANET = {p.planet: p for p in PLANET_IO}


def io_for(planet: str) -> PlanetIO:
    """행성명 → 정형 I/O 계약. 미정의 행성은 KeyError."""
    return _BY_PLANET[planet.lower()]


def needs_new_contract() -> tuple[str, ...]:
    """✳ 신규 envelope 계약이 필요한 행성 목록 (정형화 잔여 작업)."""
    return tuple(
        p.planet for p in PLANET_IO if not (p.input_exists and p.output_exists)
    )


def dsl_ready() -> tuple[str, ...]:
    """DB 결합 없이 바로 DSL 노드가 될 수 있는 행성 (현재: 없음 — 전부 어댑터 필요)."""
    return tuple(p.planet for p in PLANET_IO if p.conformance is Conformance.TYPED_FULL)
