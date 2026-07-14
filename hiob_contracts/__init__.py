"""HIOB 행성간 타입 계약 (Phase 0.1, D-15 폴리레포).

계약 체인:
    JanusBrief → BeatPlan[] → {MediaArtifact, AudioClip, KlingVideo}[]
              → CompositionSnapshot → ReelMetric → FeedbackSignal

신설 3종:
    KlingVideo: 여성 아바타 입술싱크 (Athena → Hephaestus)
    Heroine: 여성 주연 캐스팅 메타데이터 (Janus → 전 하위 행성)
    FeedbackSignal: 측정 루프 피드백 (Metis → Janus/Ares)

규칙:
- 행성은 서로 import 하지 않고 이 계약 객체로만 주고받는다 (god-file/좌초 방지).
- 모든 계약은 frozen(불변) — 새 객체를 만들지 기존 것을 변형하지 않는다.
- 부재 필드는 None 허용(byte-identical 폴백). 단 결박 필수 필드는 validate()가 강제.
- audio 클립은 beat_index 결박 필수 = P1(음소거 슬라이드쇼) 구조 봉쇄.
"""
from .execution_backend import (
    ExecutionBackend, OperationRef, OperationStatus, CancelResult,
    JobEnvelope, RouteSnapshot, ExecutionAttempt, OutboxEntry,
    ExecutionContractError, ProviderError, IdempotencyError,
    DeadlineExceededError, UnknownOperationError,
    OperationStatusType,
)
from .janus_brief import Intake13Q, JanusBrief
from .beat_plan import Beat, BeatPlan
from .media_artifact import MediaArtifact
from .audio_clip import AudioClip
from .klingvideo import KlingVideo
from .heroine import Heroine, HeroineArchetype
from .feedback_signal import FeedbackSignal
from .defect_signal import DefectSignal
from .defect_signal_provider import DefectSignalProvider
from .composition_snapshot import CompositionSnapshot
from .reel_metric import ReelMetric
from .gate import RenderReadiness, assert_render_ready
from .six_realm import SixDoPreset, get_realm_preset, get_sfx_cue_for_emotion
from .locale_pack import LocalePack, resolve_locale_pack
from .beat_personas import BeatPersona, BeatPersonas
from .element_locks import (
    ElementLocks, ElementRef, CharacterLock, ProductLock, BackgroundLock,
    LOCK_STATUSES, ELEMENT_KINDS,
)
from .planet_envelopes import VisualContext, VisualRequest, AudioRequest, SFXRequest, RenderJobRequest, RenderJobResponse, ProcessInsightsRequest
from .planet_io import PlanetIO, PLANET_IO, Conformance, io_for, needs_new_contract, dsl_ready
from .envelope_validation import (
    ContractViolation,
    ValidationResult,
    validate_payload,
    ensure_valid,
    registered_contracts,
)
from .reel_kpi_provider import ReelKpiProvider
from .decision_callable import DecisionContext, DecisionCallable, resolve_decision
from .parzifal_master_sheet import (
    ParzifalMasterSheet, CharacterMasterSheet, ProductMasterSheet, SheetPanel,
    CHARACTER_ANGLES, PRODUCT_ANGLES, EXPRESSIONS, SHEET_STATUSES,
)

__all__ = [
    "ExecutionBackend", "OperationRef", "OperationStatus", "CancelResult",
    "JobEnvelope", "RouteSnapshot", "ExecutionAttempt", "OutboxEntry",
    "ExecutionContractError", "ProviderError", "IdempotencyError",
    "DeadlineExceededError", "UnknownOperationError",
    "OperationStatusType",
    "ContractViolation", "ValidationResult", "validate_payload", "ensure_valid", "registered_contracts",
    "ReelKpiProvider",
    "DecisionContext", "DecisionCallable", "resolve_decision",
    "ParzifalMasterSheet", "CharacterMasterSheet", "ProductMasterSheet", "SheetPanel",
    "CHARACTER_ANGLES", "PRODUCT_ANGLES", "EXPRESSIONS", "SHEET_STATUSES",
    "VisualContext","VisualRequest","AudioRequest","SFXRequest","RenderJobRequest","RenderJobResponse","ProcessInsightsRequest",
    "BeatPersona", "BeatPersonas",
    "ElementLocks", "ElementRef", "CharacterLock", "ProductLock", "BackgroundLock",
    "LOCK_STATUSES", "ELEMENT_KINDS",
    "PlanetIO", "PLANET_IO", "Conformance", "io_for", "needs_new_contract", "dsl_ready",
    "Intake13Q", "JanusBrief",
    "Beat", "BeatPlan",
    "MediaArtifact", "AudioClip",
    "KlingVideo", "Heroine", "HeroineArchetype", "FeedbackSignal", "DefectSignal", "DefectSignalProvider",
     "CompositionSnapshot", "ReelMetric",
    "RenderReadiness", "assert_render_ready",
    "SixDoPreset", "get_realm_preset", "get_sfx_cue_for_emotion",
    "LocalePack", "resolve_locale_pack",
]
__version__ = "0.1.0"
