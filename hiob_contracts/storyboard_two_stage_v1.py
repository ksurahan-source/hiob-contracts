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
from weakref import WeakKeyDictionary

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    StringConstraints,
    field_validator,
    field_serializer,
    model_validator,
)

from .all_beat_video import (
    HephaestusFinalRenderReceiptV2,
    StrictAllBeatArtifactRefV1,
    _assert_audio_artifact,
    _assert_https_url,
)
from .ares_script_revision_v1 import (
    DigestStr,
    NonBlankStr,
    NonNegativeInt,
    UtcTimestamp,
    UuidStr,
    _FROZEN_STRICT,
    _deep_freeze_json,
    _json_value,
    _parse_utc,
    _validate_json,
    canonical_contract_digest_v1,
)


STORYBOARD_IMAGE_ARTIFACT_REF_VERSION_V1 = "StoryboardImageArtifactRef.v1"
STORYBOARD_IMAGE_SET_RECEIPT_VERSION_V1 = "StoryboardImageSetReceipt.v1"
STORYBOARD_CARD_VERSION_V1 = "StoryboardCard.v1"
STORYBOARD_SCENE_VERSION_V1 = "StoryboardScene.v1"
STORYBOARD_SCENE_VIDEO_ARTIFACT_REF_VERSION_V1 = "StoryboardSceneVideoArtifactRef.v1"
STORYBOARD_SCENE_VIDEO_RECEIPT_VERSION_V1 = "StoryboardSceneVideoReceipt.v1"
STORYBOARD_BEAT_SCENE_VIDEO_PROJECTION_VERSION_V1 = (
    "StoryboardBeatSceneVideoProjection.v1"
)
STORYBOARD_SCENE_VIDEO_SET_RECEIPT_VERSION_V1 = "StoryboardSceneVideoSetReceipt.v1"
STORYBOARD_SCENE_FAN_IN_MANIFEST_VERSION_V1 = "StoryboardSceneFanInManifest.v1"
REELS_FACTORY_RECEIPT_VERSION_V3 = "ReelsFactoryReceipt.v3"
STORYBOARD_DRAFT_VERSION_V1 = "StoryboardDraft.v1"
STORYBOARD_APPROVAL_RECEIPT_VERSION_V1 = "StoryboardApprovalReceipt.v1"
STORYBOARD_EXECUTION_MANIFEST_VERSION_V1 = "StoryboardExecutionManifest.v1"
FACTORY_PAID_BUDGET_AUTHORITY_VERSION_V2 = "FactoryPaidBudgetAuthority.v2"
FACTORY_PAID_BUDGET_APPROVAL_RECEIPT_VERSION_V2 = "FactoryPaidBudgetApprovalReceipt.v2"

STORYBOARD_CONTRACT_VERSIONS_V1 = {
    "image_artifact_ref": STORYBOARD_IMAGE_ARTIFACT_REF_VERSION_V1,
    "image_set_receipt": STORYBOARD_IMAGE_SET_RECEIPT_VERSION_V1,
    "card": STORYBOARD_CARD_VERSION_V1,
    "scene": STORYBOARD_SCENE_VERSION_V1,
    "scene_video_artifact_ref": STORYBOARD_SCENE_VIDEO_ARTIFACT_REF_VERSION_V1,
    "scene_video_receipt": STORYBOARD_SCENE_VIDEO_RECEIPT_VERSION_V1,
    "beat_scene_video_projection": (STORYBOARD_BEAT_SCENE_VIDEO_PROJECTION_VERSION_V1),
    "scene_video_set_receipt": STORYBOARD_SCENE_VIDEO_SET_RECEIPT_VERSION_V1,
    "scene_fan_in_manifest": STORYBOARD_SCENE_FAN_IN_MANIFEST_VERSION_V1,
    "reels_factory_receipt": REELS_FACTORY_RECEIPT_VERSION_V3,
    "draft": STORYBOARD_DRAFT_VERSION_V1,
    "approval_receipt": STORYBOARD_APPROVAL_RECEIPT_VERSION_V1,
    "execution_manifest": STORYBOARD_EXECUTION_MANIFEST_VERSION_V1,
    "paid_budget_authority": FACTORY_PAID_BUDGET_AUTHORITY_VERSION_V2,
    "paid_budget_approval_receipt": (FACTORY_PAID_BUDGET_APPROVAL_RECEIPT_VERSION_V2),
}

_JSON_SAFE_INTEGER_MAX = 9_007_199_254_740_991
_STORYBOARD_BEAT_COUNT = 16


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
BeatText = Annotated[
    str,
    StringConstraints(max_length=2_000),
    AfterValidator(_non_blank_limited),
]
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
    beat_text: str,
) -> str:
    return canonical_contract_digest_v1(
        {
            "purpose": "storyboard-beat-identity.v1",
            "plan_digest": plan_digest,
            "source_beat_index": source_beat_index,
            "beat_text": beat_text,
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


def derive_storyboard_scene_video_request_digest_v1(
    *,
    scene: Mapping[str, Any] | BaseModel,
    anchor_card: Mapping[str, Any] | BaseModel,
    storyboard_execution_manifest_digest: str,
    final_production_authority_digest: str,
) -> str:
    """Bind one scene request to only its first approved card's visual fields."""

    scene_data = _as_json_dict(scene)
    card_data = _as_json_dict(anchor_card)
    source_beat_indices = scene_data["source_beat_indices"]
    if (
        not source_beat_indices
        or card_data["source_beat_index"] != source_beat_indices[0]
        or card_data["selected_artifact"] != scene_data["anchor_selected_artifact"]
    ):
        raise ValueError("anchor_card must be the scene's first selected card")
    return canonical_contract_digest_v1(
        {
            "purpose": "storyboard-scene-video-request.v1",
            "storyboard_execution_manifest_digest": (
                storyboard_execution_manifest_digest
            ),
            "final_production_authority_digest": (final_production_authority_digest),
            "scene_sequence_index": scene_data["sequence_index"],
            "scene_id": scene_data["scene_id"],
            "scene_digest": scene_data["scene_digest"],
            "anchor": {
                "source_beat_index": card_data["source_beat_index"],
                "beat_identity_digest": card_data["beat_identity_digest"],
                "prompt_override": card_data["prompt_override"],
                "crop_mode": card_data["crop_mode"],
                "focal_x_basis_points": card_data["focal_x_basis_points"],
                "focal_y_basis_points": card_data["focal_y_basis_points"],
                "motion_note": card_data["motion_note"],
                "selected_artifact": card_data["selected_artifact"],
            },
        }
    )


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


def derive_storyboard_scene_fan_in_manifest_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "manifest_digest")


def derive_reels_factory_receipt_digest_v3(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "receipt_digest")


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
    expected_image_count: Literal[16]
    images: tuple[StoryboardImageArtifactRefV1, ...] = Field(
        min_length=16,
        max_length=16,
    )
    completed_at_utc: UtcTimestamp
    receipt_digest: DigestStr

    @field_validator("images", mode="before")
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
            "sha256",
            "provider_receipt_digest",
            "generation_nonce",
            "artifact_digest",
        )
        for field in unique_fields:
            values = [getattr(image, field) for image in self.images]
            if len(values) != len(set(values)):
                raise ValueError(f"image {field} values must be unique")

        if self.receipt_digest != derive_storyboard_image_set_receipt_digest_v1(self):
            raise ValueError("receipt_digest does not match storyboard image set")
        return self


class StoryboardCardV1(BaseModel):
    """One editor card with immutable source identity and mutable presentation."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryboardCard.v1"]
    source_beat_index: StoryboardBeatIndex
    sequence_index: StoryboardBeatIndex
    scene_id: SceneId
    beat_text: BeatText
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
        "anchor_selected_artifact": anchor.selected_artifact.model_dump(mode="json"),
    }
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
    """Successful provider receipt for one dense storyboard scene ordinal."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryboardSceneVideoReceipt.v1"]
    scene_sequence_index: StoryboardBeatIndex
    scene_id: SceneId
    scene_digest: DigestStr
    anchor_selected_artifact: StoryboardSelectedArtifactV1
    generation_nonce: UuidStr
    request_digest: DigestStr
    provider: NonBlankStr
    model: NonBlankStr
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
        if self.receipt_digest != derive_storyboard_scene_video_receipt_digest_v1(self):
            raise ValueError("receipt_digest does not match scene video receipt")
        return self


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
        if [item.scene_sequence_index for item in scene_receipts] != list(
            range(self.storyboard_scene_count)
        ):
            raise ValueError("scene video receipts must use dense sequence order")

        for field in (
            "scene_id",
            "scene_digest",
            "generation_nonce",
            "request_digest",
            "provider_job_id",
            "receipt_digest",
        ):
            values = [getattr(item, field) for item in scene_receipts]
            if len(values) != len(set(values)):
                raise ValueError(f"scene video {field} values must be unique")
        for field in ("artifact_id", "storage_key", "sha256", "artifact_digest"):
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
                projection.scene_digest != scene_receipt.scene_digest
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
    ) -> bool:
        try:
            paid_authority = _unwrap_verified_factory_paid_budget_authority_v2(
                authority
            )
        except TypeError:
            return False
        if not (
            paid_authority.purpose == "final_production"
            and paid_authority.authority_digest
            == self.final_production_authority_digest
            and paid_authority.storyboard_scene_count == self.storyboard_scene_count
            and manifest.final_production_authority_digest
            == paid_authority.authority_digest
            and manifest.manifest_digest == self.storyboard_execution_manifest_digest
            and manifest.workspace_id == self.workspace_id
            and manifest.run_id == self.run_id
            and manifest.factory_revision == self.factory_revision
            and manifest.plan_digest == self.plan_digest
            and len(manifest.scenes) == self.storyboard_scene_count
        ):
            return False

        scene_index_by_source: dict[int, tuple[int, StoryboardSceneV1]] = {
            source_beat_index: (scene_sequence_index, scene)
            for scene_sequence_index, scene in enumerate(manifest.scenes)
            for source_beat_index in scene.source_beat_indices
        }
        card_by_source = {card.source_beat_index: card for card in manifest.cards}
        for scene_sequence_index, (scene, receipt) in enumerate(
            zip(manifest.scenes, self.scene_video_receipts, strict=True)
        ):
            if not (
                receipt.scene_sequence_index == scene_sequence_index
                and receipt.scene_id == scene.scene_id
                and receipt.scene_digest == scene.scene_digest
                and receipt.anchor_selected_artifact == scene.anchor_selected_artifact
                and receipt.request_digest
                == derive_storyboard_scene_video_request_digest_v1(
                    scene=scene,
                    anchor_card=card_by_source[scene.source_beat_indices[0]],
                    storyboard_execution_manifest_digest=manifest.manifest_digest,
                    final_production_authority_digest=(paid_authority.authority_digest),
                )
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
    timeline_digest: DigestStr
    audio_mix_digest: DigestStr
    render_policy_digest: DigestStr
    manifest_digest: DigestStr

    @field_validator("audio_artifacts", mode="before")
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
        for field in ("artifact_id", "uri", "sha256", "execution_id"):
            values = [getattr(artifact, field) for artifact in self.audio_artifacts]
            if len(values) != len(set(values)):
                raise ValueError(f"audio artifact {field} values must be unique")

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
    ) -> bool:
        try:
            paid_authority = _unwrap_verified_factory_paid_budget_authority_v2(
                authority
            )
        except TypeError:
            return False
        return (
            self.workspace_id == manifest.workspace_id
            and self.run_id == manifest.run_id
            and self.factory_revision == manifest.factory_revision
            and self.plan_digest == manifest.plan_digest
            and self.paid_budget_authority_digest == paid_authority.authority_digest
            and self.storyboard_execution_manifest_digest == manifest.manifest_digest
            and self.storyboard_scene_video_set_receipt.binds(
                manifest,
                authority,
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
    selected_ids = [card.selected_artifact.artifact_id for card in cards]
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("selected artifact ids must be unique across cards")
    for card in cards:
        expected_identity = derive_storyboard_beat_identity_digest_v1(
            plan_digest,
            card.source_beat_index,
            card.beat_text,
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

    def is_valid_successor_of(self, previous: "StoryboardDraftV1") -> bool:
        if not (
            self.draft_id == previous.draft_id
            and self.workspace_id == previous.workspace_id
            and self.run_id == previous.run_id
            and self.factory_revision == previous.factory_revision
            and self.plan_digest == previous.plan_digest
            and self.image_set_receipt_digest == previous.image_set_receipt_digest
            and self.revision == previous.revision + 1
            and self.parent_draft_digest == previous.draft_digest
        ):
            return False

        current_by_source = {card.source_beat_index: card for card in self.cards}
        previous_by_source = {card.source_beat_index: card for card in previous.cards}
        for source_beat_index in range(_STORYBOARD_BEAT_COUNT):
            current = current_by_source[source_beat_index]
            prior = previous_by_source[source_beat_index]
            if (
                current.beat_text != prior.beat_text
                or current.beat_identity_digest != prior.beat_identity_digest
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

    @classmethod
    def from_verified(
        cls,
        value: Mapping[str, Any] | BaseModel,
        *,
        approval_receipt: "FactoryPaidBudgetApprovalReceiptV2",
        at_utc: str,
        resolver: FactoryPaidBudgetApprovalResolverV2,
    ) -> "VerifiedFactoryPaidBudgetAuthorityV2":
        authority = cls.model_validate(_as_json_dict(value))
        if not approval_receipt.authorizes(
            authority,
            at_utc=at_utc,
            resolver=resolver,
        ):
            raise ValueError("authority requires current durable approval")
        return VerifiedFactoryPaidBudgetAuthorityV2(
            authority,
            _token=_VERIFIED_AUTHORITY_TOKEN_V2,
        )


_VERIFIED_AUTHORITY_TOKEN_V2 = object()
_VERIFIED_AUTHORITY_REGISTRY_V2: WeakKeyDictionary[
    object,
    FactoryPaidBudgetAuthorityV2,
] = WeakKeyDictionary()


class VerifiedFactoryPaidBudgetAuthorityV2:
    """Non-serializable in-process capability minted from current V2 approval."""

    __slots__ = ("__weakref__",)

    def __init__(
        self,
        authority: FactoryPaidBudgetAuthorityV2,
        *,
        _token: object,
    ) -> None:
        if _token is not _VERIFIED_AUTHORITY_TOKEN_V2:
            raise TypeError("verified authority can only be minted by from_verified")
        _VERIFIED_AUTHORITY_REGISTRY_V2[self] = authority

    @property
    def authority(self) -> FactoryPaidBudgetAuthorityV2:
        return _unwrap_verified_factory_paid_budget_authority_v2(self)

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
    if not isinstance(capability, VerifiedFactoryPaidBudgetAuthorityV2):
        raise TypeError("execution requires VerifiedFactoryPaidBudgetAuthorityV2")
    try:
        return _VERIFIED_AUTHORITY_REGISTRY_V2[capability]
    except KeyError as exc:
        raise TypeError("unminted verified paid authority capability") from exc


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


class FactoryPaidBudgetResolutionV2(BaseModel):
    """Exact DB/BFF resolution envelope for a current V2 paid authority."""

    model_config = _FROZEN_STRICT

    approval_receipt: FactoryPaidBudgetApprovalReceiptV2
    paid_budget_authority: FactoryPaidBudgetAuthorityV2
    cost_profile: Mapping[str, Any]

    @field_validator("cost_profile", mode="after")
    @classmethod
    def _freeze_cost_profile(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        _validate_json(value, "cost_profile")
        return _deep_freeze_json(value)

    @field_serializer("cost_profile", when_used="always")
    def _serialize_cost_profile(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return _json_value(value)

    @model_validator(mode="after")
    def _bind_resolution(self) -> "FactoryPaidBudgetResolutionV2":
        authority = self.paid_budget_authority
        if not self.approval_receipt.structurally_binds(authority):
            raise ValueError("approval_receipt does not bind paid_budget_authority")
        try:
            profile_digest = self.cost_profile["profile_digest"]
            pricing_revision = self.cost_profile["pricing_policy_revision"]
        except KeyError as exc:
            raise ValueError("cost_profile is missing identity fields") from exc
        if (
            profile_digest != authority.cost_profile_digest
            or pricing_revision != authority.pricing_policy_revision
            or canonical_contract_digest_v1(
                self.cost_profile,
                exclude={"profile_digest"},
            )
            != profile_digest
        ):
            raise ValueError("cost_profile does not match paid authority")
        return self

    def from_verified(
        self,
        *,
        at_utc: str,
        resolver: FactoryPaidBudgetApprovalResolverV2,
    ) -> VerifiedFactoryPaidBudgetAuthorityV2:
        return FactoryPaidBudgetAuthorityV2.from_verified(
            self.paid_budget_authority,
            approval_receipt=self.approval_receipt,
            at_utc=at_utc,
            resolver=resolver,
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
            "sha256",
            "provider_receipt_digest",
            "generation_nonce",
            "artifact_digest",
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
    "STORYBOARD_IMAGE_ARTIFACT_REF_VERSION_V1",
    "STORYBOARD_IMAGE_SET_RECEIPT_VERSION_V1",
    "STORYBOARD_CARD_VERSION_V1",
    "STORYBOARD_SCENE_VERSION_V1",
    "STORYBOARD_SCENE_VIDEO_ARTIFACT_REF_VERSION_V1",
    "STORYBOARD_SCENE_VIDEO_RECEIPT_VERSION_V1",
    "STORYBOARD_BEAT_SCENE_VIDEO_PROJECTION_VERSION_V1",
    "STORYBOARD_SCENE_VIDEO_SET_RECEIPT_VERSION_V1",
    "STORYBOARD_SCENE_FAN_IN_MANIFEST_VERSION_V1",
    "REELS_FACTORY_RECEIPT_VERSION_V3",
    "STORYBOARD_DRAFT_VERSION_V1",
    "STORYBOARD_APPROVAL_RECEIPT_VERSION_V1",
    "STORYBOARD_EXECUTION_MANIFEST_VERSION_V1",
    "FACTORY_PAID_BUDGET_AUTHORITY_VERSION_V2",
    "FACTORY_PAID_BUDGET_APPROVAL_RECEIPT_VERSION_V2",
    "STORYBOARD_CONTRACT_VERSIONS_V1",
    "StoryboardCropMode",
    "FactoryPaidBudgetPurposeV2",
    "StoryboardImageArtifactRefV1",
    "StoryboardSelectedArtifactV1",
    "StoryboardImageSetReceiptV1",
    "StoryboardCardV1",
    "StoryboardSceneV1",
    "StoryboardSceneVideoArtifactRefV1",
    "StoryboardSceneVideoReceiptV1",
    "StoryboardBeatSceneVideoProjectionV1",
    "StoryboardSceneVideoSetReceiptV1",
    "StoryboardSceneFanInManifestV1",
    "ReelsFactoryReceiptV3",
    "StoryboardDraftV1",
    "StoryboardApprovalReceiptV1",
    "FactoryPaidCallCardinalityV2",
    "FactoryPaidBudgetAuthorityV2",
    "FactoryPaidBudgetApprovalResolverV2",
    "FactoryPaidBudgetApprovalReceiptV2",
    "VerifiedFactoryPaidBudgetAuthorityV2",
    "FactoryPaidBudgetResolutionV2",
    "StoryboardExecutionManifestV1",
    "derive_storyboard_image_artifact_digest_v1",
    "derive_storyboard_image_set_receipt_digest_v1",
    "derive_storyboard_beat_identity_digest_v1",
    "derive_storyboard_card_digest_v1",
    "derive_storyboard_scene_digest_v1",
    "derive_storyboard_scenes_v1",
    "derive_storyboard_scene_video_artifact_digest_v1",
    "derive_storyboard_scene_video_request_digest_v1",
    "derive_storyboard_scene_video_receipt_digest_v1",
    "derive_storyboard_beat_scene_video_projection_digest_v1",
    "derive_storyboard_scene_video_set_receipt_digest_v1",
    "derive_storyboard_scene_fan_in_manifest_digest_v1",
    "derive_reels_factory_receipt_digest_v3",
    "derive_storyboard_draft_digest_v1",
    "derive_storyboard_approval_receipt_digest_v1",
    "derive_storyboard_execution_manifest_digest_v1",
    "factory_paid_call_cardinality_v2",
    "derive_factory_paid_budget_approval_subject_digest_v2",
    "derive_factory_paid_budget_idempotency_key_v2",
    "derive_factory_paid_budget_authority_digest_v2",
    "derive_factory_paid_budget_approval_receipt_digest_v2",
]
