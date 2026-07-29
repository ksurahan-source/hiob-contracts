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
from .beat_plan import Beat, BeatPlan, normalize_scene_direction
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
    LOCK_STATUSES, ELEMENT_KINDS, standing_lookup,
)
from .character_identity_v1 import (
    character_identity_binding_payload_v1,
    derive_character_identity_binding_digest_v1,
)
from .character_lock_v1 import (
    CharacterLockV1,
    derive_character_lock_digest_v1,
)
from .voice_spec_v1 import VoiceSpecV1, derive_voice_spec_digest_v1
from .parzifal_voice_envelope_v1 import (
    ParzifalVoiceEnvelopeV1,
    derive_parzifal_voice_envelope_digest_v1,
)
from .star_make_ready_v1 import (
    StarMakeReadyRequestV1,
    StarMakeReadyReceiptV1,
    StarMakeReadyResolverV1,
    derive_star_make_ready_request_digest_v1,
    derive_star_make_ready_command_id_v1,
    derive_star_make_ready_receipt_digest_v1,
)
from .planet_envelopes import VisualContext, VisualRequest, AudioRequest, SFXRequest, RenderJobRequest, RenderJobResponse, ProcessInsightsRequest
from .planet_io import PlanetIO, PLANET_IO, Conformance, io_for, needs_new_contract, dsl_ready
from .envelope_validation import (
    ContractViolation,
    ValidationResult,
    validate_payload,
    ensure_valid,
    registered_contracts,
    validate_edge_target,
    ensure_edge_target,
    edge_target_contracts,
    unvalidated_edge_targets,
    verify_karma_edge_receipt,
    ensure_karma_edge_receipt,
)
from .edge_target_inputs import (
    AthenaPlanInput,
    OrpheusPlanInput,
    ApolloPlanInput,
    AtroposDraftInput,
    ArtemisReviewInput,
    AtroposApplyInput,
    HephaestusRenderInput,
    CAPIEvent,
    CAPIPayload,
)
from .timeline_v2_payload import (
    TIMELINE_V2_PAYLOAD_KEYS,
    build_timeline_v2_payload,
    hephaestus_render_node_input,
    normalize_render_dispatch_url,
    stable_snapshot_id,
)
from .reel_kpi_provider import ReelKpiProvider
from .decision_callable import DecisionContext, DecisionCallable, resolve_decision
from .parzifal_master_sheet import (
    ParzifalMasterSheet, CharacterMasterSheet, ProductMasterSheet, SheetPanel,
    CHARACTER_ANGLES, PRODUCT_ANGLES, EXPRESSIONS, SHEET_STATUSES,
)
from .parzifal_target_input import ParzifalTargetInput
from .element_lock_v3 import (
    CreateElementLockRequestV1,
    ElementArtifactRefV1,
    ElementLockPackageV1,
)
from .ares_script_input import AresScriptInput, ares_script_input_schema_digest
from .visual_materialization import (
    ALLOWED_V1_TRANSPORTS,
    BeatCastIntentV1,
    BeatFramePlanV1,
    BeatFramePlanV2,
    CastRoleIntentV1,
    PlannedReferenceV1,
    ReferenceSnapshotV1,
    SEEDREAM_5_PRO_MODEL_ID,
    SEEDREAM_V1_MAX_REFS,
    SEEDREAM_V1_TRANSPORT,
    VISUAL_CONTRACT_VERSION_V1,
    VISUAL_CONTRACT_VERSION_V2,
    VISUAL_RENDER_MODES_V1,
    assert_visual_provider_key_reuse_safe_v2,
    VisualMaterializationRequestV1,
    VisualMaterializationRequestV2,
    VisualMaterializationReceiptV1,
)
from .ares_create_script_v2 import (
    AresAuthorityV2,
    AresSpeakerSlotV2,
    AresIdentitySealedV2,
    AresProductFactsSealedV2,
    AresClaimRefV2,
    AresEvidenceAndClaimsSealedV2,
    AresHookDirectiveV2,
    AresCreativeConstraintsV2,
    AresCreateScriptRequestV2,
    ScriptPackageV2,
    AresBeatRoleIntentV2,
    BeatPlanV2,
    AresQualityFindingV2,
    AresGenerateProvenanceV2,
    AresGenerateUsageV2,
    AresCreateScriptResultV2,
    ares_create_script_request_schema_digest,
    ares_create_script_request_schema_descriptor_v2,
    ares_create_script_result_schema_digest,
    request_content_digest,
)
from .ares_create_script_v3 import (
    AresRequestScopeV3,
    authority_ref_receipt_digest_v3,
    AresAuthorityArtifactRefV3,
    AresP2ATargetProjectionV3,
    ares_p2a_target_projection_v3,
    ares_p2a_target_projection_v3_schema_descriptor,
    ares_p2a_target_projection_v3_schema_digest,
    karma_receipt_digest_v3,
    AresAuthorityBundleV3,
    AresCreateScriptRequestV3,
    ScriptPackageV3,
    AresSemanticBeatV3,
    SemanticBeatPlanV3,
    AresQualityFindingV3,
    AresGenerateProvenanceV3,
    AresGenerateUsageV3,
    AresCreateScriptResultV3,
    ares_create_script_request_v3_schema_digest,
    ares_create_script_request_v3_schema_descriptor,
    ares_create_script_result_v3_schema_digest,
    request_content_digest_v3,
)
from .ares_script_revision_v1 import (
    AresApprovalBeginCommandV1,
    AresApprovalCommandV1,
    AresApprovalReceiptV1,
    AresApprovalResolverV1,
    AresBeatPlanRevisionV1,
    AresBeatV1,
    AresSceneDirectionV1,
    AresScriptRevisionV1,
    AresScriptSegmentV1,
    BeatPlanV1,
    ScriptPackageV1,
    canonical_contract_json_v1,
    canonical_contract_digest_v1,
    derive_ares_g1_subject_digest_v1,
)
from .overnight_first_customer_v2 import (
    FIRST_CUSTOMER_CONTRACT_VERSIONS_V2,
    CreativeOrderV2,
    ScriptApprovalReceiptV2,
    EditorApprovalReceiptV2,
    PaidEffectIntentV2,
    PaidEffectAttemptV2,
    VerifiedRenderReceiptV2,
    derive_customer_order_key_v2,
    derive_effect_key_v2,
    derive_editor_approval_digest_v2,
    validate_creative_order_v2,
    validate_script_approval_receipt_v2,
    validate_editor_approval_receipt_v2,
    validate_paid_effect_intent_v2,
    validate_paid_effect_attempt_v2,
    validate_verified_render_receipt_v2,
)
from .artemis_product_lock_v1 import (
    ArtemisApprovalReceiptV1,
    ArtemisApprovalResolverV1,
    ArtemisClaimV1,
    ArtemisCompileRequestV1,
    ArtemisCompileResultV1,
    ArtemisSealRequestV1,
    ArtemisSealResultV1,
    JanusProductObservationV1,
    JanusProductObservationsV1,
    ObservationProvenanceV1,
    ProductElementLockDraftV1,
    ProductElementLockV1,
)
from .factory import (
    Digest, DigestError, canonical_json, sha256_digest, is_digest, assert_digest,
    PlanetOutput, ArtifactRef, ContractRef,
    KarmaRefineRequest, KarmaEdgeReceipt, TargetRef, PolicyRef,
    TransformLogEntry, EdgeViolation, MapperRef, derive_idempotency_key,
    StageReceipt, StageError, TERMINAL_STAGE_STATUSES,
    ApprovalReceipt, DegradationReceipt,
    FactoryState, TERMINAL_STATES, can_transition, assert_transition,
    StageExecutionState, EdgeExecutionState,
    SemanticEdge, EDGES, get_edge, is_registered_edge, required_edges,
)

__all__ = [
    "ExecutionBackend", "OperationRef", "OperationStatus", "CancelResult",
    "JobEnvelope", "RouteSnapshot", "ExecutionAttempt", "OutboxEntry",
    "ExecutionContractError", "ProviderError", "IdempotencyError",
    "DeadlineExceededError", "UnknownOperationError",
    "OperationStatusType",
    "ArtemisApprovalReceiptV1", "ArtemisApprovalResolverV1",
    "ArtemisClaimV1", "ArtemisCompileRequestV1", "ArtemisCompileResultV1",
    "ArtemisSealRequestV1", "ArtemisSealResultV1",
    "JanusProductObservationV1", "JanusProductObservationsV1",
    "ObservationProvenanceV1", "ProductElementLockDraftV1",
    "ProductElementLockV1",
    "ContractViolation", "ValidationResult", "validate_payload", "ensure_valid", "registered_contracts",
    "validate_edge_target", "ensure_edge_target", "edge_target_contracts", "unvalidated_edge_targets",
    "verify_karma_edge_receipt", "ensure_karma_edge_receipt",
    "ReelKpiProvider",
    "DecisionContext", "DecisionCallable", "resolve_decision",
    "ParzifalMasterSheet", "CharacterMasterSheet", "ProductMasterSheet", "SheetPanel",
    "CHARACTER_ANGLES", "PRODUCT_ANGLES", "EXPRESSIONS", "SHEET_STATUSES",
    "ParzifalTargetInput", "AresScriptInput", "ares_script_input_schema_digest",
    "CreateElementLockRequestV1", "ElementArtifactRefV1", "ElementLockPackageV1",
    "ALLOWED_V1_TRANSPORTS", "BeatCastIntentV1", "BeatFramePlanV1", "BeatFramePlanV2",
    "CastRoleIntentV1",
    "PlannedReferenceV1", "ReferenceSnapshotV1", "SEEDREAM_5_PRO_MODEL_ID",
    "SEEDREAM_V1_MAX_REFS", "SEEDREAM_V1_TRANSPORT",
    "VISUAL_CONTRACT_VERSION_V1", "VISUAL_CONTRACT_VERSION_V2",
    "VISUAL_RENDER_MODES_V1",
    "assert_visual_provider_key_reuse_safe_v2",
    "VisualMaterializationRequestV1",
    "VisualMaterializationRequestV2",
    "VisualMaterializationReceiptV1",
    "AresApprovalBeginCommandV1", "AresApprovalCommandV1",
    "AresApprovalReceiptV1", "AresApprovalResolverV1",
    "AresBeatPlanRevisionV1", "AresBeatV1", "AresSceneDirectionV1",
    "AresScriptRevisionV1", "AresScriptSegmentV1",
    "BeatPlanV1", "ScriptPackageV1",
    "AresAuthorityV2", "AresSpeakerSlotV2", "AresIdentitySealedV2",
    "AresProductFactsSealedV2", "AresClaimRefV2", "AresEvidenceAndClaimsSealedV2",
    "AresHookDirectiveV2", "AresCreativeConstraintsV2",
    "AresCreateScriptRequestV2", "ScriptPackageV2", "AresBeatRoleIntentV2",
    "BeatPlanV2", "AresQualityFindingV2", "AresGenerateProvenanceV2",
    "AresGenerateUsageV2", "AresCreateScriptResultV2",
    "ares_create_script_request_schema_digest",
    "ares_create_script_request_schema_descriptor_v2",
    "ares_create_script_result_schema_digest", "request_content_digest",
    "AresRequestScopeV3", "authority_ref_receipt_digest_v3",
    "AresAuthorityArtifactRefV3", "AresP2ATargetProjectionV3",
    "ares_p2a_target_projection_v3",
    "ares_p2a_target_projection_v3_schema_descriptor",
    "ares_p2a_target_projection_v3_schema_digest",
    "karma_receipt_digest_v3", "AresAuthorityBundleV3",
    "AresCreateScriptRequestV3", "ScriptPackageV3",
    "AresSemanticBeatV3", "SemanticBeatPlanV3",
    "AresQualityFindingV3", "AresGenerateProvenanceV3",
    "AresGenerateUsageV3", "AresCreateScriptResultV3",
    "ares_create_script_request_v3_schema_digest",
    "ares_create_script_request_v3_schema_descriptor",
    "ares_create_script_result_v3_schema_digest", "request_content_digest_v3",

    "canonical_contract_json_v1", "canonical_contract_digest_v1",
    "derive_ares_g1_subject_digest_v1",
    "FIRST_CUSTOMER_CONTRACT_VERSIONS_V2",
    "CreativeOrderV2", "ScriptApprovalReceiptV2", "EditorApprovalReceiptV2",
    "PaidEffectIntentV2", "PaidEffectAttemptV2", "VerifiedRenderReceiptV2",
    "derive_customer_order_key_v2", "derive_effect_key_v2",
    "derive_editor_approval_digest_v2",
    "validate_creative_order_v2", "validate_script_approval_receipt_v2",
    "validate_editor_approval_receipt_v2", "validate_paid_effect_intent_v2",
    "validate_paid_effect_attempt_v2", "validate_verified_render_receipt_v2",
    "AthenaPlanInput", "OrpheusPlanInput", "ApolloPlanInput", "AtroposDraftInput",
    "ArtemisReviewInput", "AtroposApplyInput", "HephaestusRenderInput",
    "CAPIEvent", "CAPIPayload",
    "TIMELINE_V2_PAYLOAD_KEYS", "build_timeline_v2_payload",
    "hephaestus_render_node_input", "normalize_render_dispatch_url", "stable_snapshot_id",
    "VisualContext","VisualRequest","AudioRequest","SFXRequest","RenderJobRequest","RenderJobResponse","ProcessInsightsRequest",
    "BeatPersona", "BeatPersonas",
    "ElementLocks", "ElementRef", "CharacterLock", "ProductLock", "BackgroundLock",
    "CharacterLockV1", "derive_character_lock_digest_v1",
    "character_identity_binding_payload_v1",
    "derive_character_identity_binding_digest_v1",
    "VoiceSpecV1", "derive_voice_spec_digest_v1",
    "ParzifalVoiceEnvelopeV1",
    "derive_parzifal_voice_envelope_digest_v1",
    "StarMakeReadyRequestV1", "StarMakeReadyReceiptV1",
    "StarMakeReadyResolverV1",
    "derive_star_make_ready_request_digest_v1",
    "derive_star_make_ready_command_id_v1",
    "derive_star_make_ready_receipt_digest_v1",
    "LOCK_STATUSES", "ELEMENT_KINDS", "standing_lookup",
    "PlanetIO", "PLANET_IO", "Conformance", "io_for", "needs_new_contract", "dsl_ready",
    "Intake13Q", "JanusBrief",
    "Beat", "BeatPlan", "normalize_scene_direction",
    "MediaArtifact", "AudioClip",
    "KlingVideo", "Heroine", "HeroineArchetype", "FeedbackSignal", "DefectSignal", "DefectSignalProvider",
     "CompositionSnapshot", "ReelMetric",
    "RenderReadiness", "assert_render_ready",
    "SixDoPreset", "get_realm_preset", "get_sfx_cue_for_emotion",
    "LocalePack", "resolve_locale_pack",
    # ── Creative Factory Harmony kernel (PRD 2026-07-14 §6–§7) ──
    "Digest", "DigestError", "canonical_json", "sha256_digest", "is_digest", "assert_digest",
    "PlanetOutput", "ArtifactRef", "ContractRef",
    "KarmaRefineRequest", "KarmaEdgeReceipt", "TargetRef", "PolicyRef",
    "TransformLogEntry", "EdgeViolation", "MapperRef", "derive_idempotency_key",
    "StageReceipt", "StageError", "TERMINAL_STAGE_STATUSES",
    "ApprovalReceipt", "DegradationReceipt",
    "FactoryState", "TERMINAL_STATES", "can_transition", "assert_transition",
    "StageExecutionState", "EdgeExecutionState",
    "SemanticEdge", "EDGES", "get_edge", "is_registered_edge", "required_edges",
]
__version__ = "0.1.0"
