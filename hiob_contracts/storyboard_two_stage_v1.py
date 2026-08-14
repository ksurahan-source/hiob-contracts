"""Strict contracts for a two-stage, editor-approved storyboard workflow.

Phase A produces one script and exactly sixteen still images.  A provider-free
editor may then reorder/group cards, adjust framing metadata, or select a
server-verified replacement image.  Phase B remains impossible to authorize
until an approval receipt binds the current draft and its base image set.

Signed preview URLs are deliberately absent.  Browser state carries only the
opaque artifact id and the binary SHA-256 lookup digest; storage and provider
evidence remain server-side in :class:`StoryboardImageArtifactRefV1`.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Annotated, Any, Literal, Mapping, Protocol
from uuid import NAMESPACE_URL, uuid5
from weakref import WeakKeyDictionary

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    JsonValue,
    StrictBool,
    StringConstraints,
    field_validator,
    model_validator,
)

from .all_beat_video import (
    HephaestusFinalRenderReceiptV2,
    StrictAllBeatArtifactRefV1,
    _assert_audio_artifact,
    _assert_https_url,
)
from .ares_script_revision_v1 import (
    AresBeatPlanRevisionV1,
    AresScriptRevisionV1,
    DigestStr,
    NonBlankStr,
    NonNegativeInt,
    UtcTimestamp,
    UuidStr,
    _FROZEN_STRICT,
    _parse_utc,
    canonical_contract_digest_v1,
)


STORYBOARD_IMAGE_ARTIFACT_REF_VERSION_V1 = "StoryboardImageArtifactRef.v1"
ATHENA_FRAME_PLAN_RECEIPT_VERSION_V1 = "AthenaFramePlanReceipt.v1"
STORYBOARD_IMAGE_PROVIDER_REQUEST_VERSION_V1 = "StoryboardImageProviderRequest.v1"
STORYBOARD_IMAGE_PROVIDER_RECEIPT_VERSION_V1 = "StoryboardImageProviderReceipt.v1"
FACTORY_PAID_OPERATION_HISTORICAL_EVIDENCE_VERSION_V2 = (
    "FactoryPaidOperationHistoricalEvidence.v2"
)
STORYBOARD_IMAGE_SET_RECEIPT_VERSION_V1 = "StoryboardImageSetReceipt.v1"
STORYBOARD_CARD_VERSION_V1 = "StoryboardCard.v1"
STORYBOARD_SCENE_VERSION_V1 = "StoryboardScene.v1"
STORYBOARD_SCENE_VIDEO_ARTIFACT_REF_VERSION_V1 = "StoryboardSceneVideoArtifactRef.v1"
STORYBOARD_SCENE_VIDEO_RECEIPT_VERSION_V1 = "StoryboardSceneVideoReceipt.v1"
STORYBOARD_BEAT_SCENE_VIDEO_PROJECTION_VERSION_V1 = (
    "StoryboardBeatSceneVideoProjection.v1"
)
STORYBOARD_SCENE_VIDEO_SET_RECEIPT_VERSION_V1 = "StoryboardSceneVideoSetReceipt.v1"
STORYBOARD_SCENE_VIDEO_SET_SUMMARY_VERSION_V1 = "StoryboardSceneVideoSetSummary.v1"
STORYBOARD_BEAT_SCENE_PROJECTION_SUMMARY_VERSION_V1 = (
    "StoryboardBeatSceneProjectionSummary.v1"
)
STORYBOARD_BEAT_CAPTION_VERSION_V1 = "StoryboardBeatCaption.v1"
STORYBOARD_SCENE_FAN_IN_MANIFEST_VERSION_V1 = "StoryboardSceneFanInManifest.v1"
STORYBOARD_SCENE_VIDEO_REQUEST_VERSION_V1 = "StoryboardSceneVideoRequest.v1"
REELS_FACTORY_RECEIPT_VERSION_V3 = "ReelsFactoryReceipt.v3"
REELS_FACTORY_COMPLETION_SUMMARY_VERSION_V3 = "ReelsFactoryCompletionSummary.v3"
REELS_FACTORY_PROGRESS_RECEIPT_VERSION_V3 = "ReelsFactoryProgressReceipt.v3"
REELS_FACTORY_FAILURE_RECEIPT_VERSION_V3 = "ReelsFactoryFailureReceipt.v3"
FACTORY_COST_PROFILE_VERSION_V1 = "FactoryCostProfile.v1"
STORYBOARD_DRAFT_VERSION_V1 = "StoryboardDraft.v1"
STORYBOARD_APPROVAL_RECEIPT_VERSION_V1 = "StoryboardApprovalReceipt.v1"
STORYBOARD_EXECUTION_MANIFEST_VERSION_V1 = "StoryboardExecutionManifest.v1"
FACTORY_PAID_BUDGET_AUTHORITY_VERSION_V2 = "FactoryPaidBudgetAuthority.v2"
FACTORY_PAID_BUDGET_APPROVAL_RECEIPT_VERSION_V2 = "FactoryPaidBudgetApprovalReceipt.v2"

STORYBOARD_CONTRACT_VERSIONS_V1 = {
    "image_artifact_ref": STORYBOARD_IMAGE_ARTIFACT_REF_VERSION_V1,
    "athena_frame_plan_receipt": ATHENA_FRAME_PLAN_RECEIPT_VERSION_V1,
    "image_provider_request": STORYBOARD_IMAGE_PROVIDER_REQUEST_VERSION_V1,
    "image_provider_receipt": STORYBOARD_IMAGE_PROVIDER_RECEIPT_VERSION_V1,
    "paid_operation_historical_evidence": (
        FACTORY_PAID_OPERATION_HISTORICAL_EVIDENCE_VERSION_V2
    ),
    "image_set_receipt": STORYBOARD_IMAGE_SET_RECEIPT_VERSION_V1,
    "card": STORYBOARD_CARD_VERSION_V1,
    "scene": STORYBOARD_SCENE_VERSION_V1,
    "scene_video_artifact_ref": STORYBOARD_SCENE_VIDEO_ARTIFACT_REF_VERSION_V1,
    "scene_video_receipt": STORYBOARD_SCENE_VIDEO_RECEIPT_VERSION_V1,
    "beat_scene_video_projection": (STORYBOARD_BEAT_SCENE_VIDEO_PROJECTION_VERSION_V1),
    "scene_video_set_receipt": STORYBOARD_SCENE_VIDEO_SET_RECEIPT_VERSION_V1,
    "scene_video_set_summary": STORYBOARD_SCENE_VIDEO_SET_SUMMARY_VERSION_V1,
    "beat_scene_projection_summary": (
        STORYBOARD_BEAT_SCENE_PROJECTION_SUMMARY_VERSION_V1
    ),
    "beat_caption": STORYBOARD_BEAT_CAPTION_VERSION_V1,
    "scene_fan_in_manifest": STORYBOARD_SCENE_FAN_IN_MANIFEST_VERSION_V1,
    "scene_video_request": STORYBOARD_SCENE_VIDEO_REQUEST_VERSION_V1,
    "reels_factory_receipt": REELS_FACTORY_RECEIPT_VERSION_V3,
    "reels_factory_completion_summary": REELS_FACTORY_COMPLETION_SUMMARY_VERSION_V3,
    "reels_factory_progress_receipt": REELS_FACTORY_PROGRESS_RECEIPT_VERSION_V3,
    "reels_factory_failure_receipt": REELS_FACTORY_FAILURE_RECEIPT_VERSION_V3,
    "factory_cost_profile": FACTORY_COST_PROFILE_VERSION_V1,
    "draft": STORYBOARD_DRAFT_VERSION_V1,
    "approval_receipt": STORYBOARD_APPROVAL_RECEIPT_VERSION_V1,
    "execution_manifest": STORYBOARD_EXECUTION_MANIFEST_VERSION_V1,
    "paid_budget_authority": FACTORY_PAID_BUDGET_AUTHORITY_VERSION_V2,
    "paid_budget_approval_receipt": (FACTORY_PAID_BUDGET_APPROVAL_RECEIPT_VERSION_V2),
}

_JSON_SAFE_INTEGER_MAX = 9_007_199_254_740_991
_STORYBOARD_BEAT_COUNT = 16
STORYBOARD_SCENE_VIDEO_PROVIDER_PROMPT_MAX_CHARS_V1 = 2_500


def _non_blank_limited(value: str) -> str:
    if not value.strip():
        raise ValueError("string must not be blank")
    return value


StoryboardBeatIndex = Annotated[int, Field(ge=0, le=15)]
PositiveSafeInt = Annotated[int, Field(gt=0, le=_JSON_SAFE_INTEGER_MAX)]
PositiveDimension = Annotated[int, Field(gt=0, le=65_535)]
BasisPoints = Annotated[int, Field(ge=0, le=10_000)]
RevisionInt = Annotated[int, Field(ge=1, le=_JSON_SAFE_INTEGER_MAX)]
StoryboardSceneCount = Annotated[int, Field(ge=1, le=16)]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
SceneId = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=80,
        pattern=r"^[a-z0-9](?:[a-z0-9._-]{0,79})$",
    ),
]
ArtifactId = Annotated[
    str,
    StringConstraints(max_length=240),
    AfterValidator(_non_blank_limited),
]
VoiceText = Annotated[
    str,
    StringConstraints(max_length=2_000),
    AfterValidator(_non_blank_limited),
]
ScriptText = Annotated[
    str,
    StringConstraints(max_length=2_000),
    AfterValidator(_non_blank_limited),
]
CaptionText = Annotated[str, StringConstraints(max_length=2_000)]
PromptOverride = Annotated[
    str,
    StringConstraints(max_length=4_000),
    AfterValidator(_non_blank_limited),
]
MotionNote = Annotated[
    str,
    StringConstraints(max_length=2_000),
    AfterValidator(_non_blank_limited),
]
StoryboardBeatDurationMs = Annotated[
    int,
    Field(strict=True, ge=1_000, le=15_000),
]
ImageMime = Literal["image/png", "image/jpeg", "image/webp"]
StoryboardCropMode = Literal["cover", "contain"]
FactoryPaidBudgetPurposeV2 = Literal[
    "storyboard_draft",
    "storyboard_regen",
    "final_production",
]


def _as_json_dict(value: Mapping[str, Any] | BaseModel) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return dict(value)


def _derive_digest(
    value: Mapping[str, Any] | BaseModel,
    digest_field: str,
) -> str:
    return canonical_contract_digest_v1(value, exclude={digest_field})


def derive_storyboard_image_generation_nonce_v1(
    *,
    authority_idempotency_key: str,
    purpose: FactoryPaidBudgetPurposeV2,
    source_beat_index: int,
) -> str:
    """Return the sole deterministic image nonce for one paid authority slot."""

    if purpose not in {"storyboard_draft", "storyboard_regen"}:
        raise ValueError("image generation nonce requires a storyboard image purpose")
    if type(source_beat_index) is not int or not 0 <= source_beat_index < 16:
        raise ValueError("source_beat_index must be an integer in 0..15")
    return str(
        uuid5(
            NAMESPACE_URL,
            (
                "hiob:storyboard-image-generation.v1:"
                f"{authority_idempotency_key}:{purpose}:image:{source_beat_index}"
            ),
        )
    )


def derive_storyboard_image_operation_key_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    data = _as_json_dict(value)
    return (
        f"reels:{data['workspace_id']}:{data['run_id']}:{data['plan_digest']}:"
        f"{data['generation_nonce']}:image:{data['source_beat_index']}"
    )


def derive_storyboard_image_provider_request_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    data = _as_json_dict(value)
    return canonical_contract_digest_v1(
        {
            "purpose": "storyboard-image-provider-request.v1",
            "contract_version": data["contract_version"],
            "workspace_id": data["workspace_id"],
            "run_id": data["run_id"],
            "factory_revision": data["factory_revision"],
            "budget_purpose": data["purpose"],
            "plan_digest": data["plan_digest"],
            "ares_script_revision_digest": data["ares_script_revision_digest"],
            "ares_beat_plan_revision_digest": data["ares_beat_plan_revision_digest"],
            "paid_budget_authority_digest": data["paid_budget_authority_digest"],
            "source_beat_index": data["source_beat_index"],
            "frame_plan": data["frame_plan"],
            "athena_frame_plan_receipt_digest": data[
                "athena_frame_plan_receipt_digest"
            ],
            "provider": data["provider"],
            "model": data["model"],
            "cost_profile_digest": data["cost_profile_digest"],
            "pricing_policy_revision": data["pricing_policy_revision"],
            "generation_nonce": data["generation_nonce"],
            "operation_key": data["operation_key"],
        }
    )


def derive_storyboard_image_expected_artifact_id_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    data = _as_json_dict(value)
    return str(
        uuid5(
            NAMESPACE_URL,
            (
                "hiob:storyboard-image-artifact.v1:"
                f"{data['operation_key']}:{data['request_digest']}"
            ),
        )
    )


def derive_storyboard_image_expected_storage_key_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    data = _as_json_dict(value)
    return (
        f"workspaces/{data['workspace_id']}/runs/{data['run_id']}/"
        f"storyboard/images/{data['source_beat_index']:02d}/"
        f"{data['expected_artifact_id']}"
    )


def derive_storyboard_image_provider_execution_request_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    data = _as_json_dict(value)
    return canonical_contract_digest_v1(
        {
            "purpose": "storyboard-image-provider-execution-request.v1",
            "contract_version": data["contract_version"],
            "workspace_id": data["workspace_id"],
            "run_id": data["run_id"],
            "factory_revision": data["factory_revision"],
            "budget_purpose": data["purpose"],
            "plan_digest": data["plan_digest"],
            "ares_script_revision_digest": data["ares_script_revision_digest"],
            "ares_beat_plan_revision_digest": data["ares_beat_plan_revision_digest"],
            "paid_budget_authority_digest": data["paid_budget_authority_digest"],
            "source_beat_index": data["source_beat_index"],
            "frame_plan": data["frame_plan"],
            "athena_frame_plan_receipt_digest": data[
                "athena_frame_plan_receipt_digest"
            ],
            "provider": data["provider"],
            "model": data["model"],
            "cost_profile_digest": data["cost_profile_digest"],
            "pricing_policy_revision": data["pricing_policy_revision"],
            "generation_nonce": data["generation_nonce"],
            "operation_key": data["operation_key"],
            "request_digest": data["request_digest"],
            "expected_artifact_id": data["expected_artifact_id"],
            "expected_storage_key": data["expected_storage_key"],
        }
    )


def derive_storyboard_image_provider_idempotency_key_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    data = _as_json_dict(value)
    return canonical_contract_digest_v1(
        {
            "purpose": "storyboard-image-provider-idempotency.v1",
            "operation_key": data["operation_key"],
            "execution_request_digest": data["execution_request_digest"],
        }
    )


def derive_storyboard_image_provider_receipt_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "receipt_digest")


def derive_factory_paid_operation_claim_output_digest_v2(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    """Seal the full typed provider result stored by a completed operation claim."""

    return canonical_contract_digest_v1(_as_json_dict(value))


def derive_factory_paid_operation_historical_evidence_digest_v2(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "evidence_digest")


def derive_athena_frame_plan_receipt_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "receipt_digest")


def derive_storyboard_image_artifact_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    """Return the binary lookup digest exposed to browser editor state."""

    data = _as_json_dict(value)
    digest = data.get("sha256")
    if not isinstance(digest, str):
        raise ValueError("sha256 is required to derive artifact_digest")
    return digest


def derive_storyboard_image_set_receipt_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "receipt_digest")


def derive_storyboard_beat_identity_digest_v1(
    plan_digest: str,
    source_beat_index: int,
    voice_text: str,
    caption_text: str,
) -> str:
    return canonical_contract_digest_v1(
        {
            "purpose": "storyboard-beat-identity.v1",
            "plan_digest": plan_digest,
            "source_beat_index": source_beat_index,
            "voice_text": voice_text,
            "caption_text": caption_text,
        }
    )


def derive_storyboard_card_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "card_digest")


def derive_storyboard_scene_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "scene_digest")


def derive_storyboard_scene_video_artifact_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    data = _as_json_dict(value)
    digest = data.get("sha256")
    if not isinstance(digest, str):
        raise ValueError("sha256 is required to derive video artifact_digest")
    return digest


def derive_storyboard_scene_video_operation_key_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    """Match Star's immutable paid operation key for one scene ordinal."""

    data = _as_json_dict(value)
    plan_nonce = str(data["plan_digest"]).removeprefix("sha256:")
    return (
        f"reels:{data['workspace_id']}:{data['run_id']}:"
        f"{data['factory_revision']}:{plan_nonce}:video:"
        f"{data['scene_sequence_index']}"
    )


def derive_storyboard_scene_video_request_digest_v1(
    value: Mapping[str, Any] | BaseModel | None = None,
    *,
    scene: Mapping[str, Any] | BaseModel | None = None,
    anchor_card: Mapping[str, Any] | BaseModel | None = None,
    storyboard_execution_manifest_digest: str | None = None,
    final_production_authority_digest: str | None = None,
) -> str:
    """Bind only the approved anchor and manifest/authority scene scope."""

    if value is not None:
        data = _as_json_dict(value)
        return _derive_storyboard_scene_video_request_digest_from_anchor_v1(
            scene_sequence_index=data["scene_sequence_index"],
            scene_id=data["scene_id"],
            scene_digest=data["scene_digest"],
            anchor=data["anchor"],
            storyboard_execution_manifest_digest=data[
                "storyboard_execution_manifest_digest"
            ],
            final_production_authority_digest=data["final_production_authority_digest"],
        )
    if (
        scene is None
        or anchor_card is None
        or storyboard_execution_manifest_digest is None
        or final_production_authority_digest is None
    ):
        raise TypeError("full request or complete legacy anchor scope is required")

    scene_data = _as_json_dict(scene)
    card_data = _as_json_dict(anchor_card)
    source_beat_indices = scene_data["source_beat_indices"]
    if (
        not source_beat_indices
        or card_data["source_beat_index"] != source_beat_indices[0]
        or card_data["selected_artifact"] != scene_data["anchor_selected_artifact"]
    ):
        raise ValueError("anchor_card must be the scene's first selected card")
    anchor = {
        "source_beat_index": card_data["source_beat_index"],
        "beat_identity_digest": card_data["beat_identity_digest"],
        "prompt_override": card_data["prompt_override"],
        "crop_mode": card_data["crop_mode"],
        "focal_x_basis_points": card_data["focal_x_basis_points"],
        "focal_y_basis_points": card_data["focal_y_basis_points"],
        "motion_note": card_data["motion_note"],
        "selected_artifact": card_data["selected_artifact"],
    }
    return _derive_storyboard_scene_video_request_digest_from_anchor_v1(
        scene_sequence_index=scene_data["sequence_index"],
        scene_id=scene_data["scene_id"],
        scene_digest=scene_data["scene_digest"],
        anchor=anchor,
        storyboard_execution_manifest_digest=storyboard_execution_manifest_digest,
        final_production_authority_digest=final_production_authority_digest,
    )


def _derive_storyboard_scene_video_request_digest_from_anchor_v1(
    *,
    scene_sequence_index: int,
    scene_id: str,
    scene_digest: str,
    anchor: Mapping[str, Any],
    storyboard_execution_manifest_digest: str,
    final_production_authority_digest: str,
) -> str:
    return canonical_contract_digest_v1(
        {
            "purpose": "storyboard-scene-video-request.v1",
            "storyboard_execution_manifest_digest": storyboard_execution_manifest_digest,
            "final_production_authority_digest": final_production_authority_digest,
            "scene_sequence_index": scene_sequence_index,
            "scene_id": scene_id,
            "scene_digest": scene_digest,
            "anchor": dict(anchor),
        }
    )


def derive_storyboard_scene_video_idempotency_key_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    data = _as_json_dict(value)
    return canonical_contract_digest_v1(
        {
            "purpose": "storyboard-scene-video-idempotency.v1",
            "workspace_id": data["workspace_id"],
            "run_id": data["run_id"],
            "factory_revision": data["factory_revision"],
            "plan_digest": data["plan_digest"],
            "storyboard_execution_manifest_digest": data[
                "storyboard_execution_manifest_digest"
            ],
            "final_production_authority_digest": data[
                "final_production_authority_digest"
            ],
            "scene_sequence_index": data["scene_sequence_index"],
            "scene_id": data["scene_id"],
            "scene_digest": data["scene_digest"],
            "provider": data["provider"],
            "model": data["model"],
            "generation_nonce": data["generation_nonce"],
            "duration_ms": data["duration_ms"],
            "fps": data["fps"],
            "width": data["width"],
            "height": data["height"],
            "audio_mode": data["audio_mode"],
            "cost_profile_digest": data["cost_profile_digest"],
            "pricing_policy_revision": data["pricing_policy_revision"],
            "request_digest": data["request_digest"],
            "execution_request_digest": data["execution_request_digest"],
        }
    )


def derive_storyboard_scene_video_execution_request_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    """Seal exact paid transport while preserving the anchor-only request digest."""

    data = _as_json_dict(value)
    return canonical_contract_digest_v1(
        {
            "purpose": "storyboard-scene-video-execution-request.v1",
            "contract_version": data["contract_version"],
            "workspace_id": data["workspace_id"],
            "run_id": data["run_id"],
            "factory_revision": data["factory_revision"],
            "plan_digest": data["plan_digest"],
            "storyboard_execution_manifest_digest": data[
                "storyboard_execution_manifest_digest"
            ],
            "final_production_authority_digest": data[
                "final_production_authority_digest"
            ],
            "scene_sequence_index": data["scene_sequence_index"],
            "scene_id": data["scene_id"],
            "scene_digest": data["scene_digest"],
            "request_digest": data["request_digest"],
            "provider": data["provider"],
            "model": data["model"],
            "cost_profile_digest": data["cost_profile_digest"],
            "pricing_policy_revision": data["pricing_policy_revision"],
            "duration_ms": data["duration_ms"],
            "fps": data["fps"],
            "width": data["width"],
            "height": data["height"],
            "audio_mode": data["audio_mode"],
            "generation_nonce": data["generation_nonce"],
        }
    )


def derive_storyboard_scene_video_provider_prompt_v1(
    anchor: Mapping[str, Any] | BaseModel,
) -> str:
    """Compile only approved anchor fields into the exact Kling prompt surface."""

    value = StoryboardSceneVideoAnchorV1.model_validate(_as_json_dict(anchor))
    lines = [
        "@image_1",
        f"crop_mode: {value.crop_mode}",
        f"focal_x_basis_points: {value.focal_x_basis_points}",
        f"focal_y_basis_points: {value.focal_y_basis_points}",
    ]
    for field_name, approved_text in (
        ("prompt_override", value.prompt_override),
        ("motion_note", value.motion_note),
    ):
        if approved_text is None:
            continue
        if "@image_" in approved_text.casefold():
            raise ValueError("provider prompt permits sole image reference @image_1")
        lines.extend((f"{field_name}:", approved_text))
    prompt = "\n".join(lines)
    if len(prompt) > STORYBOARD_SCENE_VIDEO_PROVIDER_PROMPT_MAX_CHARS_V1:
        raise ValueError("provider prompt exceeds 2500 character limit")
    return prompt


def derive_storyboard_scene_video_receipt_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "receipt_digest")


def derive_storyboard_beat_scene_video_projection_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "projection_digest")


def derive_storyboard_scene_video_set_receipt_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "receipt_digest")


def derive_storyboard_scene_video_set_summary_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "summary_digest")


def derive_storyboard_beat_caption_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "caption_digest")


def derive_storyboard_caption_set_digest_v1(
    value: tuple[BaseModel, ...] | list[BaseModel] | list[Mapping[str, Any]],
) -> str:
    captions = [
        item.model_dump(mode="json") if isinstance(item, BaseModel) else dict(item)
        for item in value
    ]
    return canonical_contract_digest_v1({"captions": captions})


def derive_storyboard_beat_scene_projection_summary_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "projection_digest")


def derive_storyboard_scene_fan_in_manifest_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "manifest_digest")


def derive_reels_factory_receipt_digest_v3(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "receipt_digest")


def derive_reels_factory_completion_summary_digest_v3(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "summary_digest")


def derive_storyboard_draft_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "draft_digest")


def derive_storyboard_approval_receipt_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "receipt_digest")


def derive_storyboard_execution_manifest_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "manifest_digest")


def derive_factory_paid_budget_approval_subject_digest_v2(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    data = _as_json_dict(value)
    return canonical_contract_digest_v1(
        {
            "contract_version": "FactoryPaidBudgetApprovalSubject.v2",
            "workspace_id": data["workspace_id"],
            "run_id": data["run_id"],
            "factory_revision": data["factory_revision"],
            "all_beat_count": data["all_beat_count"],
            "purpose": data["purpose"],
            "plan_digest": data["plan_digest"],
            "storyboard_draft_digest": data["storyboard_draft_digest"],
            "storyboard_approval_receipt_digest": data[
                "storyboard_approval_receipt_digest"
            ],
            "storyboard_scene_count": data["storyboard_scene_count"],
            "image_source_beat_indices": data["image_source_beat_indices"],
            "paid_calls": data["paid_calls"],
            "max_total_cost_microunits": data["max_total_cost_microunits"],
            "currency": data["currency"],
            "cost_profile_digest": data["cost_profile_digest"],
            "pricing_policy_revision": data["pricing_policy_revision"],
        }
    )


def derive_factory_paid_budget_idempotency_key_v2(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    data = _as_json_dict(value)
    return canonical_contract_digest_v1(
        {
            "purpose": "factory-paid-budget-authority.v2",
            "workspace_id": data["workspace_id"],
            "run_id": data["run_id"],
            "factory_revision": data["factory_revision"],
            "budget_purpose": data["purpose"],
            "approval_subject_digest": data["approval_subject_digest"],
            "approval_receipt_id": data["approval_receipt_id"],
            "approval_receipt_digest": data["approval_receipt_digest"],
            "cost_profile_digest": data["cost_profile_digest"],
            "pricing_policy_revision": data["pricing_policy_revision"],
        }
    )


def derive_factory_paid_budget_authority_digest_v2(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "authority_digest")


def derive_factory_paid_budget_approval_receipt_digest_v2(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "receipt_digest")


def derive_factory_cost_profile_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    data = _as_json_dict(value)
    data.pop("profile_digest", None)
    if data.get("all_beat_count") is None:
        data.pop("all_beat_count", None)
    if data.get("purpose_policies") is None:
        data.pop("purpose_policies", None)
    return canonical_contract_digest_v1(data)


def derive_reels_factory_progress_receipt_digest_v3(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "receipt_digest")


def derive_reels_factory_failure_receipt_digest_v3(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "receipt_digest")


class FactoryPaidBudgetApprovalResolverV2(Protocol):
    """Durable check proving a structurally valid V2 receipt is still current."""

    def is_current_approval(
        self,
        *,
        receipt_id: str,
        receipt_digest: str,
        workspace_id: str,
        run_id: str,
        factory_revision: int,
        state_revision: int,
        policy_version: str,
        approval_subject_digest: str,
        approver_account_id: str,
        cost_profile_digest: str,
        pricing_policy_revision: int,
        purpose: str,
        plan_digest: str | None,
        storyboard_draft_digest: str | None,
        storyboard_approval_receipt_digest: str | None,
        storyboard_scene_count: int | None,
        image_source_beat_indices: tuple[int, ...],
    ) -> bool: ...


class FactoryPaidOperationEvidenceResolverV2(Protocol):
    """Server-only proof that one historical paid claim completed durably."""

    def is_verified_completed_operation(
        self,
        *,
        evidence_id: str,
        evidence_digest: str,
        workspace_id: str,
        run_id: str,
        factory_revision: int,
        purpose: str,
        operation: str,
        source_index: int | None,
        paid_budget_authority_digest: str,
        cost_profile_digest: str,
        pricing_policy_revision: int,
        provider: str,
        model: str,
        operation_key: str,
        execution_request_digest: str,
        provider_operation_id: str,
        provider_binding_receipt_digest: str,
        provider_result_receipt_id: str,
        provider_result_receipt_digest: str,
        provider_result_output_digest: str,
        provider_result_recorded_at_utc: str,
        completed_claim_output_digest: str,
        reserved_at_utc: str,
        completed_at_utc: str,
    ) -> bool: ...


def _assert_storage_key(value: str) -> None:
    lowered = value.lower()
    if (
        not value
        or value != value.strip()
        or lowered.startswith(("http://", "https://", "data:", "file:"))
        or value.startswith("/")
        or "\\" in value
        or "?" in value
        or "#" in value
        or "%" in value
    ):
        raise ValueError("storage_key must be a relative credential-free storage key")
    path = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("storage_key must not contain empty or traversal segments")
    if path.as_posix() != value:
        raise ValueError("storage_key must use canonical POSIX form")


def _assert_opaque_artifact_id(value: str) -> None:
    if value != value.strip() or value.lower().startswith(
        ("http://", "https://", "data:", "file:")
    ):
        raise ValueError("artifact_id must be opaque, not a URL")


class StoryboardImageReferenceSnapshotV1(BaseModel):
    """Strict lossless projection of one approved BeatFramePlanV1 reference."""

    model_config = _FROZEN_STRICT

    owner: Literal["parzifal", "artemis"]
    workspace_id: NonBlankStr
    master_id: NonBlankStr
    version: RevisionInt
    approval_status: Literal["approved"]
    storage_key: NonBlankStr
    content_digest: DigestStr
    ref_kind: Literal["character", "product", "evidence"]
    subject_id: NonBlankStr
    label: NonBlankStr
    url: Literal[None]
    source_run_id: str | None

    @field_validator("storage_key")
    @classmethod
    def _credential_free_storage_key(cls, value: str) -> str:
        _assert_storage_key(value)
        return value

    @model_validator(mode="after")
    def _bind_reference_owner(self) -> "StoryboardImageReferenceSnapshotV1":
        if self.ref_kind == "character" and self.owner != "parzifal":
            raise ValueError("character references must be owned by parzifal")
        if self.ref_kind in {"product", "evidence"} and self.owner != "artemis":
            raise ValueError("product/evidence references must be owned by artemis")
        return self


class StoryboardImagePlannedReferenceV1(BaseModel):
    """Strict provider-order reference projection from BeatFramePlanV1."""

    model_config = _FROZEN_STRICT

    role: Literal["lead", "co_star", "product", "evidence"]
    required: StrictBool
    snapshot: StoryboardImageReferenceSnapshotV1


class StoryboardImageFramePlanV1(BaseModel):
    """Byte-equivalent, strict Pydantic projection of BeatFramePlanV1."""

    model_config = _FROZEN_STRICT

    run_id: NonBlankStr
    workspace_id: NonBlankStr
    beat_index: StoryboardBeatIndex
    shot_list_digest: DigestStr
    render_mode: Literal[
        "persona_talk",
        "duet",
        "hands_demo",
        "product_solo",
        "social_proof",
        "scene_no_person",
        "situation_pov",
        "before_after",
    ]
    ordered_refs: tuple[StoryboardImagePlannedReferenceV1, ...] = Field(max_length=5)
    shot: dict[str, JsonValue]
    prompt: NonBlankStr
    prompt_constitution_version: NonBlankStr
    plan_digest: DigestStr
    provider: Literal["seedream"]
    model: Literal["seedream-5-pro"]
    width: Literal[1024]
    height: Literal[1536]
    quality: Literal["high"]
    lock_policy: Literal["hard_fail"]
    max_refs: Annotated[int, Field(ge=1, le=5)]

    @field_validator("ordered_refs", mode="before")
    @classmethod
    def _refs_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _bind_legacy_frame_plan(self) -> "StoryboardImageFramePlanV1":
        if self.shot.get("beat_index") != self.beat_index:
            raise ValueError("shot must contain the matching beat_index")
        if len(self.ordered_refs) > self.max_refs:
            raise ValueError("ordered_refs exceeds max_refs")
        storage_keys = [ref.snapshot.storage_key for ref in self.ordered_refs]
        if len(storage_keys) != len(set(storage_keys)):
            raise ValueError("ordered_refs contains duplicate storage keys")
        if any(
            ref.snapshot.workspace_id != self.workspace_id for ref in self.ordered_refs
        ):
            raise ValueError("frame plan contains a cross-workspace reference")
        if self.plan_digest != canonical_contract_digest_v1(
            self,
            exclude={"plan_digest"},
        ):
            raise ValueError("plan_digest does not match BeatFramePlanV1 payload")
        return self


class AthenaFramePlanReceiptV1(BaseModel):
    """Canonical Athena authority for the exact sixteen paid still prompts."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AthenaFramePlanReceipt.v1"]
    workspace_id: NonBlankStr
    run_id: NonBlankStr
    script_revision_digest: DigestStr
    beat_plan_digest: DigestStr
    beat_plan_revision_digest: DigestStr
    visual_bridge_digest: DigestStr | None
    frame_plans: tuple[StoryboardImageFramePlanV1, ...] = Field(
        min_length=16,
        max_length=16,
    )
    receipt_digest: DigestStr

    @field_validator("frame_plans", mode="before")
    @classmethod
    def _plans_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _bind_complete_receipt(self) -> "AthenaFramePlanReceiptV1":
        if [plan.beat_index for plan in self.frame_plans] != list(range(16)):
            raise ValueError("Athena frame plans must cover beats exactly 0..15")
        if any(
            plan.workspace_id != self.workspace_id or plan.run_id != self.run_id
            for plan in self.frame_plans
        ):
            raise ValueError("Athena frame plan scope does not match receipt")
        if self.receipt_digest != derive_athena_frame_plan_receipt_digest_v1(self):
            raise ValueError("receipt_digest does not match Athena frame-plan receipt")
        return self


class StoryboardImageProviderRequestV1(BaseModel):
    """Exact paid Seedream request, inert until a fresh capability is minted."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryboardImageProviderRequest.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    purpose: Literal["storyboard_draft", "storyboard_regen"]
    plan_digest: DigestStr
    ares_script_revision_digest: DigestStr
    ares_beat_plan_revision_digest: DigestStr
    paid_budget_authority_digest: DigestStr
    source_beat_index: StoryboardBeatIndex
    frame_plan: StoryboardImageFramePlanV1
    athena_frame_plan_receipt_digest: DigestStr
    provider: NonBlankStr
    model: NonBlankStr
    cost_profile_digest: DigestStr
    pricing_policy_revision: PositiveSafeInt
    generation_nonce: UuidStr
    operation_key: NonBlankStr
    expected_artifact_id: UuidStr
    expected_storage_key: NonBlankStr
    request_digest: DigestStr
    execution_request_digest: DigestStr
    idempotency_key: DigestStr

    @field_validator("expected_storage_key")
    @classmethod
    def _relative_expected_storage_key(cls, value: str) -> str:
        _assert_storage_key(value)
        return value

    @model_validator(mode="after")
    def _bind_request(self) -> "StoryboardImageProviderRequestV1":
        if self.ares_beat_plan_revision_digest != self.plan_digest:
            raise ValueError("ares beat-plan revision digest must equal plan_digest")
        if (
            self.frame_plan.workspace_id != self.workspace_id
            or self.frame_plan.run_id != self.run_id
            or self.frame_plan.beat_index != self.source_beat_index
            or self.frame_plan.provider != self.provider
            or self.frame_plan.model != self.model
        ):
            raise ValueError("frame plan does not match image request scope")
        if self.operation_key != derive_storyboard_image_operation_key_v1(self):
            raise ValueError("operation_key does not match image request")
        if self.request_digest != derive_storyboard_image_provider_request_digest_v1(
            self
        ):
            raise ValueError("request_digest does not match image request")
        if self.expected_artifact_id != (
            derive_storyboard_image_expected_artifact_id_v1(self)
        ):
            raise ValueError("expected_artifact_id does not match image request")
        if self.expected_storage_key != (
            derive_storyboard_image_expected_storage_key_v1(self)
        ):
            raise ValueError("expected_storage_key does not match image request")
        if self.execution_request_digest != (
            derive_storyboard_image_provider_execution_request_digest_v1(self)
        ):
            raise ValueError("execution_request_digest does not match image request")
        if self.idempotency_key != (
            derive_storyboard_image_provider_idempotency_key_v1(self)
        ):
            raise ValueError("idempotency_key does not match image request")
        return self

    @classmethod
    def from_verified(
        cls,
        value: Mapping[str, Any] | "StoryboardImageProviderRequestV1",
        *,
        authority: object,
        script_revision: AresScriptRevisionV1,
        plan_revision: AresBeatPlanRevisionV1,
        athena_receipt: Mapping[str, Any] | AthenaFramePlanReceiptV1,
        at_utc: str,
        resolver: FactoryPaidBudgetApprovalResolverV2,
    ) -> "VerifiedStoryboardImageProviderRequestV1":
        request = cls.model_validate(value)
        resolution = _unwrap_verified_factory_paid_budget_resolution_v2(authority)
        paid_authority = resolution.paid_budget_authority
        profile = resolution.cost_profile
        if not isinstance(script_revision, AresScriptRevisionV1) or not isinstance(
            plan_revision,
            AresBeatPlanRevisionV1,
        ):
            raise TypeError("image execution requires validated Ares revisions")
        athena = AthenaFramePlanReceiptV1.model_validate(athena_receipt)
        if not profile.is_valid_at(
            at_utc
        ) or not resolution.approval_receipt.authorizes(
            paid_authority,
            at_utc=at_utc,
            resolver=resolver,
        ):
            raise ValueError("image execution requires current durable approval")
        if (
            not plan_revision.binds_script_revision(script_revision)
            or script_revision.workspace_id != request.workspace_id
            or script_revision.run_id != request.run_id
            or script_revision.factory_revision != request.factory_revision
            or request.ares_script_revision_digest != script_revision.revision_digest
            or request.ares_beat_plan_revision_digest != plan_revision.revision_digest
            or request.plan_digest != plan_revision.revision_digest
            or len(plan_revision.beat_plan.beats) != 16
            or plan_revision.beat_plan.beats[request.source_beat_index].beat_index
            != request.source_beat_index
        ):
            raise ValueError(
                "image request does not bind the current Ares revision pair"
            )
        if (
            athena.workspace_id != request.workspace_id
            or athena.run_id != request.run_id
            or athena.script_revision_digest != script_revision.revision_digest
            or athena.beat_plan_digest != plan_revision.beat_plan.plan_digest
            or athena.beat_plan_revision_digest != plan_revision.revision_digest
            or athena.receipt_digest != request.athena_frame_plan_receipt_digest
            or athena.frame_plans[request.source_beat_index] != request.frame_plan
        ):
            raise ValueError("image request does not bind the exact Athena frame plan")
        if (
            paid_authority.purpose not in {"storyboard_draft", "storyboard_regen"}
            or paid_authority.purpose != request.purpose
            or paid_authority.workspace_id != request.workspace_id
            or paid_authority.run_id != request.run_id
            or paid_authority.factory_revision != request.factory_revision
            or paid_authority.authority_digest != request.paid_budget_authority_digest
            or request.source_beat_index not in paid_authority.image_source_beat_indices
            or (
                paid_authority.purpose == "storyboard_draft"
                and paid_authority.plan_digest is not None
            )
            or (
                paid_authority.purpose == "storyboard_regen"
                and paid_authority.plan_digest != request.plan_digest
            )
        ):
            raise ValueError("image request does not match paid image authority")
        operation = profile.operations.image
        if (
            request.provider != operation.provider
            or request.model != operation.model
            or request.cost_profile_digest != profile.profile_digest
            or request.pricing_policy_revision != profile.pricing_policy_revision
        ):
            raise ValueError("image provider/model does not match current cost profile")
        expected_nonce = derive_storyboard_image_generation_nonce_v1(
            authority_idempotency_key=paid_authority.idempotency_key,
            purpose=paid_authority.purpose,
            source_beat_index=request.source_beat_index,
        )
        if request.generation_nonce != expected_nonce:
            raise ValueError("generation_nonce does not match the paid image slot")
        return VerifiedStoryboardImageProviderRequestV1(
            request,
            _token=_VERIFIED_IMAGE_REQUEST_TOKEN_V1,
        )


_VERIFIED_IMAGE_REQUEST_TOKEN_V1 = object()
_VERIFIED_IMAGE_REQUEST_REGISTRY_V1: WeakKeyDictionary[object, object] = (
    WeakKeyDictionary()
)


class VerifiedStoryboardImageProviderRequestV1:
    """Non-serializable single-process capability required before Seedream."""

    __slots__ = ("__weakref__",)

    def __init__(self, request: object, *, _token: object) -> None:
        if _token is not _VERIFIED_IMAGE_REQUEST_TOKEN_V1:
            raise TypeError(
                "verified image request can only be minted by from_verified"
            )
        _VERIFIED_IMAGE_REQUEST_REGISTRY_V1[self] = request

    def __setattr__(self, _name: str, _value: object) -> None:
        raise TypeError("verified image request is immutable")

    def __reduce_ex__(self, _protocol: int) -> object:
        raise TypeError("verified image request is not serializable")

    def __repr__(self) -> str:
        return "VerifiedStoryboardImageProviderRequestV1(<sealed>)"


def require_verified_storyboard_image_provider_request_v1(
    capability: object,
) -> StoryboardImageProviderRequestV1:
    if not isinstance(capability, VerifiedStoryboardImageProviderRequestV1):
        raise TypeError(
            "provider call requires VerifiedStoryboardImageProviderRequestV1"
        )
    try:
        request = _VERIFIED_IMAGE_REQUEST_REGISTRY_V1[capability]
    except KeyError as exc:
        raise TypeError("unminted verified image request capability") from exc
    if not isinstance(request, StoryboardImageProviderRequestV1):
        raise TypeError("verified image request capability is invalid")
    return request


class StoryboardImageProviderReceiptV1(BaseModel):
    """Committed durable still result for one exact verified image request."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryboardImageProviderReceipt.v1"]
    request: StoryboardImageProviderRequestV1
    operation_key: NonBlankStr
    provider: NonBlankStr
    model: NonBlankStr
    provider_task_id: NonBlankStr
    status: Literal["committed"]
    artifact_id: UuidStr
    storage_key: NonBlankStr
    sha256: DigestStr
    mime: ImageMime
    bytes_len: PositiveSafeInt
    width: PositiveDimension
    height: PositiveDimension
    started_at_utc: UtcTimestamp
    completed_at_utc: UtcTimestamp
    receipt_digest: DigestStr

    @field_validator("storage_key")
    @classmethod
    def _relative_storage_key(cls, value: str) -> str:
        _assert_storage_key(value)
        return value

    @model_validator(mode="after")
    def _bind_result(self) -> "StoryboardImageProviderReceiptV1":
        if (
            self.operation_key != self.request.operation_key
            or self.provider != self.request.provider
            or self.model != self.request.model
            or self.artifact_id != self.request.expected_artifact_id
            or self.storage_key != self.request.expected_storage_key
        ):
            raise ValueError("provider result does not match exact verified request")
        if _parse_utc(self.completed_at_utc) < _parse_utc(self.started_at_utc):
            raise ValueError("completed_at_utc must not precede started_at_utc")
        if self.receipt_digest != derive_storyboard_image_provider_receipt_digest_v1(
            self
        ):
            raise ValueError("receipt_digest does not match image provider receipt")
        return self

    @classmethod
    def from_verified_request(
        cls,
        value: Mapping[str, Any] | "StoryboardImageProviderReceiptV1",
        *,
        request: object,
    ) -> "StoryboardImageProviderReceiptV1":
        expected = require_verified_storyboard_image_provider_request_v1(request)
        receipt = cls.model_validate(value)
        if receipt.request != expected:
            raise ValueError("provider receipt does not bind verified image request")
        return receipt

    @classmethod
    def from_historical_evidence(
        cls,
        value: Mapping[str, Any] | "StoryboardImageProviderReceiptV1",
        *,
        request: StoryboardImageProviderRequestV1,
        evidence: object,
    ) -> "StoryboardImageProviderReceiptV1":
        receipt = cls.model_validate(value)
        historical = require_verified_factory_paid_operation_historical_evidence_v2(
            evidence
        )
        if (
            receipt.request != request
            or not _historical_evidence_binds_image_receipt_v2(
                historical,
                receipt,
            )
        ):
            raise ValueError("historical evidence does not bind image receipt")
        return receipt

    @classmethod
    def from_reconciled_claim(
        cls,
        value: Mapping[str, Any] | "StoryboardImageProviderReceiptV1",
        *,
        request: StoryboardImageProviderRequestV1,
        reconciliation: object,
    ) -> "StoryboardImageProviderReceiptV1":
        return cls.from_historical_evidence(
            value,
            request=request,
            evidence=reconciliation,
        )


class StoryboardImageArtifactRefV1(BaseModel):
    """Server-only rich still reference; signed preview URLs are forbidden."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryboardImageArtifactRef.v1"]
    source_beat_index: StoryboardBeatIndex
    artifact_id: ArtifactId
    storage_key: NonBlankStr
    sha256: DigestStr
    mime: ImageMime
    width: PositiveDimension
    height: PositiveDimension
    provider_receipt_digest: DigestStr
    frame_plan_digest: DigestStr
    generation_nonce: UuidStr
    artifact_digest: DigestStr

    @field_validator("artifact_id")
    @classmethod
    def _opaque_artifact_id(cls, value: str) -> str:
        _assert_opaque_artifact_id(value)
        return value

    @field_validator("storage_key")
    @classmethod
    def _relative_storage_key(cls, value: str) -> str:
        _assert_storage_key(value)
        return value

    @model_validator(mode="after")
    def _bind_binary_digest(self) -> "StoryboardImageArtifactRefV1":
        if self.artifact_digest != self.sha256:
            raise ValueError("artifact_digest must equal sha256")
        return self


class StoryboardSelectedArtifactV1(BaseModel):
    """Browser-safe artifact identity used by provider-free edit commands."""

    model_config = _FROZEN_STRICT

    artifact_id: ArtifactId
    artifact_digest: DigestStr

    @field_validator("artifact_id")
    @classmethod
    def _opaque_artifact_id(cls, value: str) -> str:
        _assert_opaque_artifact_id(value)
        return value


class StoryboardImageSetReceiptV1(BaseModel):
    """Complete Phase-A proof: exactly sixteen unique stills for beats 0..15."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryboardImageSetReceipt.v1"]
    receipt_id: NonBlankStr
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    plan_digest: DigestStr
    paid_budget_authority_digest: DigestStr
    paid_source_beat_indices: tuple[StoryboardBeatIndex, ...] = Field(
        min_length=1,
        max_length=16,
    )
    previous_image_set_receipt_digest: DigestStr | None
    expected_image_count: Literal[16]
    images: tuple[StoryboardImageArtifactRefV1, ...] = Field(
        min_length=16,
        max_length=16,
    )
    provider_receipts: tuple[StoryboardImageProviderReceiptV1, ...] = Field(
        min_length=16,
        max_length=16,
    )
    completed_at_utc: UtcTimestamp
    receipt_digest: DigestStr

    @field_validator(
        "paid_source_beat_indices",
        "images",
        "provider_receipts",
        mode="before",
    )
    @classmethod
    def _images_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _bind_complete_unique_set(self) -> "StoryboardImageSetReceiptV1":
        if [image.source_beat_index for image in self.images] != list(
            range(_STORYBOARD_BEAT_COUNT)
        ):
            raise ValueError("images must cover source beats exactly 0..15 in order")

        unique_fields = (
            "artifact_id",
            "storage_key",
            "provider_receipt_digest",
            "generation_nonce",
        )
        for field in unique_fields:
            values = [getattr(image, field) for image in self.images]
            if len(values) != len(set(values)):
                raise ValueError(f"image {field} values must be unique")

        receipt_sources = [
            receipt.request.source_beat_index for receipt in self.provider_receipts
        ]
        if receipt_sources != list(range(_STORYBOARD_BEAT_COUNT)):
            raise ValueError(
                "provider receipts must cover source beats exactly 0..15 in order"
            )
        execution_fields = {
            "provider_task_id": [
                receipt.provider_task_id for receipt in self.provider_receipts
            ],
            "receipt_digest": [
                receipt.receipt_digest for receipt in self.provider_receipts
            ],
            "operation_key": [
                receipt.request.operation_key for receipt in self.provider_receipts
            ],
            "request_digest": [
                receipt.request.request_digest for receipt in self.provider_receipts
            ],
            "execution_request_digest": [
                receipt.request.execution_request_digest
                for receipt in self.provider_receipts
            ],
            "idempotency_key": [
                receipt.request.idempotency_key for receipt in self.provider_receipts
            ],
            "generation_nonce": [
                receipt.request.generation_nonce for receipt in self.provider_receipts
            ],
            "artifact_id": [receipt.artifact_id for receipt in self.provider_receipts],
            "storage_key": [receipt.storage_key for receipt in self.provider_receipts],
        }
        for field, values in execution_fields.items():
            if len(values) != len(set(values)):
                raise ValueError(f"provider receipt {field} values must be unique")

        for image, receipt in zip(
            self.images,
            self.provider_receipts,
            strict=True,
        ):
            request = receipt.request
            if (
                image.source_beat_index != request.source_beat_index
                or image.artifact_id != receipt.artifact_id
                or image.storage_key != receipt.storage_key
                or image.sha256 != receipt.sha256
                or image.mime != receipt.mime
                or image.width != receipt.width
                or image.height != receipt.height
                or image.provider_receipt_digest != receipt.receipt_digest
                or image.frame_plan_digest != request.frame_plan.plan_digest
                or image.generation_nonce != request.generation_nonce
                or request.workspace_id != self.workspace_id
                or request.run_id != self.run_id
                or request.factory_revision != self.factory_revision
                or request.plan_digest != self.plan_digest
            ):
                raise ValueError("image does not match provider receipt projection")
        current_receipts = [
            receipt
            for receipt in self.provider_receipts
            if receipt.request.paid_budget_authority_digest
            == self.paid_budget_authority_digest
        ]
        current_purposes = {receipt.request.purpose for receipt in current_receipts}
        if not current_receipts or len(current_purposes) != 1:
            raise ValueError("image set current paid authority output is ambiguous")
        current_purpose = next(iter(current_purposes))
        current_sources = tuple(
            receipt.request.source_beat_index for receipt in current_receipts
        )
        if current_sources != self.paid_source_beat_indices:
            raise ValueError(
                "paid_source_beat_indices must equal current authority receipts"
            )
        if current_purpose == "storyboard_draft" and len(current_receipts) != 16:
            raise ValueError(
                "storyboard_draft image set requires all 16 current authority receipts"
            )
        if current_purpose == "storyboard_draft" and (
            self.paid_source_beat_indices != tuple(range(16))
            or self.previous_image_set_receipt_digest is not None
        ):
            raise ValueError("initial image set cannot carry prior regen lineage")
        if current_purpose == "storyboard_regen" and (
            self.previous_image_set_receipt_digest is None
            or tuple(sorted(self.paid_source_beat_indices))
            != self.paid_source_beat_indices
            or len(set(self.paid_source_beat_indices))
            != len(self.paid_source_beat_indices)
        ):
            raise ValueError(
                "regen image set requires exact prior lineage and paid subset"
            )
        if current_purpose == "storyboard_regen" and any(
            receipt.request.purpose != "storyboard_regen"
            for receipt in current_receipts
        ):
            raise ValueError("regen image set contains mismatched current receipts")
        if _parse_utc(self.completed_at_utc) < max(
            _parse_utc(receipt.completed_at_utc) for receipt in self.provider_receipts
        ):
            raise ValueError("completed_at_utc precedes a provider receipt")

        if self.receipt_digest != derive_storyboard_image_set_receipt_digest_v1(self):
            raise ValueError("receipt_digest does not match storyboard image set")
        return self

    def binds_paid_operations(
        self,
        authority: object,
        operation_proofs: tuple[object, ...],
        *,
        previous_image_set: "StoryboardImageSetReceiptV1 | None" = None,
    ) -> bool:
        """Bind only live call capabilities or resolver-verified completed claims."""

        resolution = _resolve_terminal_paid_budget_resolution_v2(
            authority,
            operation_proofs,
        )
        if resolution is None:
            return False
        paid_authority = resolution.paid_budget_authority
        if not (
            paid_authority.purpose in {"storyboard_draft", "storyboard_regen"}
            and paid_authority.workspace_id == self.workspace_id
            and paid_authority.run_id == self.run_id
            and paid_authority.factory_revision == self.factory_revision
            and paid_authority.authority_digest == self.paid_budget_authority_digest
            and paid_authority.image_source_beat_indices
            == self.paid_source_beat_indices
            and len(operation_proofs) == len(self.paid_source_beat_indices)
        ):
            return False
        if paid_authority.purpose == "storyboard_draft":
            if (
                paid_authority.plan_digest is not None
                or previous_image_set is not None
                or self.previous_image_set_receipt_digest is not None
                or self.paid_source_beat_indices != tuple(range(16))
            ):
                return False
        elif (
            previous_image_set is None
            or paid_authority.plan_digest != self.plan_digest
            or self.previous_image_set_receipt_digest
            != previous_image_set.receipt_digest
            or previous_image_set.workspace_id != self.workspace_id
            or previous_image_set.run_id != self.run_id
            or previous_image_set.factory_revision != self.factory_revision
            or previous_image_set.plan_digest != self.plan_digest
        ):
            return False

        receipt_by_source = {
            receipt.request.source_beat_index: receipt
            for receipt in self.provider_receipts
        }
        for source, proof in zip(
            self.paid_source_beat_indices,
            operation_proofs,
            strict=True,
        ):
            receipt = receipt_by_source[source]
            if (
                receipt.request.paid_budget_authority_digest
                != paid_authority.authority_digest
                or receipt.request.purpose != paid_authority.purpose
                or not _image_receipt_binds_operation_proof_v2(receipt, proof)
            ):
                return False

        paid_sources = set(self.paid_source_beat_indices)
        if paid_authority.purpose == "storyboard_draft":
            return all(
                receipt.request.paid_budget_authority_digest
                == paid_authority.authority_digest
                and receipt.request.purpose == "storyboard_draft"
                for receipt in self.provider_receipts
            )

        assert previous_image_set is not None
        for source in set(range(16)) - paid_sources:
            if (
                self.images[source] != previous_image_set.images[source]
                or self.provider_receipts[source]
                != previous_image_set.provider_receipts[source]
            ):
                return False
        return True


class StoryboardCardV1(BaseModel):
    """One editor card with immutable source identity and mutable presentation."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryboardCard.v1"]
    source_beat_index: StoryboardBeatIndex
    sequence_index: StoryboardBeatIndex
    scene_id: SceneId
    script_text: ScriptText
    voice_text: VoiceText
    caption_text: CaptionText
    duration_ms: StoryboardBeatDurationMs
    image_prompt: PromptOverride
    beat_identity_digest: DigestStr
    prompt_override: PromptOverride | None
    crop_mode: StoryboardCropMode
    focal_x_basis_points: BasisPoints
    focal_y_basis_points: BasisPoints
    motion_note: MotionNote | None
    selected_artifact: StoryboardSelectedArtifactV1
    card_digest: DigestStr

    @model_validator(mode="after")
    def _bind_card_digest(self) -> "StoryboardCardV1":
        if self.card_digest != derive_storyboard_card_digest_v1(self):
            raise ValueError("card_digest does not match storyboard card")
        return self


class StoryboardSceneV1(BaseModel):
    """One contiguous scene run anchored to its first approved card."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryboardScene.v1"]
    scene_id: SceneId
    sequence_index: StoryboardBeatIndex
    source_beat_indices: tuple[StoryboardBeatIndex, ...] = Field(
        min_length=1,
        max_length=16,
    )
    duration_ms: StoryboardBeatDurationMs
    anchor_selected_artifact: StoryboardSelectedArtifactV1
    scene_digest: DigestStr

    @field_validator("source_beat_indices", mode="before")
    @classmethod
    def _source_indices_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _bind_scene_digest(self) -> "StoryboardSceneV1":
        if len(self.source_beat_indices) != len(set(self.source_beat_indices)):
            raise ValueError("scene source beat indices must be unique")
        if self.scene_digest != derive_storyboard_scene_digest_v1(self):
            raise ValueError("scene_digest does not match storyboard scene")
        return self


class StoryboardSceneVideoAnchorV1(BaseModel):
    """Provider-free visual fields from the first approved card in one scene."""

    model_config = _FROZEN_STRICT

    source_beat_index: StoryboardBeatIndex
    beat_identity_digest: DigestStr
    prompt_override: PromptOverride | None
    crop_mode: StoryboardCropMode
    focal_x_basis_points: BasisPoints
    focal_y_basis_points: BasisPoints
    motion_note: MotionNote | None
    selected_artifact: StoryboardSelectedArtifactV1


class StoryboardSceneVideoRequestV1(BaseModel):
    """Exact provider request that can execute only after capability verification."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryboardSceneVideoRequest.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    plan_digest: DigestStr
    storyboard_execution_manifest_digest: DigestStr
    final_production_authority_digest: DigestStr
    scene_sequence_index: StoryboardBeatIndex
    scene_id: SceneId
    scene_digest: DigestStr
    anchor: StoryboardSceneVideoAnchorV1
    anchor_image: StoryboardImageArtifactRefV1
    generation_nonce: UuidStr
    duration_ms: Literal[4_000]
    fps: Literal[24]
    width: Literal[720]
    height: Literal[1_280]
    audio_mode: Literal["none"]
    provider: NonBlankStr
    model: NonBlankStr
    cost_profile_digest: DigestStr
    pricing_policy_revision: PositiveSafeInt
    request_digest: DigestStr
    execution_request_digest: DigestStr
    idempotency_key: DigestStr

    @model_validator(mode="after")
    def _bind_request_identity(self) -> "StoryboardSceneVideoRequestV1":
        derive_storyboard_scene_video_provider_prompt_v1(self.anchor)
        if (
            self.anchor.source_beat_index != self.anchor_image.source_beat_index
            or self.anchor.selected_artifact.artifact_id
            != self.anchor_image.artifact_id
            or self.anchor.selected_artifact.artifact_digest
            != self.anchor_image.artifact_digest
        ):
            raise ValueError("anchor image does not match selected artifact")
        expected_request_digest = derive_storyboard_scene_video_request_digest_v1(self)
        if self.request_digest != expected_request_digest:
            raise ValueError("request_digest does not match approved anchor request")
        if self.execution_request_digest != (
            derive_storyboard_scene_video_execution_request_digest_v1(self)
        ):
            raise ValueError(
                "execution_request_digest does not match paid provider request"
            )
        if self.idempotency_key != derive_storyboard_scene_video_idempotency_key_v1(
            self
        ):
            raise ValueError("idempotency_key does not match scene provider request")
        return self

    @classmethod
    def from_verified(
        cls,
        value: Mapping[str, Any] | BaseModel,
        *,
        manifest: "StoryboardExecutionManifestV1",
        authority: object,
        at_utc: str,
        resolver: "FactoryPaidBudgetApprovalResolverV2",
    ) -> "VerifiedStoryboardSceneVideoRequestV1":
        request = cls.model_validate(_as_json_dict(value))
        try:
            resolution = _unwrap_verified_factory_paid_budget_resolution_v2(authority)
        except TypeError as exc:
            raise TypeError(
                "scene request requires VerifiedFactoryPaidBudgetAuthorityV2"
            ) from exc
        if not request._binds_manifest_authority_and_cost_profile(
            manifest,
            resolution.paid_budget_authority,
            resolution.cost_profile,
            at_utc=at_utc,
        ):
            raise ValueError(
                "scene request anchor image, manifest, paid authority, audio mode, "
                "cost profile digest, pricing policy revision, or output profile "
                "does not bind"
            )
        if not resolution.approval_receipt.authorizes(
            resolution.paid_budget_authority,
            at_utc=at_utc,
            resolver=resolver,
        ):
            raise ValueError("scene provider call requires current durable approval")
        return VerifiedStoryboardSceneVideoRequestV1(
            request,
            _token=_VERIFIED_SCENE_VIDEO_REQUEST_TOKEN_V1,
        )

    def _binds_manifest_authority_and_cost_profile(
        self,
        manifest: "StoryboardExecutionManifestV1",
        paid_authority: "FactoryPaidBudgetAuthorityV2",
        cost_profile: "FactoryCostProfileV1",
        *,
        at_utc: str,
    ) -> bool:
        if self.scene_sequence_index >= len(manifest.scenes):
            return False
        scene = manifest.scenes[self.scene_sequence_index]
        anchor_source = scene.source_beat_indices[0]
        card_by_source = {card.source_beat_index: card for card in manifest.cards}
        image_by_source = {image.source_beat_index: image for image in manifest.images}
        anchor_card = card_by_source[anchor_source]
        expected_anchor = StoryboardSceneVideoAnchorV1.model_validate(
            {
                "source_beat_index": anchor_card.source_beat_index,
                "beat_identity_digest": anchor_card.beat_identity_digest,
                "prompt_override": anchor_card.prompt_override,
                "crop_mode": anchor_card.crop_mode,
                "focal_x_basis_points": anchor_card.focal_x_basis_points,
                "focal_y_basis_points": anchor_card.focal_y_basis_points,
                "motion_note": anchor_card.motion_note,
                "selected_artifact": anchor_card.selected_artifact,
            }
        )
        video_operation = cost_profile.operations.video
        return (
            paid_authority.purpose == "final_production"
            and paid_authority.workspace_id == manifest.workspace_id
            and paid_authority.run_id == manifest.run_id
            and paid_authority.factory_revision == manifest.factory_revision
            and paid_authority.plan_digest == manifest.plan_digest
            and paid_authority.storyboard_draft_digest
            == manifest.storyboard_draft_digest
            and paid_authority.storyboard_approval_receipt_digest
            == manifest.storyboard_approval_receipt_digest
            and paid_authority.storyboard_scene_count == len(manifest.scenes)
            and paid_authority.authority_digest
            == manifest.final_production_authority_digest
            and cost_profile.all_beat_count == 16
            and cost_profile.purpose_policies is not None
            and cost_profile.profile_digest == paid_authority.cost_profile_digest
            and cost_profile.pricing_policy_revision
            == paid_authority.pricing_policy_revision
            and cost_profile.currency == paid_authority.currency
            and cost_profile.is_valid_at(at_utc)
            and cost_profile.worst_case_cost_microunits(paid_authority.paid_calls)
            == paid_authority.max_total_cost_microunits
            and self.provider == video_operation.provider
            and self.model == video_operation.model
            and self.cost_profile_digest == cost_profile.profile_digest
            and self.pricing_policy_revision == cost_profile.pricing_policy_revision
            and video_operation.billing_unit == "second"
            and self.duration_ms // 1_000 <= video_operation.max_units_per_operation
            and self.workspace_id == manifest.workspace_id
            and self.run_id == manifest.run_id
            and self.factory_revision == manifest.factory_revision
            and self.plan_digest == manifest.plan_digest
            and self.storyboard_execution_manifest_digest == manifest.manifest_digest
            and self.final_production_authority_digest
            == paid_authority.authority_digest
            and self.scene_id == scene.scene_id
            and self.scene_digest == scene.scene_digest
            and self.anchor == expected_anchor
            and self.anchor_image == image_by_source[anchor_source]
        )


_VERIFIED_SCENE_VIDEO_REQUEST_TOKEN_V1 = object()
_VERIFIED_SCENE_VIDEO_REQUEST_REGISTRY_V1: WeakKeyDictionary[
    object,
    StoryboardSceneVideoRequestV1,
] = WeakKeyDictionary()


class VerifiedStoryboardSceneVideoRequestV1:
    """Non-serializable provider-call capability for one exact scene request."""

    __slots__ = ("__weakref__",)

    def __init__(
        self,
        request: StoryboardSceneVideoRequestV1,
        *,
        _token: object,
    ) -> None:
        if _token is not _VERIFIED_SCENE_VIDEO_REQUEST_TOKEN_V1:
            raise TypeError(
                "verified scene request can only be minted by from_verified"
            )
        _VERIFIED_SCENE_VIDEO_REQUEST_REGISTRY_V1[self] = request

    def __setattr__(self, _name: str, _value: object) -> None:
        raise TypeError("verified scene request is immutable")

    def __delattr__(self, _name: str) -> None:
        raise TypeError("verified scene request is immutable")

    def __copy__(self) -> object:
        raise TypeError("verified scene request cannot be copied")

    def __deepcopy__(self, _memo: dict[int, object]) -> object:
        raise TypeError("verified scene request cannot be copied")

    def __reduce_ex__(self, _protocol: int) -> object:
        raise TypeError("verified scene request is not serializable")

    def __repr__(self) -> str:
        return "VerifiedStoryboardSceneVideoRequestV1(<sealed>)"


def require_verified_storyboard_scene_video_request_v1(
    capability: object,
) -> StoryboardSceneVideoRequestV1:
    """Fail closed immediately before the paid provider adapter is entered."""

    if not isinstance(capability, VerifiedStoryboardSceneVideoRequestV1):
        raise TypeError("provider call requires VerifiedStoryboardSceneVideoRequestV1")
    try:
        return _VERIFIED_SCENE_VIDEO_REQUEST_REGISTRY_V1[capability]
    except KeyError as exc:
        raise TypeError("unminted verified scene request capability") from exc


def derive_storyboard_scenes_v1(
    cards: tuple[StoryboardCardV1, ...] | list[StoryboardCardV1],
) -> tuple[StoryboardSceneV1, ...]:
    """Project ordered cards into deterministic contiguous scene runs."""

    ordered = tuple(cards)
    if len(ordered) != _STORYBOARD_BEAT_COUNT or [
        card.sequence_index for card in ordered
    ] != list(range(_STORYBOARD_BEAT_COUNT)):
        raise ValueError("scene projection requires cards in sequence order 0..15")

    scenes: list[StoryboardSceneV1] = []
    seen_scene_ids: set[str] = set()
    run: list[StoryboardCardV1] = []
    for card in ordered:
        if run and card.scene_id != run[0].scene_id:
            scenes.append(_build_storyboard_scene_v1(run, len(scenes)))
            seen_scene_ids.add(run[0].scene_id)
            run = []
        if not run and card.scene_id in seen_scene_ids:
            raise ValueError("each scene_id must form one contiguous card run")
        run.append(card)
    scenes.append(_build_storyboard_scene_v1(run, len(scenes)))
    return tuple(scenes)


def _build_storyboard_scene_v1(
    cards: list[StoryboardCardV1],
    scene_sequence_index: int,
) -> StoryboardSceneV1:
    anchor = cards[0]
    body: dict[str, Any] = {
        "contract_version": STORYBOARD_SCENE_VERSION_V1,
        "scene_id": anchor.scene_id,
        "sequence_index": scene_sequence_index,
        "source_beat_indices": [card.source_beat_index for card in cards],
        "duration_ms": sum(card.duration_ms for card in cards),
        "anchor_selected_artifact": anchor.selected_artifact.model_dump(mode="json"),
    }
    if body["duration_ms"] > 15_000:
        raise ValueError("each contiguous storyboard scene must be 15 seconds or less")
    body["scene_digest"] = derive_storyboard_scene_digest_v1(body)
    return StoryboardSceneV1.model_validate(body)


class StoryboardSceneVideoArtifactRefV1(BaseModel):
    """Immutable durable artifact produced for one approved scene."""

    model_config = _FROZEN_STRICT

    artifact_id: ArtifactId
    storage_key: NonBlankStr
    sha256: DigestStr
    mime: Literal["video/mp4"]
    bytes_len: PositiveSafeInt
    duration_ms: Literal[4_000]
    width: PositiveDimension
    height: PositiveDimension
    artifact_digest: DigestStr

    @field_validator("artifact_id")
    @classmethod
    def _opaque_artifact_id(cls, value: str) -> str:
        _assert_opaque_artifact_id(value)
        return value

    @field_validator("storage_key")
    @classmethod
    def _relative_storage_key(cls, value: str) -> str:
        _assert_storage_key(value)
        return value

    @model_validator(mode="after")
    def _bind_binary_digest(self) -> "StoryboardSceneVideoArtifactRefV1":
        if self.artifact_digest != self.sha256:
            raise ValueError("artifact_digest must equal sha256")
        return self


class StoryboardSceneVideoReceiptV1(BaseModel):
    """Successful provider receipt for one exact verified paid request."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryboardSceneVideoReceipt.v1"]
    request: StoryboardSceneVideoRequestV1
    provider_job_id: ArtifactId
    status: Literal["succeeded"]
    artifact: StoryboardSceneVideoArtifactRefV1
    receipt_digest: DigestStr

    @field_validator("provider_job_id")
    @classmethod
    def _opaque_provider_job_id(cls, value: str) -> str:
        _assert_opaque_artifact_id(value)
        return value

    @model_validator(mode="after")
    def _bind_receipt_digest(self) -> "StoryboardSceneVideoReceiptV1":
        if (
            self.artifact.duration_ms != self.request.duration_ms
            or self.artifact.width != self.request.width
            or self.artifact.height != self.request.height
        ):
            raise ValueError("video artifact output profile does not match request")
        if self.receipt_digest != derive_storyboard_scene_video_receipt_digest_v1(self):
            raise ValueError("receipt_digest does not match scene video receipt")
        return self

    @classmethod
    def from_verified_request(
        cls,
        value: Mapping[str, Any] | BaseModel,
        *,
        request: object,
    ) -> "StoryboardSceneVideoReceiptV1":
        receipt = cls.model_validate(_as_json_dict(value))
        if not receipt.binds_verified_request(request):
            raise ValueError("receipt does not bind the exact verified request")
        return receipt

    def binds_verified_request(self, request: object) -> bool:
        try:
            verified_request = require_verified_storyboard_scene_video_request_v1(
                request
            )
        except TypeError:
            return False
        return self.request == verified_request

    @classmethod
    def from_historical_evidence(
        cls,
        value: Mapping[str, Any] | BaseModel,
        *,
        request: StoryboardSceneVideoRequestV1,
        evidence: object,
    ) -> "StoryboardSceneVideoReceiptV1":
        receipt = cls.model_validate(_as_json_dict(value))
        historical = require_verified_factory_paid_operation_historical_evidence_v2(
            evidence
        )
        if (
            receipt.request != request
            or not _historical_evidence_binds_scene_receipt_v2(
                historical,
                receipt,
            )
        ):
            raise ValueError("historical evidence does not bind scene video receipt")
        return receipt

    @classmethod
    def from_reconciled_claim(
        cls,
        value: Mapping[str, Any] | BaseModel,
        *,
        request: StoryboardSceneVideoRequestV1,
        reconciliation: object,
    ) -> "StoryboardSceneVideoReceiptV1":
        return cls.from_historical_evidence(
            value,
            request=request,
            evidence=reconciliation,
        )


class StoryboardBeatSceneVideoProjectionV1(BaseModel):
    """One card's deterministic reference to its scene's shared video."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryboardBeatSceneVideoProjection.v1"]
    sequence_index: StoryboardBeatIndex
    source_beat_index: StoryboardBeatIndex
    scene_sequence_index: StoryboardBeatIndex
    scene_digest: DigestStr
    video_artifact_id: ArtifactId
    video_artifact_digest: DigestStr
    repeat_index: StoryboardBeatIndex
    projection_digest: DigestStr

    @field_validator("video_artifact_id")
    @classmethod
    def _opaque_video_artifact_id(cls, value: str) -> str:
        _assert_opaque_artifact_id(value)
        return value

    @model_validator(mode="after")
    def _bind_projection_digest(self) -> "StoryboardBeatSceneVideoProjectionV1":
        if self.projection_digest != (
            derive_storyboard_beat_scene_video_projection_digest_v1(self)
        ):
            raise ValueError("projection_digest does not match beat scene projection")
        return self


class StoryboardSceneVideoSetReceiptV1(BaseModel):
    """Complete scene-video proof plus an exact sixteen-card projection."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryboardSceneVideoSetReceipt.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    plan_digest: DigestStr
    storyboard_execution_manifest_digest: DigestStr
    final_production_authority_digest: DigestStr
    storyboard_scene_count: StoryboardSceneCount
    scene_video_receipts: tuple[StoryboardSceneVideoReceiptV1, ...] = Field(
        min_length=1,
        max_length=16,
    )
    beat_projections: tuple[StoryboardBeatSceneVideoProjectionV1, ...] = Field(
        min_length=16,
        max_length=16,
    )
    completed_at_utc: UtcTimestamp
    receipt_digest: DigestStr

    @field_validator("scene_video_receipts", "beat_projections", mode="before")
    @classmethod
    def _tuple_fields(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _bind_complete_scene_video_set(self) -> "StoryboardSceneVideoSetReceiptV1":
        scene_receipts = self.scene_video_receipts
        if len(scene_receipts) != self.storyboard_scene_count:
            raise ValueError(
                "scene video receipt count must equal storyboard_scene_count"
            )
        if [item.request.scene_sequence_index for item in scene_receipts] != list(
            range(self.storyboard_scene_count)
        ):
            raise ValueError("scene video receipts must use dense sequence order")

        for field in (
            "scene_id",
            "scene_digest",
            "generation_nonce",
            "request_digest",
            "execution_request_digest",
            "idempotency_key",
        ):
            values = [getattr(item.request, field) for item in scene_receipts]
            if len(values) != len(set(values)):
                raise ValueError(f"scene video request {field} values must be unique")
        for field in (
            "provider_job_id",
            "receipt_digest",
        ):
            values = [getattr(item, field) for item in scene_receipts]
            if len(values) != len(set(values)):
                raise ValueError(f"scene video {field} values must be unique")
        for field in ("artifact_id", "storage_key"):
            values = [getattr(item.artifact, field) for item in scene_receipts]
            if len(values) != len(set(values)):
                raise ValueError(f"scene video artifact {field} values must be unique")

        projections = self.beat_projections
        if [item.sequence_index for item in projections] != list(
            range(_STORYBOARD_BEAT_COUNT)
        ):
            raise ValueError("beat projections must be in sequence order 0..15")
        if sorted(item.source_beat_index for item in projections) != list(
            range(_STORYBOARD_BEAT_COUNT)
        ):
            raise ValueError("beat projections must cover source beats exactly 0..15")

        current_scene = -1
        repeat_index = 0
        for projection in projections:
            if projection.scene_sequence_index == current_scene + 1:
                current_scene += 1
                repeat_index = 0
            elif projection.scene_sequence_index != current_scene:
                raise ValueError("beat projection scenes must be contiguous and dense")
            if projection.repeat_index != repeat_index:
                raise ValueError("repeat_index must be dense within its scene run")
            scene_receipt = scene_receipts[current_scene]
            if (
                projection.scene_digest != scene_receipt.request.scene_digest
                or projection.video_artifact_id != scene_receipt.artifact.artifact_id
                or projection.video_artifact_digest
                != scene_receipt.artifact.artifact_digest
            ):
                raise ValueError("beat projection does not match its scene video")
            repeat_index += 1
        if current_scene != self.storyboard_scene_count - 1:
            raise ValueError(
                "every scene video must be referenced by a beat projection"
            )
        if self.receipt_digest != (
            derive_storyboard_scene_video_set_receipt_digest_v1(self)
        ):
            raise ValueError("receipt_digest does not match scene video set")
        return self

    def binds(
        self,
        manifest: "StoryboardExecutionManifestV1",
        authority: object,
        verified_requests: tuple[object, ...],
    ) -> bool:
        resolution = _resolve_terminal_paid_budget_resolution_v2(
            authority,
            verified_requests,
        )
        if resolution is None:
            return False
        paid_authority = resolution.paid_budget_authority
        profile = resolution.cost_profile
        if not (
            paid_authority.purpose == "final_production"
            and paid_authority.workspace_id == manifest.workspace_id
            and paid_authority.run_id == manifest.run_id
            and paid_authority.factory_revision == manifest.factory_revision
            and paid_authority.plan_digest == manifest.plan_digest
            and paid_authority.authority_digest
            == self.final_production_authority_digest
            and paid_authority.storyboard_scene_count == self.storyboard_scene_count
            and paid_authority.storyboard_draft_digest
            == manifest.storyboard_draft_digest
            and paid_authority.storyboard_approval_receipt_digest
            == manifest.storyboard_approval_receipt_digest
            and manifest.final_production_authority_digest
            == paid_authority.authority_digest
            and manifest.manifest_digest == self.storyboard_execution_manifest_digest
            and manifest.workspace_id == self.workspace_id
            and manifest.run_id == self.run_id
            and manifest.factory_revision == self.factory_revision
            and manifest.plan_digest == self.plan_digest
            and len(manifest.scenes) == self.storyboard_scene_count
            and len(verified_requests) == self.storyboard_scene_count
        ):
            return False

        scene_index_by_source: dict[int, tuple[int, StoryboardSceneV1]] = {
            source_beat_index: (scene_sequence_index, scene)
            for scene_sequence_index, scene in enumerate(manifest.scenes)
            for source_beat_index in scene.source_beat_indices
        }
        for scene_sequence_index, (scene, receipt, request_capability) in enumerate(
            zip(
                manifest.scenes,
                self.scene_video_receipts,
                verified_requests,
                strict=True,
            )
        ):
            request = receipt.request
            if not (
                _scene_receipt_binds_operation_proof_v2(
                    receipt,
                    request_capability,
                )
                and request.scene_sequence_index == scene_sequence_index
                and request.scene_id == scene.scene_id
                and request.scene_digest == scene.scene_digest
                and request.anchor.selected_artifact == scene.anchor_selected_artifact
                and request.storyboard_execution_manifest_digest
                == manifest.manifest_digest
                and request.final_production_authority_digest
                == paid_authority.authority_digest
                and request.cost_profile_digest == profile.profile_digest
                and request.pricing_policy_revision == profile.pricing_policy_revision
                and request.provider == profile.operations.video.provider
                and request.model == profile.operations.video.model
            ):
                return False
        for card, projection in zip(
            manifest.cards,
            self.beat_projections,
            strict=True,
        ):
            scene_sequence_index, scene = scene_index_by_source[card.source_beat_index]
            receipt = self.scene_video_receipts[scene_sequence_index]
            if not (
                projection.sequence_index == card.sequence_index
                and projection.source_beat_index == card.source_beat_index
                and projection.scene_sequence_index == scene_sequence_index
                and projection.scene_digest == scene.scene_digest
                and projection.video_artifact_id == receipt.artifact.artifact_id
                and projection.video_artifact_digest == receipt.artifact.artifact_digest
                and projection.repeat_index
                == scene.source_beat_indices.index(card.source_beat_index)
            ):
                return False
        return True


class StoryboardBeatSceneProjectionSummaryV1(BaseModel):
    """Browser-safe 16-to-N scene mapping without artifact/provider identity."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryboardBeatSceneProjectionSummary.v1"]
    sequence_index: StoryboardBeatIndex
    source_beat_index: StoryboardBeatIndex
    scene_sequence_index: StoryboardBeatIndex
    scene_digest: DigestStr
    repeat_index: StoryboardBeatIndex
    projection_digest: DigestStr

    @model_validator(mode="after")
    def _bind_projection_digest(self) -> "StoryboardBeatSceneProjectionSummaryV1":
        if self.projection_digest != (
            derive_storyboard_beat_scene_projection_summary_digest_v1(self)
        ):
            raise ValueError("projection_digest does not match safe scene projection")
        return self


class StoryboardSceneVideoSetSummaryV1(BaseModel):
    """Browser-safe projection of the server-only scene video set receipt."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryboardSceneVideoSetSummary.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    plan_digest: DigestStr
    storyboard_execution_manifest_digest: DigestStr
    final_production_authority_digest: DigestStr
    storyboard_scene_count: StoryboardSceneCount
    beat_projections: tuple[StoryboardBeatSceneProjectionSummaryV1, ...] = Field(
        min_length=16,
        max_length=16,
    )
    completed_at_utc: UtcTimestamp
    scene_video_set_receipt_digest: DigestStr
    summary_digest: DigestStr

    @field_validator("beat_projections", mode="before")
    @classmethod
    def _projections_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _bind_safe_projection(self) -> "StoryboardSceneVideoSetSummaryV1":
        if [item.sequence_index for item in self.beat_projections] != list(range(16)):
            raise ValueError("safe beat projections must be ordered 0..15")
        if sorted(item.source_beat_index for item in self.beat_projections) != list(
            range(16)
        ):
            raise ValueError("safe beat projections must cover source beats 0..15")
        seen_scenes: list[int] = []
        expected_repeat = 0
        current_scene = -1
        for projection in self.beat_projections:
            if projection.scene_sequence_index == current_scene + 1:
                current_scene += 1
                seen_scenes.append(current_scene)
                expected_repeat = 0
            elif projection.scene_sequence_index != current_scene:
                raise ValueError("safe scene projections must be contiguous and dense")
            if projection.repeat_index != expected_repeat:
                raise ValueError("safe repeat_index must be dense within each scene")
            expected_repeat += 1
        if seen_scenes != list(range(self.storyboard_scene_count)):
            raise ValueError("safe projections must reference every scene exactly")
        if self.summary_digest != (
            derive_storyboard_scene_video_set_summary_digest_v1(self)
        ):
            raise ValueError("summary_digest does not match scene video set summary")
        return self

    @classmethod
    def from_receipt(
        cls,
        receipt: StoryboardSceneVideoSetReceiptV1,
        *,
        manifest: "StoryboardExecutionManifestV1",
        authority: object,
        operation_proofs: tuple[object, ...],
    ) -> "StoryboardSceneVideoSetSummaryV1":
        if not receipt.binds(manifest, authority, operation_proofs):
            raise ValueError(
                "scene video summary requires verified live or historical proof"
            )
        projections: list[dict[str, Any]] = []
        for item in receipt.beat_projections:
            body: dict[str, Any] = {
                "contract_version": "StoryboardBeatSceneProjectionSummary.v1",
                "sequence_index": item.sequence_index,
                "source_beat_index": item.source_beat_index,
                "scene_sequence_index": item.scene_sequence_index,
                "scene_digest": item.scene_digest,
                "repeat_index": item.repeat_index,
            }
            body["projection_digest"] = (
                derive_storyboard_beat_scene_projection_summary_digest_v1(body)
            )
            projections.append(body)
        body = {
            "contract_version": "StoryboardSceneVideoSetSummary.v1",
            "workspace_id": receipt.workspace_id,
            "run_id": receipt.run_id,
            "factory_revision": receipt.factory_revision,
            "plan_digest": receipt.plan_digest,
            "storyboard_execution_manifest_digest": (
                receipt.storyboard_execution_manifest_digest
            ),
            "final_production_authority_digest": (
                receipt.final_production_authority_digest
            ),
            "storyboard_scene_count": receipt.storyboard_scene_count,
            "beat_projections": projections,
            "completed_at_utc": receipt.completed_at_utc,
            "scene_video_set_receipt_digest": receipt.receipt_digest,
        }
        body["summary_digest"] = derive_storyboard_scene_video_set_summary_digest_v1(
            body
        )
        return cls.model_validate(body)

    def binds(
        self,
        receipt: StoryboardSceneVideoSetReceiptV1,
        *,
        manifest: "StoryboardExecutionManifestV1",
        authority: object,
        operation_proofs: tuple[object, ...],
    ) -> bool:
        return self == self.from_receipt(
            receipt,
            manifest=manifest,
            authority=authority,
            operation_proofs=operation_proofs,
        )


class StoryboardBeatCaptionV1(BaseModel):
    """One approved beat caption retained independently from scene grouping."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryboardBeatCaption.v1"]
    source_beat_index: StoryboardBeatIndex
    sequence_index: StoryboardBeatIndex
    text_content: CaptionText
    duration_ms: Literal[4_000]
    caption_digest: DigestStr

    @model_validator(mode="after")
    def _bind_caption_digest(self) -> "StoryboardBeatCaptionV1":
        if self.caption_digest != derive_storyboard_beat_caption_digest_v1(self):
            raise ValueError("caption_digest does not match beat caption")
        return self


class StoryboardSceneFanInManifestV1(BaseModel):
    """Render input joining shared scene videos to sixteen beat voices."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryboardSceneFanInManifest.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    plan_digest: DigestStr
    paid_budget_authority_digest: DigestStr
    storyboard_execution_manifest_digest: DigestStr
    storyboard_scene_video_set_receipt: StoryboardSceneVideoSetReceiptV1
    storyboard_scene_video_set_receipt_digest: DigestStr
    audio_artifacts: tuple[StrictAllBeatArtifactRefV1, ...] = Field(
        min_length=16,
        max_length=16,
    )
    captions: tuple[StoryboardBeatCaptionV1, ...] = Field(
        min_length=16,
        max_length=16,
    )
    caption_set_digest: DigestStr
    timeline_digest: DigestStr
    audio_mix_digest: DigestStr
    render_policy_digest: DigestStr
    manifest_digest: DigestStr

    @field_validator("audio_artifacts", "captions", mode="before")
    @classmethod
    def _audio_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _bind_fan_in(self) -> "StoryboardSceneFanInManifestV1":
        scene_set = self.storyboard_scene_video_set_receipt
        if (
            scene_set.workspace_id != self.workspace_id
            or scene_set.run_id != self.run_id
            or scene_set.factory_revision != self.factory_revision
            or scene_set.plan_digest != self.plan_digest
            or scene_set.final_production_authority_digest
            != self.paid_budget_authority_digest
            or scene_set.storyboard_execution_manifest_digest
            != self.storyboard_execution_manifest_digest
            or scene_set.receipt_digest
            != self.storyboard_scene_video_set_receipt_digest
        ):
            raise ValueError("scene video set scope or digest does not match fan-in")

        for artifact in self.audio_artifacts:
            _assert_audio_artifact(artifact)
        audio_source_order = [artifact.beat_index for artifact in self.audio_artifacts]
        projection_source_order = [
            item.source_beat_index for item in scene_set.beat_projections
        ]
        if audio_source_order != projection_source_order or sorted(
            audio_source_order
        ) != list(range(_STORYBOARD_BEAT_COUNT)):
            raise ValueError("audio artifacts must match beat projection source order")
        for field in ("artifact_id", "uri", "execution_id"):
            values = [getattr(artifact, field) for artifact in self.audio_artifacts]
            if len(values) != len(set(values)):
                raise ValueError(f"audio artifact {field} values must be unique")

        if [caption.sequence_index for caption in self.captions] != list(range(16)):
            raise ValueError("captions must be in sequence order 0..15")
        if sorted(caption.source_beat_index for caption in self.captions) != list(
            range(16)
        ):
            raise ValueError("captions must cover source beats exactly 0..15")
        if self.caption_set_digest != derive_storyboard_caption_set_digest_v1(
            self.captions
        ):
            raise ValueError("caption_set_digest must bind ordered captions")

        expected_audio_mix_digest = canonical_contract_digest_v1(
            {
                "audio_artifacts": [
                    artifact.model_dump(mode="json")
                    for artifact in self.audio_artifacts
                ]
            }
        )
        if self.audio_mix_digest != expected_audio_mix_digest:
            raise ValueError("audio_mix_digest must bind ordered audio artifacts")
        if self.manifest_digest != (
            derive_storyboard_scene_fan_in_manifest_digest_v1(self)
        ):
            raise ValueError("manifest_digest does not match storyboard scene fan-in")
        return self

    def binds(
        self,
        manifest: "StoryboardExecutionManifestV1",
        authority: object,
        verified_requests: tuple[object, ...],
    ) -> bool:
        resolution = _resolve_terminal_paid_budget_resolution_v2(
            authority,
            verified_requests,
        )
        if resolution is None:
            return False
        paid_authority = resolution.paid_budget_authority
        expected_captions = tuple(
            StoryboardBeatCaptionV1.model_validate(
                {
                    "contract_version": "StoryboardBeatCaption.v1",
                    "source_beat_index": card.source_beat_index,
                    "sequence_index": card.sequence_index,
                    "text_content": card.caption_text,
                    "duration_ms": 4_000,
                    "caption_digest": derive_storyboard_beat_caption_digest_v1(
                        {
                            "contract_version": "StoryboardBeatCaption.v1",
                            "source_beat_index": card.source_beat_index,
                            "sequence_index": card.sequence_index,
                            "text_content": card.caption_text,
                            "duration_ms": 4_000,
                        }
                    ),
                }
            )
            for card in manifest.cards
        )
        return (
            self.workspace_id == manifest.workspace_id
            and self.run_id == manifest.run_id
            and self.factory_revision == manifest.factory_revision
            and self.plan_digest == manifest.plan_digest
            and self.paid_budget_authority_digest == paid_authority.authority_digest
            and self.storyboard_execution_manifest_digest == manifest.manifest_digest
            and paid_authority.storyboard_draft_digest
            == manifest.storyboard_draft_digest
            and paid_authority.storyboard_approval_receipt_digest
            == manifest.storyboard_approval_receipt_digest
            and self.captions == expected_captions
            and self.storyboard_scene_video_set_receipt.binds(
                manifest,
                authority,
                verified_requests,
            )
        )


class ReelsFactoryReceiptV3(BaseModel):
    """Terminal storyboard factory success without all-beat receipt reuse."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["ReelsFactoryReceipt.v3"]
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    plan_digest: DigestStr
    paid_budget_authority_digest: DigestStr
    storyboard_execution_manifest_digest: DigestStr
    storyboard_scene_video_set_receipt_digest: DigestStr
    fan_in_manifest_digest: DigestStr
    fan_in_manifest: StoryboardSceneFanInManifestV1
    final_render_receipt: HephaestusFinalRenderReceiptV2
    status: Literal["succeeded"]
    output_url: NonBlankStr
    output_sha256: DigestStr
    receipt_digest: DigestStr

    @field_validator("output_url")
    @classmethod
    def _durable_output_url(cls, value: str) -> str:
        _assert_https_url(value)
        return value

    @model_validator(mode="after")
    def _bind_terminal_success(self) -> "ReelsFactoryReceiptV3":
        render = self.final_render_receipt
        fan_in = self.fan_in_manifest
        if (
            fan_in.workspace_id != self.workspace_id
            or fan_in.run_id != self.run_id
            or fan_in.factory_revision != self.factory_revision
            or fan_in.plan_digest != self.plan_digest
            or fan_in.paid_budget_authority_digest != self.paid_budget_authority_digest
            or fan_in.storyboard_execution_manifest_digest
            != self.storyboard_execution_manifest_digest
            or fan_in.storyboard_scene_video_set_receipt_digest
            != self.storyboard_scene_video_set_receipt_digest
            or fan_in.manifest_digest != self.fan_in_manifest_digest
        ):
            raise ValueError("storyboard scene fan-in does not match factory")
        if (
            render.workspace_id != self.workspace_id
            or render.run_id != self.run_id
            or render.factory_revision != self.factory_revision
        ):
            raise ValueError("final render receipt scope does not match factory")
        if render.fan_in_manifest_digest != self.fan_in_manifest_digest:
            raise ValueError(
                "fan_in_manifest_digest does not match final render receipt"
            )
        if render.output_url != self.output_url:
            raise ValueError("output_url does not match final render receipt")
        if render.output_artifact.sha256 != self.output_sha256:
            raise ValueError("output_sha256 does not match final render artifact")
        if self.receipt_digest != derive_reels_factory_receipt_digest_v3(self):
            raise ValueError("receipt_digest does not match reels factory receipt")
        return self

    def binds_scene_video_set(
        self,
        receipt: StoryboardSceneVideoSetReceiptV1,
    ) -> bool:
        return (
            self.workspace_id == receipt.workspace_id
            and self.run_id == receipt.run_id
            and self.factory_revision == receipt.factory_revision
            and self.plan_digest == receipt.plan_digest
            and self.paid_budget_authority_digest
            == receipt.final_production_authority_digest
            and self.storyboard_execution_manifest_digest
            == receipt.storyboard_execution_manifest_digest
            and self.storyboard_scene_video_set_receipt_digest == receipt.receipt_digest
            and self.fan_in_manifest.storyboard_scene_video_set_receipt == receipt
        )

    def binds_chain(
        self,
        fan_in: StoryboardSceneFanInManifestV1,
        scene_video_set: StoryboardSceneVideoSetReceiptV1,
        *,
        manifest: "StoryboardExecutionManifestV1",
        authority: object,
        verified_requests: tuple[object, ...],
    ) -> bool:
        return (
            self.fan_in_manifest == fan_in
            and self.fan_in_manifest_digest == fan_in.manifest_digest
            and fan_in.storyboard_scene_video_set_receipt == scene_video_set
            and fan_in.storyboard_scene_video_set_receipt_digest
            == scene_video_set.receipt_digest
            and self.binds_scene_video_set(scene_video_set)
            and self.final_render_receipt.fan_in_manifest_digest
            == fan_in.manifest_digest
            and fan_in.binds(manifest, authority, verified_requests)
        )


class ReelsFactoryCompletionSummaryV3(BaseModel):
    """Browser-safe terminal output; full fan-in/provider proof stays server-only."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["ReelsFactoryCompletionSummary.v3"]
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    plan_digest: DigestStr
    paid_budget_authority_digest: DigestStr
    storyboard_execution_manifest_digest: DigestStr
    storyboard_scene_video_set_receipt_digest: DigestStr
    storyboard_scene_video_set_summary_digest: DigestStr
    fan_in_manifest_digest: DigestStr
    final_render_receipt_digest: DigestStr
    rendered_at_utc: UtcTimestamp
    status: Literal["succeeded"]
    output_url: NonBlankStr
    output_sha256: DigestStr
    factory_receipt_digest: DigestStr
    summary_digest: DigestStr

    @field_validator("output_url")
    @classmethod
    def _durable_output_url(cls, value: str) -> str:
        _assert_https_url(value)
        return value

    @model_validator(mode="after")
    def _bind_summary_digest(self) -> "ReelsFactoryCompletionSummaryV3":
        if self.summary_digest != derive_reels_factory_completion_summary_digest_v3(
            self
        ):
            raise ValueError("summary_digest does not match factory completion")
        return self

    @classmethod
    def from_receipt(
        cls,
        receipt: ReelsFactoryReceiptV3,
        *,
        scene_video_set_summary: StoryboardSceneVideoSetSummaryV1,
        manifest: "StoryboardExecutionManifestV1",
        authority: object,
        operation_proofs: tuple[object, ...],
    ) -> "ReelsFactoryCompletionSummaryV3":
        scene_set = receipt.fan_in_manifest.storyboard_scene_video_set_receipt
        if not receipt.binds_chain(
            receipt.fan_in_manifest,
            scene_set,
            manifest=manifest,
            authority=authority,
            verified_requests=operation_proofs,
        ) or not scene_video_set_summary.binds(
            scene_set,
            manifest=manifest,
            authority=authority,
            operation_proofs=operation_proofs,
        ):
            raise ValueError("factory summary requires verified terminal proof chain")
        body: dict[str, Any] = {
            "contract_version": "ReelsFactoryCompletionSummary.v3",
            "workspace_id": receipt.workspace_id,
            "run_id": receipt.run_id,
            "factory_revision": receipt.factory_revision,
            "plan_digest": receipt.plan_digest,
            "paid_budget_authority_digest": receipt.paid_budget_authority_digest,
            "storyboard_execution_manifest_digest": (
                receipt.storyboard_execution_manifest_digest
            ),
            "storyboard_scene_video_set_receipt_digest": (
                receipt.storyboard_scene_video_set_receipt_digest
            ),
            "storyboard_scene_video_set_summary_digest": (
                scene_video_set_summary.summary_digest
            ),
            "fan_in_manifest_digest": receipt.fan_in_manifest_digest,
            "final_render_receipt_digest": (
                receipt.final_render_receipt.receipt_digest
            ),
            "rendered_at_utc": receipt.final_render_receipt.rendered_at_utc,
            "status": receipt.status,
            "output_url": receipt.output_url,
            "output_sha256": receipt.output_sha256,
            "factory_receipt_digest": receipt.receipt_digest,
        }
        body["summary_digest"] = derive_reels_factory_completion_summary_digest_v3(body)
        return cls.model_validate(body)

    def binds(
        self,
        receipt: ReelsFactoryReceiptV3,
        *,
        scene_video_set_summary: StoryboardSceneVideoSetSummaryV1,
        manifest: "StoryboardExecutionManifestV1",
        authority: object,
        operation_proofs: tuple[object, ...],
    ) -> bool:
        return self == self.from_receipt(
            receipt,
            scene_video_set_summary=scene_video_set_summary,
            manifest=manifest,
            authority=authority,
            operation_proofs=operation_proofs,
        )


def _assert_card_permutations(
    cards: tuple[StoryboardCardV1, ...],
    *,
    plan_digest: str,
) -> None:
    if len(cards) != _STORYBOARD_BEAT_COUNT:
        raise ValueError("cards must contain exactly 16 entries")
    if [card.sequence_index for card in cards] != list(range(_STORYBOARD_BEAT_COUNT)):
        raise ValueError("card sequence indices must be exactly 0..15 in array order")
    source_indices = [card.source_beat_index for card in cards]
    if sorted(source_indices) != list(range(_STORYBOARD_BEAT_COUNT)):
        raise ValueError("card source beat indices must be a permutation of 0..15")
    total_duration_ms = sum(card.duration_ms for card in cards)
    if not 45_000 <= total_duration_ms <= 55_000:
        raise ValueError("storyboard duration must be between 45 and 55 seconds")
    selected_ids = [card.selected_artifact.artifact_id for card in cards]
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("selected artifact ids must be unique across cards")
    for card in cards:
        expected_identity = derive_storyboard_beat_identity_digest_v1(
            plan_digest,
            card.source_beat_index,
            card.voice_text,
            card.caption_text,
        )
        if card.beat_identity_digest != expected_identity:
            raise ValueError(
                "beat_identity_digest does not match immutable source beat"
            )
    derive_storyboard_scenes_v1(cards)


class StoryboardDraftV1(BaseModel):
    """CAS-addressable editor state; every edit creates a new revision."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryboardDraft.v1"]
    draft_id: UuidStr
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    plan_digest: DigestStr
    image_set_receipt_digest: DigestStr
    revision: RevisionInt
    parent_draft_digest: DigestStr | None
    cards: tuple[StoryboardCardV1, ...] = Field(min_length=16, max_length=16)
    draft_digest: DigestStr

    @field_validator("cards", mode="before")
    @classmethod
    def _cards_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _bind_draft(self) -> "StoryboardDraftV1":
        if self.revision == 1 and self.parent_draft_digest is not None:
            raise ValueError("parent_draft_digest must be null for revision 1")
        if self.revision > 1 and self.parent_draft_digest is None:
            raise ValueError("parent_draft_digest is required after revision 1")
        _assert_card_permutations(self.cards, plan_digest=self.plan_digest)
        if self.draft_digest != derive_storyboard_draft_digest_v1(self):
            raise ValueError("draft_digest does not match storyboard draft")
        return self

    def binds_image_set(self, image_set: StoryboardImageSetReceiptV1) -> bool:
        """Bind the immutable base set; selections may be server-verified replacements."""

        return (
            self.workspace_id == image_set.workspace_id
            and self.run_id == image_set.run_id
            and self.factory_revision == image_set.factory_revision
            and self.plan_digest == image_set.plan_digest
            and self.image_set_receipt_digest == image_set.receipt_digest
        )

    def is_valid_successor_of(
        self,
        previous: "StoryboardDraftV1",
        *,
        replacement_image_set: StoryboardImageSetReceiptV1 | None = None,
    ) -> bool:
        image_set_matches = (
            self.image_set_receipt_digest == previous.image_set_receipt_digest
            if replacement_image_set is None
            else self.binds_image_set(replacement_image_set)
        )
        if not (
            self.draft_id == previous.draft_id
            and self.workspace_id == previous.workspace_id
            and self.run_id == previous.run_id
            and self.factory_revision == previous.factory_revision
            and self.plan_digest == previous.plan_digest
            and image_set_matches
            and self.revision == previous.revision + 1
            and self.parent_draft_digest == previous.draft_digest
        ):
            return False

        return True


class StoryboardApprovalReceiptV1(BaseModel):
    """Human approval evidence bound to the exact current draft and base set."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryboardApprovalReceipt.v1"]
    receipt_id: NonBlankStr
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    plan_digest: DigestStr
    draft_id: UuidStr
    draft_revision: RevisionInt
    storyboard_draft_digest: DigestStr
    image_set_receipt_digest: DigestStr
    approver_account_id: NonBlankStr
    decision: Literal["approved"]
    policy_version: NonBlankStr
    approved_at_utc: UtcTimestamp
    transaction_audit_id: NonBlankStr
    receipt_digest: DigestStr

    @model_validator(mode="after")
    def _bind_receipt(self) -> "StoryboardApprovalReceiptV1":
        if self.transaction_audit_id != self.receipt_id:
            raise ValueError("transaction_audit_id must equal receipt_id")
        if self.receipt_digest != derive_storyboard_approval_receipt_digest_v1(self):
            raise ValueError("receipt_digest does not match storyboard approval")
        return self

    def binds(
        self,
        draft: StoryboardDraftV1,
        image_set: StoryboardImageSetReceiptV1,
    ) -> bool:
        return (
            draft.binds_image_set(image_set)
            and self.workspace_id == draft.workspace_id
            and self.run_id == draft.run_id
            and self.factory_revision == draft.factory_revision
            and self.plan_digest == draft.plan_digest
            and self.draft_id == draft.draft_id
            and self.draft_revision == draft.revision
            and self.storyboard_draft_digest == draft.draft_digest
            and self.image_set_receipt_digest == image_set.receipt_digest
        )


class FactoryPaidCallCardinalityV2(BaseModel):
    """Zero-capable lane ceilings with no implicit retry or fallback spend."""

    model_config = _FROZEN_STRICT

    script: Annotated[int, Field(ge=0, le=1)]
    image: Annotated[int, Field(ge=0, le=16)]
    video: Annotated[int, Field(ge=0, le=16)]
    voice: Annotated[int, Field(ge=0, le=16)]
    render: Annotated[int, Field(ge=0, le=1)]
    retries: Literal[0]
    fallbacks: Literal[0]
    character_lock: Literal[0]


def factory_paid_call_cardinality_v2(
    purpose: FactoryPaidBudgetPurposeV2,
    *,
    regen_image_count: int | None = None,
    storyboard_scene_count: int | None = None,
) -> dict[str, int]:
    if purpose == "storyboard_draft":
        if storyboard_scene_count is not None:
            raise ValueError("storyboard_draft cannot carry storyboard_scene_count")
        calls = (1, 16, 0, 0, 0)
    elif purpose == "storyboard_regen":
        if storyboard_scene_count is not None:
            raise ValueError("storyboard_regen cannot carry storyboard_scene_count")
        if (
            isinstance(regen_image_count, bool)
            or not isinstance(regen_image_count, int)
            or not 1 <= regen_image_count <= 16
        ):
            raise ValueError("regen_image_count must be an integer from 1 to 16")
        calls = (0, regen_image_count, 0, 0, 0)
    elif purpose == "final_production":
        if (
            isinstance(storyboard_scene_count, bool)
            or not isinstance(storyboard_scene_count, int)
            or not 1 <= storyboard_scene_count <= 16
        ):
            raise ValueError("storyboard_scene_count must be an integer from 1 to 16")
        calls = (0, 0, storyboard_scene_count, 16, 1)
    else:
        raise ValueError("unsupported paid budget purpose")
    return {
        "script": calls[0],
        "image": calls[1],
        "video": calls[2],
        "voice": calls[3],
        "render": calls[4],
        "retries": 0,
        "fallbacks": 0,
        "character_lock": 0,
    }


def _expected_paid_phase_calls_v2(
    *,
    purpose: FactoryPaidBudgetPurposeV2,
    plan_digest: str | None,
    storyboard_draft_digest: str | None,
    storyboard_approval_receipt_digest: str | None,
    storyboard_scene_count: int | None,
    image_source_beat_indices: tuple[int, ...],
) -> dict[str, int]:
    indices = image_source_beat_indices
    if purpose == "storyboard_draft":
        if (
            plan_digest is not None
            or indices != tuple(range(_STORYBOARD_BEAT_COUNT))
            or storyboard_draft_digest is not None
            or storyboard_approval_receipt_digest is not None
            or storyboard_scene_count is not None
        ):
            raise ValueError(
                "storyboard_draft must be pre-plan, cover 0..15, and have no "
                "draft/approval/storyboard_scene_count refs"
            )
        return factory_paid_call_cardinality_v2(purpose)
    if purpose == "storyboard_regen":
        if (
            plan_digest is None
            or not indices
            or len(indices) != len(set(indices))
            or tuple(sorted(indices)) != indices
            or storyboard_draft_digest is None
            or storyboard_approval_receipt_digest is not None
            or storyboard_scene_count is not None
        ):
            raise ValueError(
                "storyboard_regen requires a plan, sorted unique source beats, "
                "one draft ref, and no approval/storyboard_scene_count ref"
            )
        return factory_paid_call_cardinality_v2(
            purpose,
            regen_image_count=len(indices),
        )
    if (
        plan_digest is None
        or indices
        or storyboard_draft_digest is None
        or storyboard_approval_receipt_digest is None
        or storyboard_scene_count is None
    ):
        raise ValueError(
            "final_production requires a plan, current draft and approval refs, "
            "one storyboard_scene_count, and no image generation scope"
        )
    return factory_paid_call_cardinality_v2(
        purpose,
        storyboard_scene_count=storyboard_scene_count,
    )


class FactoryPaidBudgetAuthorityV2(BaseModel):
    """One exact paid phase; draft, regen, and final production never overlap."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["FactoryPaidBudgetAuthority.v2"]
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    all_beat_count: Literal[16]
    purpose: FactoryPaidBudgetPurposeV2
    plan_digest: DigestStr | None
    storyboard_draft_digest: DigestStr | None
    storyboard_approval_receipt_digest: DigestStr | None
    storyboard_scene_count: StoryboardSceneCount | None
    image_source_beat_indices: tuple[StoryboardBeatIndex, ...] = Field(max_length=16)
    paid_calls: FactoryPaidCallCardinalityV2
    max_total_cost_microunits: PositiveSafeInt
    currency: CurrencyCode
    cost_profile_digest: DigestStr
    pricing_policy_revision: NonNegativeInt
    approval_receipt_id: NonBlankStr
    approval_receipt_digest: DigestStr
    approval_subject_digest: DigestStr
    idempotency_key: DigestStr
    authority_digest: DigestStr

    @field_validator("image_source_beat_indices", mode="before")
    @classmethod
    def _indices_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _bind_exact_phase(self) -> "FactoryPaidBudgetAuthorityV2":
        expected_calls = _expected_paid_phase_calls_v2(
            purpose=self.purpose,
            plan_digest=self.plan_digest,
            storyboard_draft_digest=self.storyboard_draft_digest,
            storyboard_approval_receipt_digest=(
                self.storyboard_approval_receipt_digest
            ),
            storyboard_scene_count=self.storyboard_scene_count,
            image_source_beat_indices=self.image_source_beat_indices,
        )

        if self.paid_calls.model_dump() != expected_calls:
            raise ValueError("paid_calls do not match exact authority purpose")
        if self.approval_subject_digest != (
            derive_factory_paid_budget_approval_subject_digest_v2(self)
        ):
            raise ValueError("approval_subject_digest does not match paid scope")
        if self.idempotency_key != derive_factory_paid_budget_idempotency_key_v2(self):
            raise ValueError("idempotency_key does not match paid authority")
        if self.authority_digest != derive_factory_paid_budget_authority_digest_v2(
            self
        ):
            raise ValueError("authority_digest does not match paid authority")
        return self


_VERIFIED_AUTHORITY_TOKEN_V2 = object()
_VERIFIED_AUTHORITY_REGISTRY_V2: WeakKeyDictionary[object, object] = WeakKeyDictionary()


class VerifiedFactoryPaidBudgetAuthorityV2:
    """Non-serializable in-process capability minted from current V2 approval."""

    __slots__ = ("__weakref__",)

    def __init__(
        self,
        resolution: object,
        *,
        _token: object,
    ) -> None:
        if _token is not _VERIFIED_AUTHORITY_TOKEN_V2:
            raise TypeError(
                "verified authority can only be minted by resolution.from_verified"
            )
        _VERIFIED_AUTHORITY_REGISTRY_V2[self] = resolution

    @property
    def authority(self) -> FactoryPaidBudgetAuthorityV2:
        return _unwrap_verified_factory_paid_budget_authority_v2(self)

    @property
    def cost_profile(self) -> "FactoryCostProfileV1":
        return _unwrap_verified_factory_paid_budget_resolution_v2(self).cost_profile

    @property
    def approval_receipt(self) -> "FactoryPaidBudgetApprovalReceiptV2":
        return _unwrap_verified_factory_paid_budget_resolution_v2(self).approval_receipt

    def __setattr__(self, _name: str, _value: object) -> None:
        raise TypeError("verified paid authority is immutable")

    def __delattr__(self, _name: str) -> None:
        raise TypeError("verified paid authority is immutable")

    def __copy__(self) -> object:
        raise TypeError("verified paid authority cannot be copied")

    def __deepcopy__(self, _memo: dict[int, object]) -> object:
        raise TypeError("verified paid authority cannot be copied")

    def __reduce_ex__(self, _protocol: int) -> object:
        raise TypeError("verified paid authority is not serializable")

    def __repr__(self) -> str:
        return "VerifiedFactoryPaidBudgetAuthorityV2(<sealed>)"


def _unwrap_verified_factory_paid_budget_authority_v2(
    capability: object,
) -> FactoryPaidBudgetAuthorityV2:
    return _unwrap_verified_factory_paid_budget_resolution_v2(
        capability
    ).paid_budget_authority


def _unwrap_verified_factory_paid_budget_resolution_v2(
    capability: object,
) -> "FactoryPaidBudgetResolutionV2":
    if not isinstance(capability, VerifiedFactoryPaidBudgetAuthorityV2):
        raise TypeError("execution requires VerifiedFactoryPaidBudgetAuthorityV2")
    try:
        resolution = _VERIFIED_AUTHORITY_REGISTRY_V2[capability]
    except KeyError as exc:
        raise TypeError("unminted verified paid authority capability") from exc
    if not isinstance(resolution, FactoryPaidBudgetResolutionV2):
        raise TypeError("paid authority capability is not profile-resolved")
    return resolution


class FactoryPaidBudgetApprovalReceiptV2(BaseModel):
    """Wire approval evidence; it is not bearer authority without a resolver."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["FactoryPaidBudgetApprovalReceipt.v2"]
    receipt_id: NonBlankStr
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    all_beat_count: Literal[16]
    purpose: FactoryPaidBudgetPurposeV2
    plan_digest: DigestStr | None
    storyboard_draft_digest: DigestStr | None
    storyboard_approval_receipt_digest: DigestStr | None
    storyboard_scene_count: StoryboardSceneCount | None
    image_source_beat_indices: tuple[StoryboardBeatIndex, ...] = Field(max_length=16)
    paid_calls: FactoryPaidCallCardinalityV2
    max_total_cost_microunits: PositiveSafeInt
    currency: CurrencyCode
    cost_profile_digest: DigestStr
    pricing_policy_revision: NonNegativeInt
    approval_subject_digest: DigestStr
    approver_account_id: NonBlankStr
    decision: Literal["approved"]
    policy_version: Literal["factory-paid-budget.v2"]
    state_revision: PositiveSafeInt
    approved_at_utc: UtcTimestamp
    expires_at_utc: UtcTimestamp
    revoked_at_utc: UtcTimestamp | None
    transaction_audit_id: NonBlankStr
    receipt_digest: DigestStr

    @field_validator("image_source_beat_indices", mode="before")
    @classmethod
    def _indices_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _bind_receipt(self) -> "FactoryPaidBudgetApprovalReceiptV2":
        if self.transaction_audit_id != self.receipt_id:
            raise ValueError("transaction_audit_id must equal receipt_id")
        expected_calls = _expected_paid_phase_calls_v2(
            purpose=self.purpose,
            plan_digest=self.plan_digest,
            storyboard_draft_digest=self.storyboard_draft_digest,
            storyboard_approval_receipt_digest=(
                self.storyboard_approval_receipt_digest
            ),
            storyboard_scene_count=self.storyboard_scene_count,
            image_source_beat_indices=self.image_source_beat_indices,
        )
        if self.paid_calls.model_dump() != expected_calls:
            raise ValueError("paid_calls do not match exact approval purpose")
        if self.approval_subject_digest != (
            derive_factory_paid_budget_approval_subject_digest_v2(self)
        ):
            raise ValueError("approval_subject_digest does not match paid scope")
        approved = _parse_utc(self.approved_at_utc)
        expires = _parse_utc(self.expires_at_utc)
        if expires <= approved:
            raise ValueError("expires_at_utc must follow approved_at_utc")
        if self.revoked_at_utc is not None:
            revoked = _parse_utc(self.revoked_at_utc)
            if revoked < approved or revoked > expires:
                raise ValueError("revoked_at_utc must fall within approval lifetime")
        if self.receipt_digest != (
            derive_factory_paid_budget_approval_receipt_digest_v2(self)
        ):
            raise ValueError("receipt_digest does not match approval receipt")
        return self

    def structurally_binds(self, authority: FactoryPaidBudgetAuthorityV2) -> bool:
        return (
            self.receipt_id == authority.approval_receipt_id
            and self.receipt_digest == authority.approval_receipt_digest
            and self.workspace_id == authority.workspace_id
            and self.run_id == authority.run_id
            and self.factory_revision == authority.factory_revision
            and self.all_beat_count == authority.all_beat_count
            and self.purpose == authority.purpose
            and self.plan_digest == authority.plan_digest
            and self.storyboard_draft_digest == authority.storyboard_draft_digest
            and self.storyboard_approval_receipt_digest
            == authority.storyboard_approval_receipt_digest
            and self.storyboard_scene_count == authority.storyboard_scene_count
            and self.image_source_beat_indices == authority.image_source_beat_indices
            and self.paid_calls == authority.paid_calls
            and self.max_total_cost_microunits == authority.max_total_cost_microunits
            and self.currency == authority.currency
            and self.cost_profile_digest == authority.cost_profile_digest
            and self.pricing_policy_revision == authority.pricing_policy_revision
            and self.approval_subject_digest == authority.approval_subject_digest
        )

    def authorizes(
        self,
        authority: FactoryPaidBudgetAuthorityV2,
        *,
        at_utc: str,
        resolver: FactoryPaidBudgetApprovalResolverV2,
    ) -> bool:
        if not self.structurally_binds(authority):
            return False
        at = _parse_utc(at_utc)
        if (
            at < _parse_utc(self.approved_at_utc)
            or at >= _parse_utc(self.expires_at_utc)
            or self.revoked_at_utc is not None
        ):
            return False
        return resolver.is_current_approval(
            receipt_id=self.receipt_id,
            receipt_digest=self.receipt_digest,
            workspace_id=self.workspace_id,
            run_id=self.run_id,
            factory_revision=self.factory_revision,
            state_revision=self.state_revision,
            policy_version=self.policy_version,
            approval_subject_digest=self.approval_subject_digest,
            approver_account_id=self.approver_account_id,
            cost_profile_digest=self.cost_profile_digest,
            pricing_policy_revision=self.pricing_policy_revision,
            purpose=self.purpose,
            plan_digest=self.plan_digest,
            storyboard_draft_digest=self.storyboard_draft_digest,
            storyboard_approval_receipt_digest=(
                self.storyboard_approval_receipt_digest
            ),
            storyboard_scene_count=self.storyboard_scene_count,
            image_source_beat_indices=self.image_source_beat_indices,
        )


class FactoryCostOperationV1(BaseModel):
    """One priced provider operation with an explicit billing identity."""

    model_config = _FROZEN_STRICT

    provider: NonBlankStr
    model: NonBlankStr
    billing_unit: Literal["call", "second", "character"]
    rate_microunits: PositiveSafeInt
    max_units_per_operation: PositiveSafeInt


_FACTORY_COST_OPERATION_POLICY_V1: dict[
    str,
    tuple[str, tuple[str, ...], str, int, int],
] = {
    "script": ("openai", ("gpt-5.6-sol",), "call", 2_000_000, 1),
    "image": ("seedream", ("seedream-5-pro",), "call", 1_000_000, 1),
    "video": (
        "piapi",
        ("seedance-2-fast", "kling-3.0-omni"),
        "second",
        160_000,
        4,
    ),
    "voice": ("typecast", ("ssfm-v30",), "character", 90, 200),
    "render": (
        "modal",
        ("hephaestus-final-render-v2",),
        "call",
        2_000_000,
        1,
    ),
}


class FactoryCostOperationsV1(BaseModel):
    """The exact five paid operation tracks understood by Factory V1 profiles."""

    model_config = _FROZEN_STRICT

    script: FactoryCostOperationV1
    image: FactoryCostOperationV1
    video: FactoryCostOperationV1
    voice: FactoryCostOperationV1
    render: FactoryCostOperationV1

    @model_validator(mode="after")
    def _bind_pricing_identities(self) -> "FactoryCostOperationsV1":
        for track, policy in _FACTORY_COST_OPERATION_POLICY_V1.items():
            provider, models, unit, maximum_rate, maximum_units = policy
            operation = getattr(self, track)
            if (
                operation.provider != provider
                or operation.model not in models
                or operation.billing_unit != unit
                or operation.rate_microunits > maximum_rate
                or operation.max_units_per_operation != maximum_units
            ):
                raise ValueError(
                    f"{track} operation pricing identity is not an allowed "
                    "FactoryCostProfile.v1 operation"
                )
        return self


class FactoryStoryboardDraftCostPolicyV1(BaseModel):
    model_config = _FROZEN_STRICT

    script: Literal[1]
    image: Literal[16]
    video: Literal[0]
    voice: Literal[0]
    render: Literal[0]


class FactoryStoryboardRegenCostPolicyV1(BaseModel):
    model_config = _FROZEN_STRICT

    script: Literal[0]
    image: Literal["selected"]
    video: Literal[0]
    voice: Literal[0]
    render: Literal[0]


class FactoryFinalProductionCostPolicyV1(BaseModel):
    model_config = _FROZEN_STRICT

    script: Literal[0]
    image: Literal[0]
    video: Literal["approved_scene_count"]
    voice: Literal[16]
    render: Literal[1]


class FactoryCostPurposePoliciesV1(BaseModel):
    """Exact purpose selectors used by the current two-stage factory."""

    model_config = _FROZEN_STRICT

    storyboard_draft: FactoryStoryboardDraftCostPolicyV1
    storyboard_regen: FactoryStoryboardRegenCostPolicyV1
    final_production: FactoryFinalProductionCostPolicyV1


class FactoryCostProfileV1(BaseModel):
    """Typed cost truth; legacy V1 profiles may omit purpose policy fields."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["FactoryCostProfile.v1"]
    profile_id: NonBlankStr
    currency: CurrencyCode
    pricing_policy_revision: PositiveSafeInt
    valid_from_utc: UtcTimestamp
    valid_until_utc: UtcTimestamp
    all_beat_count: Literal[16] | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    purpose_policies: FactoryCostPurposePoliciesV1 | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    operations: FactoryCostOperationsV1
    profile_digest: DigestStr

    @model_validator(mode="after")
    def _bind_profile(self) -> "FactoryCostProfileV1":
        if (self.all_beat_count is None) != (self.purpose_policies is None):
            raise ValueError(
                "all_beat_count and purpose policies must be present together"
            )
        if _parse_utc(self.valid_until_utc) <= _parse_utc(self.valid_from_utc):
            raise ValueError("valid_until_utc must follow valid_from_utc")
        if self.profile_digest != derive_factory_cost_profile_digest_v1(self):
            raise ValueError("profile_digest does not match cost_profile")
        return self

    def is_valid_at(self, at_utc: str) -> bool:
        at = _parse_utc(at_utc)
        return _parse_utc(self.valid_from_utc) <= at < _parse_utc(self.valid_until_utc)

    def worst_case_cost_microunits(
        self,
        paid_calls: FactoryPaidCallCardinalityV2,
    ) -> int:
        """Price the exact no-retry paid mask at each operation's unit ceiling."""

        calls = paid_calls.model_dump(mode="python")
        return sum(
            calls[track]
            * getattr(self.operations, track).rate_microunits
            * getattr(self.operations, track).max_units_per_operation
            for track in ("script", "image", "video", "voice", "render")
        )


class FactoryPaidBudgetResolutionV2(BaseModel):
    """Exact DB/BFF resolution envelope for a current V2 paid authority."""

    model_config = _FROZEN_STRICT

    approval_receipt: FactoryPaidBudgetApprovalReceiptV2
    paid_budget_authority: FactoryPaidBudgetAuthorityV2
    cost_profile: FactoryCostProfileV1

    @model_validator(mode="after")
    def _bind_resolution(self) -> "FactoryPaidBudgetResolutionV2":
        authority = self.paid_budget_authority
        if not self.approval_receipt.structurally_binds(authority):
            raise ValueError("approval_receipt does not bind paid_budget_authority")
        profile = self.cost_profile
        if profile.all_beat_count != 16 or profile.purpose_policies is None:
            raise ValueError("cost_profile requires current two-stage purpose policies")
        if (
            profile.currency != "USD"
            or authority.currency != "USD"
            or self.approval_receipt.currency != "USD"
        ):
            raise ValueError("V2 paid execution currency requires USD cost truth")
        if (
            profile.profile_digest != authority.cost_profile_digest
            or profile.pricing_policy_revision != authority.pricing_policy_revision
        ):
            raise ValueError("cost_profile does not match paid authority")
        if profile.currency != authority.currency:
            raise ValueError("cost_profile currency does not match paid authority")
        if authority.max_total_cost_microunits != (
            profile.worst_case_cost_microunits(authority.paid_calls)
        ):
            raise ValueError("paid authority cost cap does not match cost_profile")
        return self

    def from_verified(
        self,
        *,
        at_utc: str,
        resolver: FactoryPaidBudgetApprovalResolverV2,
    ) -> VerifiedFactoryPaidBudgetAuthorityV2:
        if not self.cost_profile.is_valid_at(at_utc):
            raise ValueError("paid execution requires a current cost profile")
        if not self.approval_receipt.authorizes(
            self.paid_budget_authority,
            at_utc=at_utc,
            resolver=resolver,
        ):
            raise ValueError("authority requires current durable approval")
        return VerifiedFactoryPaidBudgetAuthorityV2(
            self,
            _token=_VERIFIED_AUTHORITY_TOKEN_V2,
        )


class FactoryPaidOperationHistoricalEvidenceV2(BaseModel):
    """Server-only evidence for a completed paid operation after currentness ends.

    This wire is reconciliation evidence only.  Its verified capability is
    intentionally rejected by every provider adapter gate.
    """

    model_config = _FROZEN_STRICT

    contract_version: Literal["FactoryPaidOperationHistoricalEvidence.v2"]
    evidence_id: NonBlankStr
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    purpose: FactoryPaidBudgetPurposeV2
    operation: Literal["script", "image", "video", "voice", "render"]
    source_index: StoryboardBeatIndex | None
    resolution: FactoryPaidBudgetResolutionV2
    paid_budget_authority_digest: DigestStr
    cost_profile_digest: DigestStr
    pricing_policy_revision: PositiveSafeInt
    provider: NonBlankStr
    model: NonBlankStr
    operation_key: NonBlankStr
    execution_request_digest: DigestStr
    provider_operation_id: NonBlankStr
    provider_binding_receipt_digest: DigestStr
    provider_result_receipt_id: NonBlankStr
    provider_result_receipt_digest: DigestStr
    provider_result_output_digest: DigestStr
    provider_result_recorded_at_utc: UtcTimestamp
    completed_claim_output_digest: DigestStr
    claim_status: Literal["completed"]
    reserved_at_utc: UtcTimestamp
    completed_at_utc: UtcTimestamp
    evidence_digest: DigestStr

    @model_validator(mode="after")
    def _bind_completed_paid_operation(
        self,
    ) -> "FactoryPaidOperationHistoricalEvidenceV2":
        resolution = self.resolution
        authority = resolution.paid_budget_authority
        approval = resolution.approval_receipt
        profile = resolution.cost_profile
        operation_profile = getattr(profile.operations, self.operation)
        if (
            self.workspace_id != authority.workspace_id
            or self.run_id != authority.run_id
            or self.factory_revision != authority.factory_revision
            or self.purpose != authority.purpose
            or self.paid_budget_authority_digest != authority.authority_digest
            or self.cost_profile_digest != profile.profile_digest
            or self.pricing_policy_revision != profile.pricing_policy_revision
            or self.provider != operation_profile.provider
            or self.model != operation_profile.model
        ):
            raise ValueError("historical evidence does not bind paid resolution")
        if self.operation == "image":
            if (
                authority.purpose not in {"storyboard_draft", "storyboard_regen"}
                or self.source_index is None
                or self.source_index not in authority.image_source_beat_indices
            ):
                raise ValueError("historical image evidence is outside paid scope")
        elif self.operation == "video":
            if (
                authority.purpose != "final_production"
                or authority.storyboard_scene_count is None
                or self.source_index is None
                or self.source_index >= authority.storyboard_scene_count
            ):
                raise ValueError("historical video evidence is outside paid scope")
        elif self.operation == "voice":
            if authority.purpose != "final_production" or self.source_index is None:
                raise ValueError("historical voice evidence is outside paid scope")
        elif self.operation == "script":
            if authority.purpose != "storyboard_draft" or self.source_index is not None:
                raise ValueError("historical script evidence is outside paid scope")
        elif authority.purpose != "final_production" or self.source_index is not None:
            raise ValueError("historical render evidence is outside paid scope")

        reserved = _parse_utc(self.reserved_at_utc)
        provider_result_recorded = _parse_utc(self.provider_result_recorded_at_utc)
        completed = _parse_utc(self.completed_at_utc)
        if not (
            _parse_utc(approval.approved_at_utc)
            <= reserved
            < _parse_utc(approval.expires_at_utc)
            and profile.is_valid_at(self.reserved_at_utc)
        ):
            raise ValueError("historical operation was not reserved in valid windows")
        if approval.revoked_at_utc is not None and reserved >= _parse_utc(
            approval.revoked_at_utc
        ):
            raise ValueError("historical operation was reserved after revocation")
        if not reserved <= provider_result_recorded <= completed:
            raise ValueError("historical result/claim timestamps are out of order")
        if self.provider_result_output_digest != self.completed_claim_output_digest:
            raise ValueError("leaf result and completed claim output must be identical")
        if self.evidence_digest != (
            derive_factory_paid_operation_historical_evidence_digest_v2(self)
        ):
            raise ValueError("evidence_digest does not match historical operation")
        return self

    @classmethod
    def from_verified(
        cls,
        value: Mapping[str, Any] | "FactoryPaidOperationHistoricalEvidenceV2",
        *,
        resolver: FactoryPaidOperationEvidenceResolverV2,
    ) -> "VerifiedFactoryPaidOperationHistoricalEvidenceV2":
        evidence = cls.model_validate(value)
        if not resolver.is_verified_completed_operation(
            evidence_id=evidence.evidence_id,
            evidence_digest=evidence.evidence_digest,
            workspace_id=evidence.workspace_id,
            run_id=evidence.run_id,
            factory_revision=evidence.factory_revision,
            purpose=evidence.purpose,
            operation=evidence.operation,
            source_index=evidence.source_index,
            paid_budget_authority_digest=evidence.paid_budget_authority_digest,
            cost_profile_digest=evidence.cost_profile_digest,
            pricing_policy_revision=evidence.pricing_policy_revision,
            provider=evidence.provider,
            model=evidence.model,
            operation_key=evidence.operation_key,
            execution_request_digest=evidence.execution_request_digest,
            provider_operation_id=evidence.provider_operation_id,
            provider_binding_receipt_digest=(evidence.provider_binding_receipt_digest),
            provider_result_receipt_id=evidence.provider_result_receipt_id,
            provider_result_receipt_digest=evidence.provider_result_receipt_digest,
            provider_result_output_digest=evidence.provider_result_output_digest,
            provider_result_recorded_at_utc=(evidence.provider_result_recorded_at_utc),
            completed_claim_output_digest=evidence.completed_claim_output_digest,
            reserved_at_utc=evidence.reserved_at_utc,
            completed_at_utc=evidence.completed_at_utc,
        ):
            raise ValueError(
                "historical evidence resolver did not verify completed operation"
            )
        return VerifiedFactoryPaidOperationHistoricalEvidenceV2(
            evidence,
            _token=_VERIFIED_HISTORICAL_EVIDENCE_TOKEN_V2,
        )


_VERIFIED_HISTORICAL_EVIDENCE_TOKEN_V2 = object()
_VERIFIED_HISTORICAL_EVIDENCE_REGISTRY_V2: WeakKeyDictionary[object, object] = (
    WeakKeyDictionary()
)


class VerifiedFactoryPaidOperationHistoricalEvidenceV2:
    """Opaque terminal-only proof; it never authorizes a provider call."""

    __slots__ = ("__weakref__",)

    def __init__(self, evidence: object, *, _token: object) -> None:
        if _token is not _VERIFIED_HISTORICAL_EVIDENCE_TOKEN_V2:
            raise TypeError(
                "verified historical evidence can only be minted by from_verified"
            )
        _VERIFIED_HISTORICAL_EVIDENCE_REGISTRY_V2[self] = evidence

    def __setattr__(self, _name: str, _value: object) -> None:
        raise TypeError("verified historical evidence is immutable")

    def __delattr__(self, _name: str) -> None:
        raise TypeError("verified historical evidence is immutable")

    def __copy__(self) -> object:
        raise TypeError("verified historical evidence cannot be copied")

    def __deepcopy__(self, _memo: dict[int, object]) -> object:
        raise TypeError("verified historical evidence cannot be copied")

    def __reduce_ex__(self, _protocol: int) -> object:
        raise TypeError("verified historical evidence is not serializable")

    def __repr__(self) -> str:
        return "VerifiedFactoryPaidOperationHistoricalEvidenceV2(<sealed>)"


def require_verified_factory_paid_operation_historical_evidence_v2(
    capability: object,
) -> FactoryPaidOperationHistoricalEvidenceV2:
    if not isinstance(
        capability,
        VerifiedFactoryPaidOperationHistoricalEvidenceV2,
    ):
        raise TypeError(
            "terminal reconciliation requires "
            "VerifiedFactoryPaidOperationHistoricalEvidenceV2"
        )
    try:
        evidence = _VERIFIED_HISTORICAL_EVIDENCE_REGISTRY_V2[capability]
    except KeyError as exc:
        raise TypeError("unminted historical evidence capability") from exc
    if not isinstance(evidence, FactoryPaidOperationHistoricalEvidenceV2):
        raise TypeError("historical evidence capability is invalid")
    return evidence


def _historical_evidence_binds_image_receipt_v2(
    evidence: FactoryPaidOperationHistoricalEvidenceV2,
    receipt: StoryboardImageProviderReceiptV1,
) -> bool:
    request = receipt.request
    authority = evidence.resolution.paid_budget_authority
    profile = evidence.resolution.cost_profile
    output_digest = derive_factory_paid_operation_claim_output_digest_v2(receipt)
    return (
        evidence.operation == "image"
        and evidence.source_index == request.source_beat_index
        and evidence.workspace_id == request.workspace_id
        and evidence.run_id == request.run_id
        and evidence.factory_revision == request.factory_revision
        and evidence.purpose == request.purpose
        and evidence.paid_budget_authority_digest
        == request.paid_budget_authority_digest
        == authority.authority_digest
        and evidence.cost_profile_digest
        == request.cost_profile_digest
        == profile.profile_digest
        and evidence.pricing_policy_revision
        == request.pricing_policy_revision
        == profile.pricing_policy_revision
        and evidence.provider == request.provider == receipt.provider
        and evidence.model == request.model == receipt.model
        and evidence.operation_key == request.operation_key == receipt.operation_key
        and evidence.execution_request_digest == request.execution_request_digest
        and evidence.provider_operation_id == receipt.provider_task_id
        and evidence.provider_result_output_digest == output_digest
        and evidence.completed_claim_output_digest == output_digest
    )


def _historical_evidence_binds_scene_receipt_v2(
    evidence: FactoryPaidOperationHistoricalEvidenceV2,
    receipt: StoryboardSceneVideoReceiptV1,
) -> bool:
    request = receipt.request
    authority = evidence.resolution.paid_budget_authority
    profile = evidence.resolution.cost_profile
    output_digest = derive_factory_paid_operation_claim_output_digest_v2(receipt)
    return (
        evidence.operation == "video"
        and evidence.source_index == request.scene_sequence_index
        and evidence.workspace_id == request.workspace_id
        and evidence.run_id == request.run_id
        and evidence.factory_revision == request.factory_revision
        and evidence.purpose == "final_production"
        and evidence.paid_budget_authority_digest
        == request.final_production_authority_digest
        == authority.authority_digest
        and evidence.cost_profile_digest
        == request.cost_profile_digest
        == profile.profile_digest
        and evidence.pricing_policy_revision
        == request.pricing_policy_revision
        == profile.pricing_policy_revision
        and evidence.provider == request.provider
        and evidence.model == request.model
        and evidence.operation_key
        == derive_storyboard_scene_video_operation_key_v1(request)
        and evidence.execution_request_digest == request.execution_request_digest
        and evidence.provider_operation_id == receipt.provider_job_id
        and evidence.provider_result_output_digest == output_digest
        and evidence.completed_claim_output_digest == output_digest
    )


def _resolve_terminal_paid_budget_resolution_v2(
    authority: object,
    operation_proofs: tuple[object, ...],
) -> FactoryPaidBudgetResolutionV2 | None:
    """Resolve terminal truth without turning historical proof into authority."""

    try:
        return _unwrap_verified_factory_paid_budget_resolution_v2(authority)
    except TypeError:
        pass
    if not isinstance(authority, FactoryPaidBudgetResolutionV2) or not operation_proofs:
        return None
    historical: list[FactoryPaidOperationHistoricalEvidenceV2] = []
    for proof in operation_proofs:
        try:
            historical.append(
                require_verified_factory_paid_operation_historical_evidence_v2(proof)
            )
        except TypeError:
            return None
    if any(item.resolution != authority for item in historical):
        return None
    return authority


def _scene_receipt_binds_operation_proof_v2(
    receipt: StoryboardSceneVideoReceiptV1,
    proof: object,
) -> bool:
    if receipt.binds_verified_request(proof):
        return True
    try:
        evidence = require_verified_factory_paid_operation_historical_evidence_v2(proof)
    except TypeError:
        return False
    return _historical_evidence_binds_scene_receipt_v2(evidence, receipt)


def _image_receipt_binds_operation_proof_v2(
    receipt: StoryboardImageProviderReceiptV1,
    proof: object,
) -> bool:
    try:
        request = require_verified_storyboard_image_provider_request_v1(proof)
    except TypeError:
        request = None
    if request is not None:
        return receipt.request == request
    try:
        evidence = require_verified_factory_paid_operation_historical_evidence_v2(proof)
    except TypeError:
        return False
    return _historical_evidence_binds_image_receipt_v2(evidence, receipt)


class ReelsFactoryProviderAttemptsV3(BaseModel):
    """Phase-local paid attempts with hard global lane ceilings."""

    model_config = _FROZEN_STRICT

    script: Annotated[int, Field(ge=0, le=1)]
    image: Annotated[int, Field(ge=0, le=16)]
    video: Annotated[int, Field(ge=0, le=16)]
    voice: Annotated[int, Field(ge=0, le=16)]
    render: Annotated[int, Field(ge=0, le=1)]


class ReelsFactoryProviderReplaysV3(BaseModel):
    """Paid V3 execution has no replay budget in any provider lane."""

    model_config = _FROZEN_STRICT

    script: Literal[0]
    image: Literal[0]
    video: Literal[0]
    voice: Literal[0]
    render: Literal[0]


ReelsFactoryProgressStageV3 = Literal["script", "image", "video", "voice", "render"]
ReelsFactoryFailureStageV3 = Literal[
    "authority",
    "script",
    "project_script",
    "plan",
    "project_plan",
    "scheduler",
    "image",
    "video",
    "voice",
    "render",
]


_PROGRESS_STAGES_BY_PURPOSE_V3: dict[str, frozenset[str]] = {
    "storyboard_draft": frozenset({"script", "image"}),
    "storyboard_regen": frozenset({"image"}),
    "final_production": frozenset({"video", "voice", "render"}),
}
_FAILURE_STAGES_BY_PURPOSE_V3: dict[str, frozenset[str]] = {
    "storyboard_draft": frozenset(
        {
            "authority",
            "script",
            "project_script",
            "plan",
            "project_plan",
            "scheduler",
            "image",
        }
    ),
    "storyboard_regen": frozenset({"authority", "scheduler", "image"}),
    "final_production": frozenset(
        {"authority", "scheduler", "video", "voice", "render"}
    ),
}


def _v3_attempt_limits(
    *,
    purpose: FactoryPaidBudgetPurposeV2,
    storyboard_scene_count: int | None,
) -> dict[str, int]:
    if purpose == "storyboard_draft":
        return {"script": 1, "image": 16, "video": 0, "voice": 0, "render": 0}
    if purpose == "storyboard_regen":
        return {"script": 0, "image": 16, "video": 0, "voice": 0, "render": 0}
    if storyboard_scene_count is None:
        raise ValueError("final_production requires storyboard_scene_count")
    return {
        "script": 0,
        "image": 0,
        "video": storyboard_scene_count,
        "voice": 16,
        "render": 1,
    }


def _validate_v3_progress_scope(
    *,
    purpose: FactoryPaidBudgetPurposeV2,
    storyboard_scene_count: int | None,
    storyboard_execution_manifest_digest: str | None,
    provider_attempts: ReelsFactoryProviderAttemptsV3,
    stage: str,
    allowed_stages: Mapping[str, frozenset[str]],
) -> None:
    if purpose == "final_production":
        if (
            storyboard_scene_count is None
            or storyboard_execution_manifest_digest is None
        ):
            raise ValueError(
                "final_production progress requires scene count and execution manifest"
            )
    elif (
        storyboard_scene_count is not None
        or storyboard_execution_manifest_digest is not None
    ):
        raise ValueError(
            "storyboard progress cannot carry scene count or execution manifest"
        )
    if stage not in allowed_stages[purpose]:
        raise ValueError("progress stage does not match paid purpose")
    limits = _v3_attempt_limits(
        purpose=purpose,
        storyboard_scene_count=storyboard_scene_count,
    )
    observed = provider_attempts.model_dump(mode="python")
    if any(observed[track] > limit for track, limit in limits.items()):
        raise ValueError("provider attempts exceed the paid purpose mask")


def _v3_factory_receipt_structurally_binds(
    *,
    workspace_id: str,
    run_id: str,
    factory_revision: int,
    idempotency_key: str,
    all_beat_count: int,
    purpose: FactoryPaidBudgetPurposeV2,
    storyboard_scene_count: int | None,
    paid_budget_authority_digest: str,
    provider_attempts: ReelsFactoryProviderAttemptsV3,
    authority: FactoryPaidBudgetAuthorityV2,
) -> bool:
    observed = provider_attempts.model_dump(mode="python")
    paid_calls = authority.paid_calls.model_dump(mode="python")
    return (
        workspace_id == authority.workspace_id
        and run_id == authority.run_id
        and factory_revision == authority.factory_revision
        and idempotency_key == authority.idempotency_key
        and all_beat_count == authority.all_beat_count
        and purpose == authority.purpose
        and storyboard_scene_count == authority.storyboard_scene_count
        and paid_budget_authority_digest == authority.authority_digest
        and all(observed[track] <= paid_calls[track] for track in observed)
    )


class ReelsFactoryProgressReceiptV3(BaseModel):
    """Purpose- and authority-bound non-terminal paid execution proof."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["ReelsFactoryProgressReceipt.v3"]
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    idempotency_key: DigestStr
    revision: RevisionInt
    purpose: FactoryPaidBudgetPurposeV2
    stage: ReelsFactoryProgressStageV3
    all_beat_count: Literal[16]
    storyboard_scene_count: StoryboardSceneCount | None
    paid_budget_authority_digest: DigestStr
    storyboard_execution_manifest_digest: DigestStr | None
    provider_attempts: ReelsFactoryProviderAttemptsV3
    provider_replays: ReelsFactoryProviderReplaysV3
    fallbacks: Literal[0]
    receipt_digest: DigestStr

    @model_validator(mode="after")
    def _bind_progress(self) -> "ReelsFactoryProgressReceiptV3":
        _validate_v3_progress_scope(
            purpose=self.purpose,
            storyboard_scene_count=self.storyboard_scene_count,
            storyboard_execution_manifest_digest=(
                self.storyboard_execution_manifest_digest
            ),
            provider_attempts=self.provider_attempts,
            stage=self.stage,
            allowed_stages=_PROGRESS_STAGES_BY_PURPOSE_V3,
        )
        if self.receipt_digest != derive_reels_factory_progress_receipt_digest_v3(self):
            raise ValueError("receipt_digest does not match V3 progress payload")
        return self

    def structurally_binds(self, authority: FactoryPaidBudgetAuthorityV2) -> bool:
        return _v3_factory_receipt_structurally_binds(
            workspace_id=self.workspace_id,
            run_id=self.run_id,
            factory_revision=self.factory_revision,
            idempotency_key=self.idempotency_key,
            all_beat_count=self.all_beat_count,
            purpose=self.purpose,
            storyboard_scene_count=self.storyboard_scene_count,
            paid_budget_authority_digest=self.paid_budget_authority_digest,
            provider_attempts=self.provider_attempts,
            authority=authority,
        )


class ReelsFactoryFailureReceiptV3(BaseModel):
    """Purpose- and authority-bound terminal failure proof."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["ReelsFactoryFailureReceipt.v3"]
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    idempotency_key: DigestStr
    revision: RevisionInt
    purpose: FactoryPaidBudgetPurposeV2
    stage: ReelsFactoryFailureStageV3
    all_beat_count: Literal[16]
    storyboard_scene_count: StoryboardSceneCount | None
    paid_budget_authority_digest: DigestStr
    storyboard_execution_manifest_digest: DigestStr | None
    provider_attempts: ReelsFactoryProviderAttemptsV3
    provider_replays: ReelsFactoryProviderReplaysV3
    fallbacks: Literal[0]
    code: NonBlankStr
    provider_call: Literal["none", "confirmed", "unknown"]
    receipt_digest: DigestStr

    @model_validator(mode="after")
    def _bind_failure(self) -> "ReelsFactoryFailureReceiptV3":
        _validate_v3_progress_scope(
            purpose=self.purpose,
            storyboard_scene_count=self.storyboard_scene_count,
            storyboard_execution_manifest_digest=(
                self.storyboard_execution_manifest_digest
            ),
            provider_attempts=self.provider_attempts,
            stage=self.stage,
            allowed_stages=_FAILURE_STAGES_BY_PURPOSE_V3,
        )
        attempt_count = sum(self.provider_attempts.model_dump(mode="python").values())
        if (attempt_count == 0) != (self.provider_call == "none"):
            raise ValueError("provider_call must match observed provider attempts")
        if self.receipt_digest != derive_reels_factory_failure_receipt_digest_v3(self):
            raise ValueError("receipt_digest does not match V3 failure payload")
        return self

    def structurally_binds(self, authority: FactoryPaidBudgetAuthorityV2) -> bool:
        return _v3_factory_receipt_structurally_binds(
            workspace_id=self.workspace_id,
            run_id=self.run_id,
            factory_revision=self.factory_revision,
            idempotency_key=self.idempotency_key,
            all_beat_count=self.all_beat_count,
            purpose=self.purpose,
            storyboard_scene_count=self.storyboard_scene_count,
            paid_budget_authority_digest=self.paid_budget_authority_digest,
            provider_attempts=self.provider_attempts,
            authority=authority,
        )


class StoryboardExecutionManifestV1(BaseModel):
    """Post-approval Phase-B input with all selected rich stills resolved."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryboardExecutionManifest.v1"]
    manifest_id: UuidStr
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    plan_digest: DigestStr
    draft_id: UuidStr
    draft_revision: RevisionInt
    storyboard_draft_digest: DigestStr
    image_set_receipt_digest: DigestStr
    storyboard_approval_receipt_digest: DigestStr
    final_production_authority_digest: DigestStr
    cards: tuple[StoryboardCardV1, ...] = Field(min_length=16, max_length=16)
    images: tuple[StoryboardImageArtifactRefV1, ...] = Field(
        min_length=16,
        max_length=16,
    )
    scenes: tuple[StoryboardSceneV1, ...] = Field(min_length=1, max_length=16)
    manifest_digest: DigestStr

    @field_validator("cards", "images", "scenes", mode="before")
    @classmethod
    def _tuple_fields(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _bind_resolved_selections(self) -> "StoryboardExecutionManifestV1":
        _assert_card_permutations(self.cards, plan_digest=self.plan_digest)
        image_sources = [image.source_beat_index for image in self.images]
        if sorted(image_sources) != list(range(_STORYBOARD_BEAT_COUNT)):
            raise ValueError("manifest images must cover source beats exactly 0..15")
        if image_sources != [card.source_beat_index for card in self.cards]:
            raise ValueError("manifest images must follow card sequence order")
        for field in (
            "artifact_id",
            "storage_key",
            "provider_receipt_digest",
            "generation_nonce",
        ):
            values = [getattr(image, field) for image in self.images]
            if len(values) != len(set(values)):
                raise ValueError(f"manifest image {field} values must be unique")

        for card, image in zip(self.cards, self.images, strict=True):
            if (
                card.selected_artifact.artifact_id != image.artifact_id
                or card.selected_artifact.artifact_digest != image.sha256
            ):
                raise ValueError(
                    "resolved image does not match selected artifact identity"
                )
        if self.scenes != derive_storyboard_scenes_v1(self.cards):
            raise ValueError("manifest scenes do not match derived scenes")
        if self.manifest_digest != derive_storyboard_execution_manifest_digest_v1(self):
            raise ValueError("manifest_digest does not match execution manifest")
        return self

    def binds(
        self,
        approval: StoryboardApprovalReceiptV1,
        draft: StoryboardDraftV1,
        image_set: StoryboardImageSetReceiptV1,
        authority: object,
    ) -> bool:
        try:
            paid_authority = _unwrap_verified_factory_paid_budget_authority_v2(
                authority
            )
        except TypeError:
            return False
        return (
            approval.binds(draft, image_set)
            and paid_authority.purpose == "final_production"
            and paid_authority.workspace_id == self.workspace_id
            and paid_authority.run_id == self.run_id
            and paid_authority.factory_revision == self.factory_revision
            and paid_authority.plan_digest == self.plan_digest
            and paid_authority.storyboard_draft_digest == draft.draft_digest
            and paid_authority.storyboard_approval_receipt_digest
            == approval.receipt_digest
            and paid_authority.storyboard_scene_count == len(self.scenes)
            and paid_authority.authority_digest
            == self.final_production_authority_digest
            and self.workspace_id == draft.workspace_id
            and self.run_id == draft.run_id
            and self.factory_revision == draft.factory_revision
            and self.plan_digest == draft.plan_digest
            and self.draft_id == draft.draft_id
            and self.draft_revision == draft.revision
            and self.storyboard_draft_digest == draft.draft_digest
            and self.image_set_receipt_digest == image_set.receipt_digest
            and self.storyboard_approval_receipt_digest == approval.receipt_digest
            and self.cards == draft.cards
        )


__all__ = [
    "ATHENA_FRAME_PLAN_RECEIPT_VERSION_V1",
    "STORYBOARD_IMAGE_ARTIFACT_REF_VERSION_V1",
    "STORYBOARD_IMAGE_PROVIDER_REQUEST_VERSION_V1",
    "STORYBOARD_IMAGE_PROVIDER_RECEIPT_VERSION_V1",
    "FACTORY_PAID_OPERATION_HISTORICAL_EVIDENCE_VERSION_V2",
    "STORYBOARD_IMAGE_SET_RECEIPT_VERSION_V1",
    "STORYBOARD_CARD_VERSION_V1",
    "STORYBOARD_SCENE_VERSION_V1",
    "STORYBOARD_SCENE_VIDEO_ARTIFACT_REF_VERSION_V1",
    "STORYBOARD_SCENE_VIDEO_RECEIPT_VERSION_V1",
    "STORYBOARD_BEAT_SCENE_VIDEO_PROJECTION_VERSION_V1",
    "STORYBOARD_SCENE_VIDEO_SET_RECEIPT_VERSION_V1",
    "STORYBOARD_SCENE_VIDEO_SET_SUMMARY_VERSION_V1",
    "STORYBOARD_BEAT_SCENE_PROJECTION_SUMMARY_VERSION_V1",
    "STORYBOARD_BEAT_CAPTION_VERSION_V1",
    "STORYBOARD_SCENE_FAN_IN_MANIFEST_VERSION_V1",
    "STORYBOARD_SCENE_VIDEO_REQUEST_VERSION_V1",
    "REELS_FACTORY_RECEIPT_VERSION_V3",
    "REELS_FACTORY_COMPLETION_SUMMARY_VERSION_V3",
    "REELS_FACTORY_PROGRESS_RECEIPT_VERSION_V3",
    "REELS_FACTORY_FAILURE_RECEIPT_VERSION_V3",
    "FACTORY_COST_PROFILE_VERSION_V1",
    "STORYBOARD_SCENE_VIDEO_PROVIDER_PROMPT_MAX_CHARS_V1",
    "STORYBOARD_DRAFT_VERSION_V1",
    "STORYBOARD_APPROVAL_RECEIPT_VERSION_V1",
    "STORYBOARD_EXECUTION_MANIFEST_VERSION_V1",
    "FACTORY_PAID_BUDGET_AUTHORITY_VERSION_V2",
    "FACTORY_PAID_BUDGET_APPROVAL_RECEIPT_VERSION_V2",
    "STORYBOARD_CONTRACT_VERSIONS_V1",
    "StoryboardCropMode",
    "FactoryPaidBudgetPurposeV2",
    "StoryboardImageReferenceSnapshotV1",
    "StoryboardImagePlannedReferenceV1",
    "StoryboardImageFramePlanV1",
    "AthenaFramePlanReceiptV1",
    "StoryboardImageProviderRequestV1",
    "VerifiedStoryboardImageProviderRequestV1",
    "StoryboardImageProviderReceiptV1",
    "StoryboardImageArtifactRefV1",
    "StoryboardSelectedArtifactV1",
    "StoryboardImageSetReceiptV1",
    "StoryboardCardV1",
    "StoryboardSceneV1",
    "StoryboardSceneVideoAnchorV1",
    "StoryboardSceneVideoRequestV1",
    "VerifiedStoryboardSceneVideoRequestV1",
    "StoryboardSceneVideoArtifactRefV1",
    "StoryboardSceneVideoReceiptV1",
    "StoryboardBeatSceneVideoProjectionV1",
    "StoryboardSceneVideoSetReceiptV1",
    "StoryboardBeatSceneProjectionSummaryV1",
    "StoryboardSceneVideoSetSummaryV1",
    "StoryboardBeatCaptionV1",
    "StoryboardSceneFanInManifestV1",
    "ReelsFactoryReceiptV3",
    "ReelsFactoryCompletionSummaryV3",
    "StoryboardDraftV1",
    "StoryboardApprovalReceiptV1",
    "FactoryPaidCallCardinalityV2",
    "FactoryPaidBudgetAuthorityV2",
    "FactoryPaidBudgetApprovalResolverV2",
    "FactoryPaidOperationEvidenceResolverV2",
    "FactoryPaidBudgetApprovalReceiptV2",
    "VerifiedFactoryPaidBudgetAuthorityV2",
    "FactoryCostOperationV1",
    "FactoryCostOperationsV1",
    "FactoryStoryboardDraftCostPolicyV1",
    "FactoryStoryboardRegenCostPolicyV1",
    "FactoryFinalProductionCostPolicyV1",
    "FactoryCostPurposePoliciesV1",
    "FactoryCostProfileV1",
    "FactoryPaidBudgetResolutionV2",
    "FactoryPaidOperationHistoricalEvidenceV2",
    "VerifiedFactoryPaidOperationHistoricalEvidenceV2",
    "ReelsFactoryProviderAttemptsV3",
    "ReelsFactoryProviderReplaysV3",
    "ReelsFactoryProgressReceiptV3",
    "ReelsFactoryFailureReceiptV3",
    "StoryboardExecutionManifestV1",
    "derive_storyboard_image_artifact_digest_v1",
    "derive_athena_frame_plan_receipt_digest_v1",
    "derive_storyboard_image_generation_nonce_v1",
    "derive_storyboard_image_operation_key_v1",
    "derive_storyboard_image_provider_request_digest_v1",
    "derive_storyboard_image_expected_artifact_id_v1",
    "derive_storyboard_image_expected_storage_key_v1",
    "derive_storyboard_image_provider_execution_request_digest_v1",
    "derive_storyboard_image_provider_idempotency_key_v1",
    "derive_storyboard_image_provider_receipt_digest_v1",
    "derive_factory_paid_operation_claim_output_digest_v2",
    "derive_factory_paid_operation_historical_evidence_digest_v2",
    "require_verified_factory_paid_operation_historical_evidence_v2",
    "require_verified_storyboard_image_provider_request_v1",
    "derive_storyboard_image_set_receipt_digest_v1",
    "derive_storyboard_beat_identity_digest_v1",
    "derive_storyboard_card_digest_v1",
    "derive_storyboard_scene_digest_v1",
    "derive_storyboard_scenes_v1",
    "derive_storyboard_scene_video_artifact_digest_v1",
    "derive_storyboard_scene_video_operation_key_v1",
    "derive_storyboard_scene_video_request_digest_v1",
    "derive_storyboard_scene_video_execution_request_digest_v1",
    "derive_storyboard_scene_video_idempotency_key_v1",
    "derive_storyboard_scene_video_provider_prompt_v1",
    "require_verified_storyboard_scene_video_request_v1",
    "derive_storyboard_scene_video_receipt_digest_v1",
    "derive_storyboard_beat_scene_video_projection_digest_v1",
    "derive_storyboard_scene_video_set_receipt_digest_v1",
    "derive_storyboard_beat_scene_projection_summary_digest_v1",
    "derive_storyboard_scene_video_set_summary_digest_v1",
    "derive_storyboard_beat_caption_digest_v1",
    "derive_storyboard_caption_set_digest_v1",
    "derive_storyboard_scene_fan_in_manifest_digest_v1",
    "derive_reels_factory_receipt_digest_v3",
    "derive_reels_factory_completion_summary_digest_v3",
    "derive_reels_factory_progress_receipt_digest_v3",
    "derive_reels_factory_failure_receipt_digest_v3",
    "derive_storyboard_draft_digest_v1",
    "derive_storyboard_approval_receipt_digest_v1",
    "derive_storyboard_execution_manifest_digest_v1",
    "factory_paid_call_cardinality_v2",
    "derive_factory_paid_budget_approval_subject_digest_v2",
    "derive_factory_paid_budget_idempotency_key_v2",
    "derive_factory_paid_budget_authority_digest_v2",
    "derive_factory_paid_budget_approval_receipt_digest_v2",
    "derive_factory_cost_profile_digest_v1",
]
