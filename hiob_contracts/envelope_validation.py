"""런타임 계약 검증 어댑터 — 타입 DSL을 '열망'에서 '경계 강제'로 (2026-07-05 seam).

planet_io.PLANET_IO가 선언한 계약을 실제 런타임 경계에서 검증한다. 그동안 star DSL
registry는 `from_dict`로 파싱만 하고 `validate()`를 걸지 않아, 필드 드리프트가 조용히
통과했다(노드맵 감사: "타입 DSL=열망, god-file가 우회"). 이 어댑터는 각 계약의
파싱(from_dict/from_list/ctor) + validate()를 한 데 묶어 경계에서 fail-loud로 만든다.

부재 계약·파싱불가는 조용히 통과가 아니라 명확한 위반으로 보고한다(조용한 스왈로우 금지).

LP1-7 / UM-1 residual: every SemanticEdge target_contract is registered, plus
orpheus/apollo/metis/hermes planet envelopes. `validate_edge_target` maps
edge_id → target schema; `verify_karma_edge_receipt` checks origin + freshness.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import import_module
from typing import Any

from pydantic import BaseModel

_ALL_BEAT_VIDEO_MODULE = "hiob_contracts.all_beat_video"
_STORYBOARD_TWO_STAGE_MODULE = "hiob_contracts.storyboard_two_stage_v1"
_EDGE_TARGET_INPUTS_MODULE = "hiob_contracts.edge_target_inputs"
_PLANET_ENVELOPES_MODULE = "hiob_contracts.planet_envelopes"

# 계약명 → (모듈, 클래스). 런타임 경계에서 검증할 핵심 계약(파싱·validate 보유).
_REGISTRY: dict[str, tuple[str, str]] = {
    # Core planet contracts
    "JanusBrief": ("hiob_contracts.janus_brief", "JanusBrief"),
    "Intake13Q": ("hiob_contracts.janus_brief", "Intake13Q"),
    "BeatPlan": ("hiob_contracts.beat_plan", "BeatPlan"),
    "Beat": ("hiob_contracts.beat_plan", "Beat"),
    "BeatCoverageV1": ("hiob_contracts.beat_coverage", "BeatCoverageV1"),
    "SerialFanInReceiptV1": ("hiob_contracts.beat_coverage", "SerialFanInReceiptV1"),
    "MediaArtifact": ("hiob_contracts.media_artifact", "MediaArtifact"),
    "AudioClip": ("hiob_contracts.audio_clip", "AudioClip"),
    "KlingVideo": ("hiob_contracts.klingvideo", "KlingVideo"),
    "Heroine": ("hiob_contracts.heroine", "Heroine"),
    "FeedbackSignal": ("hiob_contracts.feedback_signal", "FeedbackSignal"),
    "DefectSignal": ("hiob_contracts.defect_signal", "DefectSignal"),
    "ReelMetric": ("hiob_contracts.reel_metric", "ReelMetric"),
    "CompositionSnapshot": (
        "hiob_contracts.composition_snapshot",
        "CompositionSnapshot",
    ),
    "BeatPersona": ("hiob_contracts.beat_personas", "BeatPersona"),
    "BeatPersonas": ("hiob_contracts.beat_personas", "BeatPersonas"),
    "ElementLocks": ("hiob_contracts.element_locks", "ElementLocks"),
    # All-beat video V2/V3 factory chain.
    "FactoryBeatManifest": (
        _ALL_BEAT_VIDEO_MODULE,
        "FactoryBeatManifestV1",
    ),
    "BeatVideoRequest": (
        _ALL_BEAT_VIDEO_MODULE,
        "BeatVideoRequestV1",
    ),
    "BeatVideoReceipt": (
        _ALL_BEAT_VIDEO_MODULE,
        "BeatVideoReceiptV1",
    ),
    "BeatArtifactSetReceipt": (
        _ALL_BEAT_VIDEO_MODULE,
        "BeatArtifactSetReceiptV1",
    ),
    "AtroposFanInManifest": (
        _ALL_BEAT_VIDEO_MODULE,
        "AtroposFanInManifestV2",
    ),
    "AtroposFanInManifestV2": (
        _ALL_BEAT_VIDEO_MODULE,
        "AtroposFanInManifestV2",
    ),
    "AtroposFanInManifestV3": (
        _ALL_BEAT_VIDEO_MODULE,
        "AtroposFanInManifestV3",
    ),
    "HephaestusFinalRenderReceipt": (
        _ALL_BEAT_VIDEO_MODULE,
        "HephaestusFinalRenderReceiptV2",
    ),
    "ReelsFactoryReceiptV2": (
        _ALL_BEAT_VIDEO_MODULE,
        "ReelsFactoryReceiptV2",
    ),
    "FactoryPaidBudgetAuthority": (
        "hiob_contracts.factory_paid_budget_authority_v1",
        "FactoryPaidBudgetAuthorityV1",
    ),
    "FactoryPaidBudgetApprovalReceipt": (
        "hiob_contracts.factory_paid_budget_authority_v1",
        "FactoryPaidBudgetApprovalReceiptV1",
    ),
    "FactoryPaidBudgetAuthorityV2": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "FactoryPaidBudgetAuthorityV2",
    ),
    "FactoryPaidBudgetApprovalReceiptV2": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "FactoryPaidBudgetApprovalReceiptV2",
    ),
    "FactoryPaidBudgetResolutionV2": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "FactoryPaidBudgetResolutionV2",
    ),
    "FactoryPaidOperationHistoricalEvidenceV2": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "FactoryPaidOperationHistoricalEvidenceV2",
    ),
    "FactoryCostProfile": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "FactoryCostProfileV1",
    ),
    "ReelsFactoryProgressReceiptV3": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "ReelsFactoryProgressReceiptV3",
    ),
    "ReelsFactoryFailureReceiptV3": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "ReelsFactoryFailureReceiptV3",
    ),
    "StoryboardImageArtifactRef": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "StoryboardImageArtifactRefV1",
    ),
    "AthenaFramePlanReceipt": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "AthenaFramePlanReceiptV1",
    ),
    "StoryboardImageProviderRequest": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "StoryboardImageProviderRequestV1",
    ),
    "StoryboardImageProviderReceipt": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "StoryboardImageProviderReceiptV1",
    ),
    "StoryboardImageSetReceipt": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "StoryboardImageSetReceiptV1",
    ),
    "StoryboardPhaseACompletionReceipt": (
        "hiob_contracts.star_reels_view_v1",
        "StoryboardPhaseACompletionReceiptV1",
    ),
    "StoryboardPhaseACompletionSummary": (
        "hiob_contracts.star_reels_view_v1",
        "StoryboardPhaseACompletionSummaryV1",
    ),
    "StoryboardScene": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "StoryboardSceneV1",
    ),
    "StoryboardSceneVideoReceipt": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "StoryboardSceneVideoReceiptV1",
    ),
    "StoryboardSceneVideoRequest": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "StoryboardSceneVideoRequestV1",
    ),
    "StoryboardSceneVideoSetReceipt": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "StoryboardSceneVideoSetReceiptV1",
    ),
    "StoryboardSceneVideoSetSummary": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "StoryboardSceneVideoSetSummaryV1",
    ),
    "StoryboardBeatCaption": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "StoryboardBeatCaptionV1",
    ),
    "StoryboardSceneFanInManifest": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "StoryboardSceneFanInManifestV1",
    ),
    "ReelsFactoryReceiptV3": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "ReelsFactoryReceiptV3",
    ),
    "ReelsFactoryCompletionSummaryV3": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "ReelsFactoryCompletionSummaryV3",
    ),
    "StoryboardDraft": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "StoryboardDraftV1",
    ),
    "StoryboardApprovalReceipt": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "StoryboardApprovalReceiptV1",
    ),
    "StoryboardExecutionManifest": (
        _STORYBOARD_TWO_STAGE_MODULE,
        "StoryboardExecutionManifestV1",
    ),
    # Phase-3 edge targets (j2p / p2a)
    "ParzifalTargetInput": (
        "hiob_contracts.parzifal_target_input",
        "ParzifalTargetInput",
    ),
    "AresScriptInput": ("hiob_contracts.ares_script_input", "AresScriptInput"),
    "AresP2ATargetProjection": (
        "hiob_contracts.ares_create_script_v3",
        "AresP2ATargetProjectionV3",
    ),
    # LP1-7 residual edge targets (a2* / media / editorial / render)
    "AthenaPlanInput": (_EDGE_TARGET_INPUTS_MODULE, "AthenaPlanInput"),
    "OrpheusPlanInput": (_EDGE_TARGET_INPUTS_MODULE, "OrpheusPlanInput"),
    "ApolloPlanInput": (_EDGE_TARGET_INPUTS_MODULE, "ApolloPlanInput"),
    "AtroposDraftInput": (_EDGE_TARGET_INPUTS_MODULE, "AtroposDraftInput"),
    "ArtemisReviewInput": (_EDGE_TARGET_INPUTS_MODULE, "ArtemisReviewInput"),
    "AtroposApplyInput": (_EDGE_TARGET_INPUTS_MODULE, "AtroposApplyInput"),
    "HephaestusRenderInput": (
        _EDGE_TARGET_INPUTS_MODULE,
        "HephaestusRenderInput",
    ),
    # Planet envelopes (orpheus / apollo / hephaestus / metis)
    "AudioRequest": (_PLANET_ENVELOPES_MODULE, "AudioRequest"),
    "SFXRequest": (_PLANET_ENVELOPES_MODULE, "SFXRequest"),
    "VisualRequest": (_PLANET_ENVELOPES_MODULE, "VisualRequest"),
    "VisualContext": (_PLANET_ENVELOPES_MODULE, "VisualContext"),
    "RenderJobRequest": (_PLANET_ENVELOPES_MODULE, "RenderJobRequest"),
    "RenderJobResponse": (_PLANET_ENVELOPES_MODULE, "RenderJobResponse"),
    "ProcessInsightsRequest": (
        _PLANET_ENVELOPES_MODULE,
        "ProcessInsightsRequest",
    ),
    # Hermes CAPI (was only in hiob-hermes — now contracts-owned for envelope checks)
    "CAPIEvent": (_EDGE_TARGET_INPUTS_MODULE, "CAPIEvent"),
    "CAPIPayload": (_EDGE_TARGET_INPUTS_MODULE, "CAPIPayload"),
}

# Alias: star F1 uses PlanVisualsInput name; registry edge uses AthenaPlanInput.
_REGISTRY["PlanVisualsInput"] = _REGISTRY["AthenaPlanInput"]


class ContractViolation(ValueError):
    """계약 검증 실패 — 경계에서 드리프트 발견. contract/errors에 사유."""

    def __init__(self, contract: str, errors: list[str]):
        self.contract = contract
        self.errors = list(errors)
        super().__init__(f"{contract} 계약 위반: {'; '.join(self.errors) or 'unknown'}")


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    contract: str
    errors: tuple[str, ...] = ()
    obj: Any = None


def _resolve(name: str):
    ref = _REGISTRY.get(name)
    if not ref:
        return None
    mod, cls = ref
    try:
        return getattr(import_module(mod), cls)
    except Exception:  # noqa: BLE001 — 행성 패키지 미설치 등, 조용히 None(호출자가 unknown 보고)
        return None


def _parse(cls: Any, payload: Any) -> Any:
    """dict/list/인스턴스 → 계약 인스턴스. 타입 우선(B3): list→from_list, dict→from_dict/ctor.

    from_dict를 만능 폴백으로 쓰면 list payload가 from_dict(list)로 새서 TypeError → 타입을 먼저 본다.
    """
    if isinstance(payload, cls):
        return payload
    if isinstance(payload, list):
        if hasattr(cls, "from_list"):
            return cls.from_list(payload)
        raise TypeError(f"{cls.__name__}: list payload인데 from_list 없음")
    if isinstance(payload, dict):
        return cls.from_dict(payload) if hasattr(cls, "from_dict") else cls(**payload)
    if hasattr(cls, "from_dict"):
        return cls.from_dict(payload)
    raise TypeError(
        f"{cls.__name__}: dict/list/from_dict 없이 파싱 불가 (payload type={type(payload).__name__})"
    )


def validate_payload(contract: str, payload: Any) -> ValidationResult:
    """계약명 + payload(dict/list/인스턴스) → ValidationResult(ok, errors, obj).

    파싱(from_dict/from_list/ctor) 실패 or validate() 오류 → ok=False + errors.
    파싱 성공 + validate() 없음 → ok=True(구조적으로 유효). 조용한 통과 없음.
    """
    cls = _resolve(contract)
    if cls is None:
        return ValidationResult(
            False, contract, (f"unknown/unavailable contract: {contract}",)
        )
    try:
        obj = _parse(cls, payload)
    except Exception as e:  # noqa: BLE001 — 파싱 실패는 위반으로 보고(fail-loud)
        return ValidationResult(False, contract, (f"parse error: {e}",))
    errs: list[str] = []
    v = getattr(obj, "validate", None)
    if callable(v) and not isinstance(obj, BaseModel):
        try:
            errs = list(v() or [])
        except Exception as e:  # noqa: BLE001
            errs = [f"validate() raised: {e}"]
    return ValidationResult(not errs, contract, tuple(errs), obj)


def ensure_valid(contract: str, payload: Any) -> Any:
    """경계 강제 — 위반이면 ContractViolation raise, 통과면 파싱된 계약 obj 반환.

    DSL 노드/워커 경계에서 `obj = ensure_valid("JanusBrief", raw)`로 쓴다. 드리프트가
    깊은 곳에서 이상한 크래시로 번지는 대신 경계에서 명확히 멈춘다.
    """
    r = validate_payload(contract, payload)
    if not r.ok:
        raise ContractViolation(contract, list(r.errors))
    return r.obj


def registered_contracts() -> tuple[str, ...]:
    """검증 어댑터가 아는 계약명(정렬)."""
    return tuple(sorted(_REGISTRY))


# ── LP1-7: edge-scoped validation (9/9 SemanticEdges) ───────────────────────


def validate_edge_target(edge_id: str, payload: Any) -> ValidationResult:
    """Validate `payload` as the target_input for a registered SemanticEdge.

    Looks up edge_registry[edge_id].target_contract and runs validate_payload.
    Unknown edge_id → fail-loud (not silent pass).
    """
    from hiob_contracts.factory.edge_registry import get_edge

    edge = get_edge(edge_id)
    if edge is None:
        return ValidationResult(
            False,
            edge_id,
            (f"unknown edge_id: {edge_id} (not in edge_registry)",),
        )
    contract = edge.target_contract
    result = validate_payload(contract, payload)
    # Re-tag contract field with edge context for clearer logs.
    if not result.ok:
        return ValidationResult(
            False,
            f"{edge_id}:{contract}",
            result.errors,
            result.obj,
        )
    return ValidationResult(True, f"{edge_id}:{contract}", (), result.obj)


def ensure_edge_target(edge_id: str, payload: Any) -> Any:
    """Fail-loud edge target validation — raises ContractViolation on drift."""
    r = validate_edge_target(edge_id, payload)
    if not r.ok:
        raise ContractViolation(r.contract, list(r.errors))
    return r.obj


def edge_target_contracts() -> dict[str, str]:
    """edge_id → target_contract name for every registered SemanticEdge."""
    from hiob_contracts.factory.edge_registry import EDGES

    return {e.edge_id: e.target_contract for e in EDGES}


def unvalidated_edge_targets() -> tuple[str, ...]:
    """Edge IDs whose target_contract is not registered in this adapter (should be empty)."""
    missing: list[str] = []
    for edge_id, contract in edge_target_contracts().items():
        if contract not in _REGISTRY:
            missing.append(edge_id)
    return tuple(missing)


# ── UM-1 residual: KarmaEdgeReceipt origin + staleness ─────────────────────

_KARMA_MAPPER_NODE = "karma.edge.refine"
_DEFAULT_MAX_AGE_SECONDS = 86_400  # 24h


def _parse_iso(ts: str) -> datetime | None:
    if not ts or not isinstance(ts, str):
        return None
    try:
        # Accept trailing Z
        normalized = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def verify_karma_edge_receipt(
    receipt: Any,
    *,
    expected_edge_id: str | None = None,
    expected_source_digests: tuple[str, ...] | None = None,
    max_age_seconds: float | None = _DEFAULT_MAX_AGE_SECONDS,
    now: datetime | str | None = None,
) -> ValidationResult:
    """Verify KarmaEdgeReceipt origin (mapper/edge) and optional freshness.

    Checks (fail-loud, accumulate all errors):
    1. receipt is a KarmaEdgeReceipt (or dict that constructs one)
    2. edge_id is registered in edge_registry
    3. mapper.planet == karma and mapper.node_id == karma.edge.refine
    4. optional expected_edge_id match
    5. optional source_output_digests containment/equality
    6. optional staleness vs created_at (max_age_seconds; None disables)
    7. target contract metadata matches the registered edge
    8. accepted ⇒ target_input present (model also enforces digest match)
    """
    from hiob_contracts.factory.edge_registry import get_edge
    from hiob_contracts.factory.karma_edge import KarmaEdgeReceipt

    contract = "KarmaEdgeReceipt"
    errs: list[str] = []
    obj: Any = None

    try:
        if isinstance(receipt, KarmaEdgeReceipt):
            obj = receipt
        elif isinstance(receipt, dict):
            obj = KarmaEdgeReceipt.model_validate(receipt)
        else:
            return ValidationResult(
                False,
                contract,
                (f"unsupported receipt type: {type(receipt).__name__}",),
            )
    except Exception as e:  # noqa: BLE001
        return ValidationResult(False, contract, (f"parse error: {e}",))

    edge = get_edge(obj.edge_id)
    if edge is None:
        errs.append(f"unknown edge_id: {obj.edge_id}")
    else:
        target_contract = obj.target_contract
        if target_contract.name != edge.target_contract:
            errs.append(
                "target_contract.name mismatch: "
                f"expected {edge.target_contract!r}, got {target_contract.name!r}"
            )
        if obj.edge_id == "p2a":
            from hiob_contracts.ares_create_script_v3 import (
                ares_p2a_target_projection_v3_schema_digest,
            )

            if target_contract.version != "v3":
                errs.append(
                    "target_contract.version mismatch: "
                    f"expected 'v3', got {target_contract.version!r}"
                )
            expected_schema_digest = ares_p2a_target_projection_v3_schema_digest()
            if target_contract.schema_digest != expected_schema_digest:
                errs.append(
                    "target_contract.schema_digest mismatch: "
                    f"expected {expected_schema_digest!r}, "
                    f"got {target_contract.schema_digest!r}"
                )
    if expected_edge_id is not None and obj.edge_id != expected_edge_id:
        errs.append(
            f"edge_id mismatch: expected {expected_edge_id!r}, got {obj.edge_id!r}"
        )

    mapper = obj.mapper
    planet = getattr(mapper, "planet", None)
    node_id = getattr(mapper, "node_id", None)
    if planet != "karma":
        errs.append(f"mapper.origin planet must be 'karma', got {planet!r}")
    if node_id != _KARMA_MAPPER_NODE:
        errs.append(f"mapper.node_id must be {_KARMA_MAPPER_NODE!r}, got {node_id!r}")

    if expected_source_digests is not None:
        got = tuple(obj.source_output_digests)
        expected = tuple(expected_source_digests)
        if got != expected:
            # Containment: every expected digest must appear (order-sensitive equality preferred)
            missing = [d for d in expected if d not in got]
            if missing:
                errs.append(f"source_output_digests missing expected: {missing}")
            elif got != expected:
                errs.append("source_output_digests order/set mismatch vs expected")

    if max_age_seconds is not None:
        created = _parse_iso(obj.created_at)
        if created is None:
            errs.append(f"created_at unparseable: {obj.created_at!r}")
        else:
            if now is None:
                now_dt = datetime.now(timezone.utc)
            elif isinstance(now, datetime):
                now_dt = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
            else:
                now_dt = _parse_iso(str(now)) or datetime.now(timezone.utc)
            age = (now_dt - created).total_seconds()
            if age > float(max_age_seconds):
                errs.append(
                    f"receipt stale: age={age:.0f}s > max_age_seconds={max_age_seconds}"
                )
            if age < -60:
                errs.append(f"receipt created_at in the future (age={age:.0f}s)")

    if obj.decision == "accepted":
        if not obj.target_input:
            errs.append("accepted receipt missing target_input")
        elif edge is not None:
            # Also run target schema validation when we can
            tr = validate_payload(edge.target_contract, obj.target_input)
            if not tr.ok:
                errs.extend(f"target_input: {e}" for e in tr.errors)

    return ValidationResult(not errs, contract, tuple(errs), obj)


def ensure_karma_edge_receipt(receipt: Any, **kwargs: Any) -> Any:
    """Fail-loud receipt verify — raises ContractViolation on origin/staleness fail."""
    r = verify_karma_edge_receipt(receipt, **kwargs)
    if not r.ok:
        raise ContractViolation(r.contract, list(r.errors))
    return r.obj
