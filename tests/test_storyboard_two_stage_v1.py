"""Two-stage storyboard contracts keep paid production behind editor approval."""

from __future__ import annotations

from copy import copy, deepcopy
import json
import pickle
from typing import Any, Callable
from uuid import NAMESPACE_URL, uuid5

import pytest
from pydantic import BaseModel, ValidationError

import hiob_contracts
from hiob_contracts import (
    FactoryPaidBudgetAuthorityV1,
    FactoryPaidBudgetApprovalReceiptV2,
    FactoryPaidBudgetApprovalResolverV2,
    FactoryPaidBudgetAuthorityV2,
    FactoryPaidBudgetResolutionV2,
    FactoryCostProfileV1,
    FactoryStoryboardCarrierV1,
    ReelsFactoryReceiptV3,
    StarReelsViewV3,
    StoryboardSceneFanInManifestV1,
    StoryboardBeatSceneVideoProjectionV1,
    VerifiedFactoryPaidBudgetAuthorityV2,
    StoryboardApprovalReceiptV1,
    StoryboardDraftV1,
    StoryboardExecutionManifestV1,
    StoryboardImageArtifactRefV1,
    StoryboardImageProviderReceiptV1,
    StoryboardImageSetReceiptV1,
    StoryboardSceneV1,
    StoryboardSceneVideoRequestV1,
    StoryboardSceneVideoArtifactRefV1,
    StoryboardSceneVideoReceiptV1,
    StoryboardSceneVideoSetReceiptV1,
    StrictAllBeatArtifactRefV1,
    StoryboardSelectedArtifactV1,
    VerifiedStoryboardSceneVideoRequestV1,
    canonical_contract_digest_v1,
    derive_factory_paid_budget_approval_subject_digest_v2,
    derive_factory_paid_budget_approval_receipt_digest_v2,
    derive_factory_paid_budget_authority_digest_v2,
    derive_factory_paid_budget_idempotency_key_v2,
    derive_factory_cost_profile_digest_v1,
    derive_reels_factory_receipt_digest_v3,
    derive_storyboard_approval_receipt_digest_v1,
    derive_storyboard_beat_identity_digest_v1,
    derive_storyboard_card_digest_v1,
    derive_storyboard_draft_digest_v1,
    derive_storyboard_execution_manifest_digest_v1,
    derive_storyboard_image_artifact_digest_v1,
    derive_storyboard_image_set_receipt_digest_v1,
    derive_storyboard_scene_digest_v1,
    derive_storyboard_beat_scene_video_projection_digest_v1,
    derive_storyboard_scene_video_artifact_digest_v1,
    derive_storyboard_scene_video_execution_request_digest_v1,
    derive_storyboard_scene_video_receipt_digest_v1,
    derive_storyboard_scene_video_request_digest_v1,
    derive_storyboard_scene_video_idempotency_key_v1,
    derive_storyboard_scene_video_provider_prompt_v1,
    derive_storyboard_scene_video_set_receipt_digest_v1,
    derive_storyboard_scene_fan_in_manifest_digest_v1,
    derive_storyboard_scenes_v1,
    require_verified_storyboard_scene_video_request_v1,
    registered_contracts,
    sha256_digest,
    validate_payload,
)


WORKSPACE_ID = "00000000-0000-4000-8000-000000000001"
RUN_ID = "00000000-0000-4000-8000-000000000002"
DRAFT_ID = "00000000-0000-4000-8000-000000000003"
MANIFEST_ID = "00000000-0000-4000-8000-000000000004"
PLAN_DIGEST = sha256_digest({"plan": "sixteen-beat-storyboard"})
ARES_SCRIPT_REVISION_DIGEST = sha256_digest({"ares_script_revision": 7})
ARES_BEAT_PLAN_REVISION_DIGEST = PLAN_DIGEST
DRAFT_AUTHORITY_DIGEST = sha256_digest({"authority": "storyboard-draft"})
FINAL_AUTHORITY_DIGEST = sha256_digest({"authority": "final-production"})
COST_PROFILE_DIGEST = sha256_digest({"pricing": "storyboard-2026-08-14"})
DRAFT_AUTHORITY_IDEMPOTENCY_KEY = sha256_digest(
    {"authority_idempotency": "storyboard-draft"}
)


class _ApprovalResolverV2:
    def __init__(self, current: bool = True) -> None:
        self.current = current
        self.last_identity: dict[str, Any] | None = None
        self.call_count = 0

    def is_current_approval(self, **identity: Any) -> bool:
        self.call_count += 1
        self.last_identity = identity
        return self.current


class _PaidOperationEvidenceResolverV2:
    def __init__(self, verified: bool = True) -> None:
        self.verified = verified
        self.last_identity: dict[str, Any] | None = None
        self.call_count = 0

    def is_verified_completed_operation(self, **identity: Any) -> bool:
        self.call_count += 1
        self.last_identity = identity
        return self.verified


def _sealed(
    body: dict[str, Any],
    *,
    digest_field: str,
    derive: Callable[[dict[str, Any]], str],
) -> dict[str, Any]:
    value = deepcopy(body)
    value[digest_field] = derive(value)
    return value


def _ares_revision_pair(
    *,
    text_prefix: str = "immutable beat text",
) -> tuple[Any, Any]:
    script_revision_id = "00000000-0000-4000-8000-000000000010"
    plan_revision_id = "00000000-0000-4000-8000-000000000011"
    candidate_id = "00000000-0000-4000-8000-000000000012"
    segments = [
        {"beat_index": index, "text": f"{text_prefix} {index}"} for index in range(16)
    ]
    package_body: dict[str, Any] = {
        "contract_version": "AresScriptPackage.v1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "revision_id": script_revision_id,
        "candidate_id": candidate_id,
        "factory_revision": 7,
        "master_sales_script": {"title": "sixteen beat storyboard"},
        "voice_script": segments,
        "caption_script": segments,
        "pronunciation_overrides": {},
    }
    package_body["package_digest"] = canonical_contract_digest_v1(package_body)
    script_body: dict[str, Any] = {
        "contract_version": "AresScriptRevision.v1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "revision_id": script_revision_id,
        "candidate_id": candidate_id,
        "factory_revision": 7,
        "script_package": package_body,
    }
    script_body["revision_digest"] = canonical_contract_digest_v1(script_body)
    script_revision = hiob_contracts.AresScriptRevisionV1.model_validate(script_body)
    beat_plan_body: dict[str, Any] = {
        "contract_version": "AresBeatPlan.v1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "revision_id": plan_revision_id,
        "script_revision_id": script_revision_id,
        "factory_revision": 7,
        "script_package_digest": package_body["package_digest"],
        "beats": [
            {
                "beat_index": index,
                "text": f"{text_prefix} {index}",
                "caption": f"{text_prefix} {index}",
                "scene_direction": {
                    "shot": "MCU",
                    "subject": "approved subject",
                    "setting": "approved setting",
                    "overlay": "",
                },
            }
            for index in range(16)
        ],
        "production_plan": {"visual": {"approved": True}},
    }
    beat_plan_body["plan_digest"] = canonical_contract_digest_v1(beat_plan_body)
    plan_body: dict[str, Any] = {
        "contract_version": "AresBeatPlanRevision.v1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "revision_id": plan_revision_id,
        "script_revision_id": script_revision_id,
        "factory_revision": 7,
        "approved_script_package_digest": package_body["package_digest"],
        "beat_plan": beat_plan_body,
    }
    plan_body["revision_digest"] = canonical_contract_digest_v1(plan_body)
    return script_revision, hiob_contracts.AresBeatPlanRevisionV1.model_validate(
        plan_body
    )


def _athena_frame_plan_receipt(script_revision: Any, plan_revision: Any) -> dict:
    body: dict[str, Any] = {
        "contract_version": "AthenaFramePlanReceipt.v1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "script_revision_digest": script_revision.revision_digest,
        "beat_plan_digest": plan_revision.beat_plan.plan_digest,
        "beat_plan_revision_digest": plan_revision.revision_digest,
        "visual_bridge_digest": None,
        "frame_plans": [_image_frame_plan(index) for index in range(16)],
    }
    body["receipt_digest"] = canonical_contract_digest_v1(body)
    return body


def _image_frame_plan(source_beat_index: int, **changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "run_id": RUN_ID,
        "workspace_id": WORKSPACE_ID,
        "beat_index": source_beat_index,
        "shot_list_digest": sha256_digest({"shot_list": source_beat_index}),
        "render_mode": "product_solo",
        "ordered_refs": [],
        "shot": {"beat_index": source_beat_index, "shot_size": "mcu"},
        "prompt": f"approved storyboard still prompt {source_beat_index}",
        "prompt_constitution_version": "visual-constitution.v1",
        "provider": "seedream",
        "model": "seedream-5-pro",
        "width": 1_024,
        "height": 1_536,
        "quality": "high",
        "lock_policy": "hard_fail",
        "max_refs": 5,
    }
    body.update(changes)
    body["plan_digest"] = canonical_contract_digest_v1(
        body,
        exclude={"plan_digest"},
    )
    return body


def _reseal_image_provider_request(body: dict[str, Any]) -> dict[str, Any]:
    body["operation_key"] = hiob_contracts.derive_storyboard_image_operation_key_v1(
        body
    )
    body["request_digest"] = (
        hiob_contracts.derive_storyboard_image_provider_request_digest_v1(body)
    )
    body["expected_artifact_id"] = (
        hiob_contracts.derive_storyboard_image_expected_artifact_id_v1(body)
    )
    body["expected_storage_key"] = (
        hiob_contracts.derive_storyboard_image_expected_storage_key_v1(body)
    )
    body["execution_request_digest"] = (
        hiob_contracts.derive_storyboard_image_provider_execution_request_digest_v1(
            body
        )
    )
    body["idempotency_key"] = (
        hiob_contracts.derive_storyboard_image_provider_idempotency_key_v1(body)
    )
    return body


def _image_provider_request(
    source_beat_index: int,
    *,
    purpose: str = "storyboard_draft",
    paid_budget_authority_digest: str = DRAFT_AUTHORITY_DIGEST,
    authority_idempotency_key: str = DRAFT_AUTHORITY_IDEMPOTENCY_KEY,
    athena_frame_plan_receipt_digest: str | None = None,
    generation_nonce: str | None = None,
    cost_profile: dict[str, Any] | FactoryCostProfileV1 | None = None,
    **changes: Any,
) -> dict[str, Any]:
    profile = FactoryCostProfileV1.model_validate(
        cost_profile if cost_profile is not None else _cost_profile()
    )
    body: dict[str, Any] = {
        "contract_version": "StoryboardImageProviderRequest.v1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "purpose": purpose,
        "plan_digest": PLAN_DIGEST,
        "ares_script_revision_digest": ARES_SCRIPT_REVISION_DIGEST,
        "ares_beat_plan_revision_digest": ARES_BEAT_PLAN_REVISION_DIGEST,
        "paid_budget_authority_digest": paid_budget_authority_digest,
        "source_beat_index": source_beat_index,
        "frame_plan": _image_frame_plan(source_beat_index),
        "athena_frame_plan_receipt_digest": (
            athena_frame_plan_receipt_digest
            or sha256_digest({"athena_frame_plan_receipt": PLAN_DIGEST})
        ),
        "provider": profile.operations.image.provider,
        "model": profile.operations.image.model,
        "cost_profile_digest": profile.profile_digest,
        "pricing_policy_revision": profile.pricing_policy_revision,
        "generation_nonce": generation_nonce
        or hiob_contracts.derive_storyboard_image_generation_nonce_v1(
            authority_idempotency_key=authority_idempotency_key,
            purpose=purpose,
            source_beat_index=source_beat_index,
        ),
    }
    body.update(changes)
    return _reseal_image_provider_request(body)


def _image_provider_receipt(
    request: dict[str, Any],
    source_beat_index: int,
    **changes: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "contract_version": "StoryboardImageProviderReceipt.v1",
        "request": request,
        "operation_key": request["operation_key"],
        "provider": request["provider"],
        "model": request["model"],
        "provider_task_id": f"seedream-task-{source_beat_index:02d}",
        "status": "committed",
        "artifact_id": request["expected_artifact_id"],
        "storage_key": request["expected_storage_key"],
        "sha256": sha256_digest({"image": source_beat_index}),
        "mime": "image/webp",
        "bytes_len": 4_096 + source_beat_index,
        "width": 1_080,
        "height": 1_920,
        "started_at_utc": "2026-08-14T05:10:00Z",
        "completed_at_utc": "2026-08-14T05:20:00Z",
    }
    body.update(changes)
    body["receipt_digest"] = (
        hiob_contracts.derive_storyboard_image_provider_receipt_digest_v1(body)
    )
    return body


def _image_from_provider_receipt(
    receipt: dict[str, Any] | BaseModel,
) -> dict[str, Any]:
    value = (
        receipt.model_dump(mode="json")
        if isinstance(receipt, BaseModel)
        else deepcopy(receipt)
    )
    request = value["request"]
    body: dict[str, Any] = {
        "contract_version": "StoryboardImageArtifactRef.v1",
        "source_beat_index": request["source_beat_index"],
        "artifact_id": value["artifact_id"],
        "storage_key": value["storage_key"],
        "sha256": value["sha256"],
        "mime": value["mime"],
        "width": value["width"],
        "height": value["height"],
        "provider_receipt_digest": value["receipt_digest"],
        "frame_plan_digest": request["frame_plan"]["plan_digest"],
        "generation_nonce": request["generation_nonce"],
    }
    return _sealed(
        body,
        digest_field="artifact_digest",
        derive=derive_storyboard_image_artifact_digest_v1,
    )


def _image(source_beat_index: int, **changes: Any) -> dict[str, Any]:
    generation_nonce = changes.get(
        "generation_nonce",
        hiob_contracts.derive_storyboard_image_generation_nonce_v1(
            authority_idempotency_key=DRAFT_AUTHORITY_IDEMPOTENCY_KEY,
            purpose="storyboard_draft",
            source_beat_index=source_beat_index,
        ),
    )
    request = _image_provider_request(
        source_beat_index,
        generation_nonce=generation_nonce,
    )
    artifact_changes = {
        field: changes[field]
        for field in (
            "artifact_id",
            "storage_key",
            "sha256",
            "mime",
            "width",
            "height",
        )
        if field in changes
    }
    receipt = _image_provider_receipt(
        request,
        source_beat_index,
        **artifact_changes,
    )
    body: dict[str, Any] = {
        "contract_version": "StoryboardImageArtifactRef.v1",
        "source_beat_index": source_beat_index,
        "artifact_id": receipt["artifact_id"],
        "storage_key": receipt["storage_key"],
        "sha256": receipt["sha256"],
        "mime": receipt["mime"],
        "width": receipt["width"],
        "height": receipt["height"],
        "provider_receipt_digest": receipt["receipt_digest"],
        "frame_plan_digest": request["frame_plan"]["plan_digest"],
        "generation_nonce": request["generation_nonce"],
    }
    body.update(changes)
    return _sealed(
        body,
        digest_field="artifact_digest",
        derive=derive_storyboard_image_artifact_digest_v1,
    )


def _image_set(
    *,
    images: list[dict[str, Any]] | None = None,
    provider_receipts: list[dict[str, Any]] | None = None,
    **changes: Any,
):
    selected_images = images if images is not None else [_image(i) for i in range(16)]
    selected_receipts = provider_receipts or [
        _image_provider_receipt(
            _image_provider_request(
                image["source_beat_index"],
                generation_nonce=image["generation_nonce"],
            ),
            image["source_beat_index"],
            artifact_id=image["artifact_id"],
            storage_key=image["storage_key"],
            sha256=image["sha256"],
            mime=image["mime"],
            width=image["width"],
            height=image["height"],
        )
        for image in selected_images
    ]
    body: dict[str, Any] = {
        "contract_version": "StoryboardImageSetReceipt.v1",
        "receipt_id": "storyboard-image-set-1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "plan_digest": PLAN_DIGEST,
        "paid_budget_authority_digest": DRAFT_AUTHORITY_DIGEST,
        "paid_source_beat_indices": list(range(16)),
        "previous_image_set_receipt_digest": None,
        "expected_image_count": 16,
        "images": selected_images,
        "provider_receipts": selected_receipts,
        "completed_at_utc": "2026-08-14T05:30:00Z",
    }
    body.update(changes)
    sealed = _sealed(
        body,
        digest_field="receipt_digest",
        derive=derive_storyboard_image_set_receipt_digest_v1,
    )
    return StoryboardImageSetReceiptV1.model_validate(sealed)


def _card(
    source_beat_index: int,
    sequence_index: int,
    *,
    image: StoryboardImageArtifactRefV1,
    **changes: Any,
) -> dict[str, Any]:
    beat_text = f"immutable beat text {source_beat_index}"
    body: dict[str, Any] = {
        "contract_version": "StoryboardCard.v1",
        "source_beat_index": source_beat_index,
        "sequence_index": sequence_index,
        "scene_id": f"scene-{source_beat_index // 2:02d}",
        "beat_text": beat_text,
        "beat_identity_digest": derive_storyboard_beat_identity_digest_v1(
            PLAN_DIGEST, source_beat_index, beat_text
        ),
        "prompt_override": None,
        "crop_mode": "cover",
        "focal_x_basis_points": 5_000,
        "focal_y_basis_points": 5_000,
        "motion_note": None,
        "selected_artifact": {
            "artifact_id": image.artifact_id,
            "artifact_digest": image.artifact_digest,
        },
    }
    body.update(changes)
    return _sealed(
        body,
        digest_field="card_digest",
        derive=derive_storyboard_card_digest_v1,
    )


def _cards(
    image_set: StoryboardImageSetReceiptV1,
    order: list[int] | None = None,
) -> list[dict[str, Any]]:
    source_order = order if order is not None else list(range(16))
    images = {image.source_beat_index: image for image in image_set.images}
    return [
        _card(source, sequence, image=images[source])
        for sequence, source in enumerate(source_order)
    ]


def _draft(
    image_set: StoryboardImageSetReceiptV1,
    *,
    cards: list[dict[str, Any]] | None = None,
    revision: int = 1,
    parent_draft_digest: str | None = None,
    **changes: Any,
) -> StoryboardDraftV1:
    body: dict[str, Any] = {
        "contract_version": "StoryboardDraft.v1",
        "draft_id": DRAFT_ID,
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "plan_digest": PLAN_DIGEST,
        "image_set_receipt_digest": image_set.receipt_digest,
        "revision": revision,
        "parent_draft_digest": parent_draft_digest,
        "cards": cards if cards is not None else _cards(image_set),
    }
    body.update(changes)
    sealed = _sealed(
        body,
        digest_field="draft_digest",
        derive=derive_storyboard_draft_digest_v1,
    )
    return StoryboardDraftV1.model_validate(sealed)


def _approval(
    draft: StoryboardDraftV1,
    image_set: StoryboardImageSetReceiptV1,
    **changes: Any,
) -> StoryboardApprovalReceiptV1:
    body: dict[str, Any] = {
        "contract_version": "StoryboardApprovalReceipt.v1",
        "receipt_id": "storyboard-approval-1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "plan_digest": PLAN_DIGEST,
        "draft_id": draft.draft_id,
        "draft_revision": draft.revision,
        "storyboard_draft_digest": draft.draft_digest,
        "image_set_receipt_digest": image_set.receipt_digest,
        "approver_account_id": "account-owner",
        "decision": "approved",
        "policy_version": "storyboard-editor-approval-v1",
        "approved_at_utc": "2026-08-14T05:10:00Z",
        "transaction_audit_id": "storyboard-approval-1",
    }
    body.update(changes)
    sealed = _sealed(
        body,
        digest_field="receipt_digest",
        derive=derive_storyboard_approval_receipt_digest_v1,
    )
    return StoryboardApprovalReceiptV1.model_validate(sealed)


def _calls(
    purpose: str,
    image_count: int = 16,
    storyboard_scene_count: int = 8,
) -> dict[str, int]:
    if purpose == "storyboard_draft":
        return {
            "script": 1,
            "image": 16,
            "video": 0,
            "voice": 0,
            "render": 0,
            "retries": 0,
            "fallbacks": 0,
            "character_lock": 0,
        }
    if purpose == "storyboard_regen":
        return {
            "script": 0,
            "image": image_count,
            "video": 0,
            "voice": 0,
            "render": 0,
            "retries": 0,
            "fallbacks": 0,
            "character_lock": 0,
        }
    return {
        "script": 0,
        "image": 0,
        "video": storyboard_scene_count,
        "voice": 16,
        "render": 1,
        "retries": 0,
        "fallbacks": 0,
        "character_lock": 0,
    }


def _authority(
    purpose: str,
    *,
    image_source_beat_indices: list[int] | None = None,
    **changes: Any,
) -> dict[str, Any]:
    if image_source_beat_indices is None:
        image_source_beat_indices = (
            list(range(16)) if purpose == "storyboard_draft" else []
        )
    image_count = len(image_source_beat_indices)
    storyboard_scene_count = 8 if purpose == "final_production" else None
    body: dict[str, Any] = {
        "contract_version": "FactoryPaidBudgetAuthority.v2",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "all_beat_count": 16,
        "purpose": purpose,
        "plan_digest": None if purpose == "storyboard_draft" else PLAN_DIGEST,
        "storyboard_draft_digest": (
            None if purpose == "storyboard_draft" else sha256_digest({"draft": 1})
        ),
        "storyboard_approval_receipt_digest": (
            sha256_digest({"storyboard_approval": 1})
            if purpose == "final_production"
            else None
        ),
        "storyboard_scene_count": storyboard_scene_count,
        "image_source_beat_indices": image_source_beat_indices,
        "paid_calls": _calls(
            purpose,
            image_count,
            storyboard_scene_count or 8,
        ),
        "max_total_cost_microunits": 20_000_000,
        "currency": "USD",
        "cost_profile_digest": COST_PROFILE_DIGEST,
        "pricing_policy_revision": 4,
        "approval_receipt_id": f"paid-approval-{purpose}",
        "approval_receipt_digest": sha256_digest(
            {"paid_approval": purpose, "beats": image_source_beat_indices}
        ),
    }
    body.update(changes)
    body["approval_subject_digest"] = (
        derive_factory_paid_budget_approval_subject_digest_v2(body)
    )
    body["idempotency_key"] = derive_factory_paid_budget_idempotency_key_v2(body)
    body["authority_digest"] = derive_factory_paid_budget_authority_digest_v2(body)
    return body


def _paid_approval_receipt_v2(
    purpose: str,
    *,
    image_source_beat_indices: list[int] | None = None,
    **changes: Any,
) -> FactoryPaidBudgetApprovalReceiptV2:
    profile = _cost_profile()
    selected_indices = (
        image_source_beat_indices
        if image_source_beat_indices is not None
        else list(range(16))
        if purpose == "storyboard_draft"
        else []
    )
    changes.setdefault("cost_profile_digest", profile["profile_digest"])
    changes.setdefault("pricing_policy_revision", profile["pricing_policy_revision"])
    changes.setdefault(
        "max_total_cost_microunits",
        _profile_worst_case_cost(
            profile,
            purpose=purpose,
            image_count=len(selected_indices),
            scene_count=(
                int(changes.get("storyboard_scene_count", 8))
                if purpose == "final_production"
                else 0
            ),
        ),
    )
    authority = _authority(
        purpose,
        image_source_beat_indices=image_source_beat_indices,
        cost_profile_digest=changes["cost_profile_digest"],
        pricing_policy_revision=changes["pricing_policy_revision"],
        max_total_cost_microunits=changes["max_total_cost_microunits"],
    )
    body: dict[str, Any] = {
        "contract_version": "FactoryPaidBudgetApprovalReceipt.v2",
        "receipt_id": authority["approval_receipt_id"],
        "workspace_id": authority["workspace_id"],
        "run_id": authority["run_id"],
        "factory_revision": authority["factory_revision"],
        "all_beat_count": authority["all_beat_count"],
        "purpose": authority["purpose"],
        "plan_digest": authority["plan_digest"],
        "storyboard_draft_digest": authority["storyboard_draft_digest"],
        "storyboard_approval_receipt_digest": authority[
            "storyboard_approval_receipt_digest"
        ],
        "storyboard_scene_count": authority["storyboard_scene_count"],
        "image_source_beat_indices": authority["image_source_beat_indices"],
        "paid_calls": authority["paid_calls"],
        "max_total_cost_microunits": authority["max_total_cost_microunits"],
        "currency": authority["currency"],
        "cost_profile_digest": authority["cost_profile_digest"],
        "pricing_policy_revision": authority["pricing_policy_revision"],
        "approval_subject_digest": authority["approval_subject_digest"],
        "approver_account_id": "account-owner",
        "decision": "approved",
        "policy_version": "factory-paid-budget.v2",
        "state_revision": 2,
        "approved_at_utc": "2026-08-14T05:00:00Z",
        "expires_at_utc": "2026-08-14T07:00:00Z",
        "revoked_at_utc": None,
        "transaction_audit_id": authority["approval_receipt_id"],
    }
    body.update(changes)
    body["approval_subject_digest"] = (
        derive_factory_paid_budget_approval_subject_digest_v2(body)
    )
    body["receipt_digest"] = derive_factory_paid_budget_approval_receipt_digest_v2(body)
    return FactoryPaidBudgetApprovalReceiptV2.model_validate(body)


def _authority_bound_to_receipt(
    receipt: FactoryPaidBudgetApprovalReceiptV2,
) -> dict[str, Any]:
    body = _authority(
        receipt.purpose,
        image_source_beat_indices=list(receipt.image_source_beat_indices),
        storyboard_draft_digest=receipt.storyboard_draft_digest,
        storyboard_approval_receipt_digest=(receipt.storyboard_approval_receipt_digest),
        storyboard_scene_count=receipt.storyboard_scene_count,
        paid_calls=receipt.paid_calls.model_dump(mode="json"),
        max_total_cost_microunits=receipt.max_total_cost_microunits,
        currency=receipt.currency,
        cost_profile_digest=receipt.cost_profile_digest,
        pricing_policy_revision=receipt.pricing_policy_revision,
        approval_receipt_id=receipt.receipt_id,
        approval_receipt_digest=receipt.receipt_digest,
    )
    return body


def _cost_profile() -> dict[str, Any]:
    body: dict[str, Any] = {
        "contract_version": "FactoryCostProfile.v1",
        "profile_id": "storyboard-profile-v1",
        "currency": "USD",
        "pricing_policy_revision": 4,
        "valid_from_utc": "2026-08-14T00:00:00Z",
        "valid_until_utc": "2026-08-15T00:00:00Z",
        "all_beat_count": 16,
        "purpose_policies": {
            "storyboard_draft": {
                "script": 1,
                "image": 16,
                "video": 0,
                "voice": 0,
                "render": 0,
            },
            "storyboard_regen": {
                "script": 0,
                "image": "selected",
                "video": 0,
                "voice": 0,
                "render": 0,
            },
            "final_production": {
                "script": 0,
                "image": 0,
                "video": "approved_scene_count",
                "voice": 16,
                "render": 1,
            },
        },
        "operations": {
            "script": {
                "provider": "openai",
                "model": "gpt-5.6-sol",
                "billing_unit": "call",
                "rate_microunits": 2_000_000,
                "max_units_per_operation": 1,
            },
            "image": {
                "provider": "seedream",
                "model": "seedream-5-pro",
                "billing_unit": "call",
                "rate_microunits": 160_000,
                "max_units_per_operation": 1,
            },
            "video": {
                "provider": "piapi",
                "model": "kling-3.0-omni",
                "billing_unit": "second",
                "rate_microunits": 100_000,
                "max_units_per_operation": 4,
            },
            "voice": {
                "provider": "typecast",
                "model": "ssfm-v30",
                "billing_unit": "character",
                "rate_microunits": 90,
                "max_units_per_operation": 200,
            },
            "render": {
                "provider": "modal",
                "model": "hephaestus-final-render-v2",
                "billing_unit": "call",
                "rate_microunits": 2_000_000,
                "max_units_per_operation": 1,
            },
        },
    }
    return {
        **body,
        "profile_digest": derive_factory_cost_profile_digest_v1(body),
    }


def _profile_worst_case_cost(
    profile: dict[str, Any],
    *,
    purpose: str,
    image_count: int = 0,
    scene_count: int = 0,
) -> int:
    operations = profile["operations"]
    if purpose == "storyboard_draft":
        return (
            operations["script"]["rate_microunits"]
            + 16 * operations["image"]["rate_microunits"]
        )
    if purpose == "storyboard_regen":
        return image_count * operations["image"]["rate_microunits"]
    return (
        scene_count
        * operations["video"]["rate_microunits"]
        * operations["video"]["max_units_per_operation"]
        + 16
        * operations["voice"]["rate_microunits"]
        * operations["voice"]["max_units_per_operation"]
        + operations["render"]["rate_microunits"]
    )


def _paid_resolution_v2(
    receipt: FactoryPaidBudgetApprovalReceiptV2,
    *,
    profile: dict[str, Any] | FactoryCostProfileV1 | None = None,
) -> FactoryPaidBudgetResolutionV2:
    return FactoryPaidBudgetResolutionV2.model_validate(
        {
            "approval_receipt": receipt,
            "cost_profile": profile if profile is not None else _cost_profile(),
            "paid_budget_authority": _authority_bound_to_receipt(receipt),
        }
    )


def _verified_paid_authority_v2(
    receipt: FactoryPaidBudgetApprovalReceiptV2,
    *,
    profile: dict[str, Any] | FactoryCostProfileV1 | None = None,
    at_utc: str = "2026-08-14T06:00:00Z",
    resolver: FactoryPaidBudgetApprovalResolverV2 | None = None,
) -> VerifiedFactoryPaidBudgetAuthorityV2:
    return _paid_resolution_v2(receipt, profile=profile).from_verified(
        at_utc=at_utc,
        resolver=resolver if resolver is not None else _ApprovalResolverV2(),
    )


def _image_set_for_paid_receipt(
    paid_receipt: FactoryPaidBudgetApprovalReceiptV2,
    *,
    previous_image_set: StoryboardImageSetReceiptV1 | None = None,
) -> StoryboardImageSetReceiptV1:
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(paid_receipt)
    )
    previous_receipts = (
        list(previous_image_set.provider_receipts)
        if previous_image_set is not None
        else []
    )
    receipts: list[dict[str, Any] | BaseModel] = []
    selected = set(authority.image_source_beat_indices)
    for source_beat_index in range(16):
        if source_beat_index not in selected:
            receipts.append(previous_receipts[source_beat_index])
            continue
        request = _image_provider_request(
            source_beat_index,
            purpose=authority.purpose,
            paid_budget_authority_digest=authority.authority_digest,
            authority_idempotency_key=authority.idempotency_key,
        )
        receipts.append(_image_provider_receipt(request, source_beat_index))
    images = [_image_from_provider_receipt(receipt) for receipt in receipts]
    return _image_set(
        images=images,
        provider_receipts=[
            receipt.model_dump(mode="json")
            if isinstance(receipt, BaseModel)
            else receipt
            for receipt in receipts
        ],
        paid_budget_authority_digest=authority.authority_digest,
        paid_source_beat_indices=list(authority.image_source_beat_indices),
        previous_image_set_receipt_digest=(
            previous_image_set.receipt_digest
            if previous_image_set is not None
            else None
        ),
    )


def _storyboard_carrier(
    draft: StoryboardDraftV1,
    image_set: StoryboardImageSetReceiptV1,
) -> FactoryStoryboardCarrierV1:
    return FactoryStoryboardCarrierV1.model_validate(
        {
            "contract_version": "FactoryStoryboardCarrier.v1",
            "storyboard_revision": draft.revision,
            "storyboard_digest": draft.draft_digest,
            "image_set_receipt_digest": image_set.receipt_digest,
            "approval_receipt_digest": None,
            "execution_manifest_digest": None,
        }
    )


def _phase_a_completion(
    *,
    purpose: str = "storyboard_draft",
    input_draft: StoryboardDraftV1 | None = None,
    input_image_set: StoryboardImageSetReceiptV1 | None = None,
) -> Any:
    selected = list(range(16)) if purpose == "storyboard_draft" else [0]
    paid_receipt = _paid_approval_receipt_v2(
        purpose,
        image_source_beat_indices=selected,
        **(
            {"storyboard_draft_digest": input_draft.draft_digest}
            if input_draft is not None
            else {}
        ),
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(paid_receipt)
    )
    output_image_set = _image_set_for_paid_receipt(
        paid_receipt,
        previous_image_set=input_image_set,
    )
    output_draft = _draft(
        output_image_set,
        revision=1 if input_draft is None else input_draft.revision + 1,
        parent_draft_digest=(None if input_draft is None else input_draft.draft_digest),
    )
    carrier = _storyboard_carrier(output_draft, output_image_set)
    paid_digests = [
        output_image_set.provider_receipts[index].receipt_digest for index in selected
    ]
    body: dict[str, Any] = {
        "contract_version": "StoryboardPhaseACompletionReceipt.v1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "purpose": purpose,
        "plan_digest": PLAN_DIGEST,
        "ares_script_revision_digest": ARES_SCRIPT_REVISION_DIGEST,
        "ares_beat_plan_revision_digest": ARES_BEAT_PLAN_REVISION_DIGEST,
        "paid_budget_approval_receipt": paid_receipt,
        "paid_budget_authority": authority,
        "paid_budget_authority_digest": authority.authority_digest,
        "paid_source_beat_indices": selected,
        "input_storyboard_draft": input_draft,
        "input_image_set_receipt": input_image_set,
        "paid_image_provider_receipt_digests": paid_digests,
        "output_image_set_receipt": output_image_set,
        "output_storyboard_draft": output_draft,
        "output_storyboard_carrier": carrier,
        "completed_at_utc": "2026-08-14T05:40:00Z",
    }
    body["receipt_digest"] = (
        hiob_contracts.derive_storyboard_phase_a_completion_receipt_digest_v1(body)
    )
    return hiob_contracts.StoryboardPhaseACompletionReceiptV1.model_validate(body)


def _manifest(
    draft: StoryboardDraftV1,
    image_set: StoryboardImageSetReceiptV1,
    approval: StoryboardApprovalReceiptV1,
    **changes: Any,
) -> StoryboardExecutionManifestV1:
    images_by_source = {image.source_beat_index: image for image in image_set.images}
    body: dict[str, Any] = {
        "contract_version": "StoryboardExecutionManifest.v1",
        "manifest_id": MANIFEST_ID,
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "plan_digest": PLAN_DIGEST,
        "draft_id": draft.draft_id,
        "draft_revision": draft.revision,
        "storyboard_draft_digest": draft.draft_digest,
        "image_set_receipt_digest": image_set.receipt_digest,
        "storyboard_approval_receipt_digest": approval.receipt_digest,
        "final_production_authority_digest": FINAL_AUTHORITY_DIGEST,
        "cards": [card.model_dump(mode="json") for card in draft.cards],
        "images": [
            images_by_source[card.source_beat_index].model_dump(mode="json")
            for card in draft.cards
        ],
        "scenes": [
            scene.model_dump(mode="json")
            for scene in derive_storyboard_scenes_v1(draft.cards)
        ],
    }
    body.update(changes)
    sealed = _sealed(
        body,
        digest_field="manifest_digest",
        derive=derive_storyboard_execution_manifest_digest_v1,
    )
    return StoryboardExecutionManifestV1.model_validate(sealed)


def _scene_video_artifact(scene_sequence_index: int) -> dict[str, Any]:
    body: dict[str, Any] = {
        "artifact_id": f"scene-video-{scene_sequence_index:02d}",
        "storage_key": (
            f"workspaces/{WORKSPACE_ID}/runs/{RUN_ID}/"
            f"scene-videos/{scene_sequence_index:02d}.mp4"
        ),
        "sha256": sha256_digest({"scene_video": scene_sequence_index}),
        "mime": "video/mp4",
        "bytes_len": 4_096 + scene_sequence_index,
        "duration_ms": 4_000,
        "width": 720,
        "height": 1_280,
    }
    return _sealed(
        body,
        digest_field="artifact_digest",
        derive=derive_storyboard_scene_video_artifact_digest_v1,
    )


def _scene_video_receipt(
    request: dict[str, Any],
    scene_sequence_index: int,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "contract_version": "StoryboardSceneVideoReceipt.v1",
        "request": request,
        "provider_job_id": f"scene-job-{scene_sequence_index:02d}",
        "status": "succeeded",
        "artifact": _scene_video_artifact(scene_sequence_index),
    }
    return _sealed(
        body,
        digest_field="receipt_digest",
        derive=derive_storyboard_scene_video_receipt_digest_v1,
    )


def _scene_video_request(
    manifest: StoryboardExecutionManifestV1,
    final_authority: FactoryPaidBudgetAuthorityV2,
    scene_sequence_index: int = 0,
    *,
    cost_profile: dict[str, Any] | FactoryCostProfileV1 | None = None,
    **changes: Any,
) -> dict[str, Any]:
    profile = FactoryCostProfileV1.model_validate(
        cost_profile if cost_profile is not None else _cost_profile()
    )
    scene = manifest.scenes[scene_sequence_index]
    anchor_card = next(
        card
        for card in manifest.cards
        if card.source_beat_index == scene.source_beat_indices[0]
    )
    anchor_image = next(
        image
        for image in manifest.images
        if image.source_beat_index == anchor_card.source_beat_index
    )
    body: dict[str, Any] = {
        "contract_version": "StoryboardSceneVideoRequest.v1",
        "workspace_id": manifest.workspace_id,
        "run_id": manifest.run_id,
        "factory_revision": manifest.factory_revision,
        "plan_digest": manifest.plan_digest,
        "storyboard_execution_manifest_digest": manifest.manifest_digest,
        "final_production_authority_digest": final_authority.authority_digest,
        "scene_sequence_index": scene_sequence_index,
        "scene_id": scene.scene_id,
        "scene_digest": scene.scene_digest,
        "anchor": {
            "source_beat_index": anchor_card.source_beat_index,
            "beat_identity_digest": anchor_card.beat_identity_digest,
            "prompt_override": anchor_card.prompt_override,
            "crop_mode": anchor_card.crop_mode,
            "focal_x_basis_points": anchor_card.focal_x_basis_points,
            "focal_y_basis_points": anchor_card.focal_y_basis_points,
            "motion_note": anchor_card.motion_note,
            "selected_artifact": anchor_card.selected_artifact.model_dump(mode="json"),
        },
        "anchor_image": anchor_image.model_dump(mode="json"),
        "generation_nonce": (
            f"00000000-0000-4000-8000-{scene_sequence_index + 800:012d}"
        ),
        "duration_ms": 4_000,
        "fps": 24,
        "width": 720,
        "height": 1_280,
        "audio_mode": "none",
        "provider": profile.operations.video.provider,
        "model": profile.operations.video.model,
        "cost_profile_digest": profile.profile_digest,
        "pricing_policy_revision": profile.pricing_policy_revision,
    }
    body.update(changes)
    return _reseal_scene_video_request(body)


def _reseal_scene_video_request(body: dict[str, Any]) -> dict[str, Any]:
    body["request_digest"] = derive_storyboard_scene_video_request_digest_v1(body)
    body["execution_request_digest"] = (
        derive_storyboard_scene_video_execution_request_digest_v1(body)
    )
    body["idempotency_key"] = derive_storyboard_scene_video_idempotency_key_v1(body)
    return body


def _verified_scene_video_requests(
    manifest: StoryboardExecutionManifestV1,
    authority: VerifiedFactoryPaidBudgetAuthorityV2,
    *,
    resolver: FactoryPaidBudgetApprovalResolverV2 | None = None,
) -> tuple[VerifiedStoryboardSceneVideoRequestV1, ...]:
    current_approval_resolver = resolver or _ApprovalResolverV2()
    return tuple(
        StoryboardSceneVideoRequestV1.from_verified(
            _scene_video_request(
                manifest,
                authority.authority,
                scene_sequence_index,
                cost_profile=authority.cost_profile,
            ),
            manifest=manifest,
            authority=authority,
            at_utc="2026-08-14T06:00:00Z",
            resolver=current_approval_resolver,
        )
        for scene_sequence_index in range(len(manifest.scenes))
    )


def _beat_scene_video_projection(
    *,
    card: Any,
    scene: StoryboardSceneV1,
    scene_sequence_index: int,
    artifact: dict[str, Any],
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "contract_version": "StoryboardBeatSceneVideoProjection.v1",
        "sequence_index": card.sequence_index,
        "source_beat_index": card.source_beat_index,
        "scene_sequence_index": scene_sequence_index,
        "scene_digest": scene.scene_digest,
        "video_artifact_id": artifact["artifact_id"],
        "video_artifact_digest": artifact["artifact_digest"],
        "repeat_index": scene.source_beat_indices.index(card.source_beat_index),
    }
    return _sealed(
        body,
        digest_field="projection_digest",
        derive=derive_storyboard_beat_scene_video_projection_digest_v1,
    )


def _scene_video_set(
    manifest: StoryboardExecutionManifestV1,
    final_authority: FactoryPaidBudgetAuthorityV2,
    **changes: Any,
) -> StoryboardSceneVideoSetReceiptV1:
    profile = _cost_profile()
    scene_requests = [
        _scene_video_request(
            manifest,
            final_authority,
            index,
            cost_profile=profile,
        )
        for index in range(len(manifest.scenes))
    ]
    scene_video_receipts = [
        _scene_video_receipt(
            scene_requests[index],
            index,
        )
        for index in range(len(manifest.scenes))
    ]
    scene_by_source = {
        source_beat_index: (index, scene)
        for index, scene in enumerate(manifest.scenes)
        for source_beat_index in scene.source_beat_indices
    }
    beat_projections = []
    for card in manifest.cards:
        scene_sequence_index, scene = scene_by_source[card.source_beat_index]
        beat_projections.append(
            _beat_scene_video_projection(
                card=card,
                scene=scene,
                scene_sequence_index=scene_sequence_index,
                artifact=scene_video_receipts[scene_sequence_index]["artifact"],
            )
        )
    body: dict[str, Any] = {
        "contract_version": "StoryboardSceneVideoSetReceipt.v1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "plan_digest": PLAN_DIGEST,
        "storyboard_execution_manifest_digest": manifest.manifest_digest,
        "final_production_authority_digest": final_authority.authority_digest,
        "storyboard_scene_count": len(manifest.scenes),
        "scene_video_receipts": scene_video_receipts,
        "beat_projections": beat_projections,
        "completed_at_utc": "2026-08-14T06:30:00Z",
    }
    body.update(changes)
    return StoryboardSceneVideoSetReceiptV1.model_validate(
        _sealed(
            body,
            digest_field="receipt_digest",
            derive=derive_storyboard_scene_video_set_receipt_digest_v1,
        )
    )


def _audio_artifact(source_beat_index: int) -> dict[str, Any]:
    artifact_id = f"voice-beat-{source_beat_index:02d}.mp3"
    return {
        "artifact_id": artifact_id,
        "kind": "audio",
        "uri": f"factory-artifacts/{artifact_id}",
        "sha256": sha256_digest({"voice": source_beat_index}),
        "mime": "audio/mpeg",
        "bytes_len": 2_048 + source_beat_index,
        "duration_ms": 4_000,
        "width": None,
        "height": None,
        "beat_index": source_beat_index,
        "producer_planet": "orpheus",
        "producer_node_id": "voice.materialize",
        "execution_id": f"voice-exec-{source_beat_index:02d}",
        "producer_revision": "rev-1",
        "image_digest": None,
        "source_output_digests": [],
        "edge_receipt_digests": [],
        "provenance_refs": [],
        "consent_refs": [],
    }


def _scene_fan_in(
    manifest: StoryboardExecutionManifestV1,
    final_authority: FactoryPaidBudgetAuthorityV2,
    scene_video_set: StoryboardSceneVideoSetReceiptV1,
    **changes: Any,
) -> StoryboardSceneFanInManifestV1:
    audio_artifacts = [
        _audio_artifact(card.source_beat_index) for card in manifest.cards
    ]
    body: dict[str, Any] = {
        "contract_version": "StoryboardSceneFanInManifest.v1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "plan_digest": PLAN_DIGEST,
        "paid_budget_authority_digest": final_authority.authority_digest,
        "storyboard_execution_manifest_digest": manifest.manifest_digest,
        "storyboard_scene_video_set_receipt": scene_video_set,
        "storyboard_scene_video_set_receipt_digest": scene_video_set.receipt_digest,
        "audio_artifacts": audio_artifacts,
        "timeline_digest": sha256_digest({"timeline": "storyboard-scenes"}),
        "audio_mix_digest": canonical_contract_digest_v1(
            {"audio_artifacts": audio_artifacts}
        ),
        "render_policy_digest": sha256_digest({"render_policy": "storyboard-scenes"}),
    }
    body.update(changes)
    return StoryboardSceneFanInManifestV1.model_validate(
        _sealed(
            body,
            digest_field="manifest_digest",
            derive=derive_storyboard_scene_fan_in_manifest_digest_v1,
        )
    )


def _final_render_receipt(fan_in_manifest_digest: str) -> dict[str, Any]:
    artifact = {
        "artifact_id": "final-storyboard-reel.mp4",
        "kind": "video",
        "uri": "factory-artifacts/final-storyboard-reel.mp4",
        "sha256": sha256_digest({"artifact": "final-storyboard-reel"}),
        "mime": "video/mp4",
        "bytes_len": 8_192,
        "duration_ms": 64_000,
        "width": 1_080,
        "height": 1_920,
        "beat_index": None,
        "producer_planet": "hephaestus",
        "producer_node_id": "video.materialize",
        "execution_id": "exec-final-storyboard-reel",
        "producer_revision": "rev-1",
        "image_digest": None,
        "source_output_digests": [],
        "edge_receipt_digests": [],
        "provenance_refs": [],
        "consent_refs": [],
    }
    body: dict[str, Any] = {
        "contract_version": "HephaestusFinalRenderReceipt.v2",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "fan_in_manifest_digest": fan_in_manifest_digest,
        "status": "ready",
        "output_artifact": artifact,
        "output_url": "https://cdn.example/final-storyboard-reel.mp4",
        "mechanical_qa_passed": True,
        "rendered_at_utc": "2026-08-14T06:40:00Z",
    }
    return _sealed(
        body,
        digest_field="receipt_digest",
        derive=lambda value: canonical_contract_digest_v1(
            value,
            exclude={"receipt_digest"},
        ),
    )


def _factory_receipt_v3(
    manifest: StoryboardExecutionManifestV1,
    final_authority: FactoryPaidBudgetAuthorityV2,
    scene_video_set: StoryboardSceneVideoSetReceiptV1,
    fan_in: StoryboardSceneFanInManifestV1,
) -> dict[str, Any]:
    final_render = _final_render_receipt(fan_in.manifest_digest)
    body: dict[str, Any] = {
        "contract_version": "ReelsFactoryReceipt.v3",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "plan_digest": PLAN_DIGEST,
        "paid_budget_authority_digest": final_authority.authority_digest,
        "storyboard_execution_manifest_digest": manifest.manifest_digest,
        "storyboard_scene_video_set_receipt_digest": scene_video_set.receipt_digest,
        "fan_in_manifest_digest": fan_in.manifest_digest,
        "fan_in_manifest": fan_in,
        "final_render_receipt": final_render,
        "status": "succeeded",
        "output_url": final_render["output_url"],
        "output_sha256": final_render["output_artifact"]["sha256"],
    }
    return _sealed(
        body,
        digest_field="receipt_digest",
        derive=derive_reels_factory_receipt_digest_v3,
    )


def test_image_ref_is_url_free_strict_frozen_and_digest_bound() -> None:
    image = StoryboardImageArtifactRefV1.model_validate(_image(0))

    assert image.source_beat_index == 0
    assert image.storage_key == _image_provider_request(0)["expected_storage_key"]
    assert "url" not in StoryboardImageArtifactRefV1.model_fields
    assert image.artifact_digest == derive_storyboard_image_artifact_digest_v1(image)
    with pytest.raises((ValidationError, TypeError)):
        image.storage_key = "other.webp"


@pytest.mark.parametrize(
    "storage_key",
    [
        "https://cdn.example/image.webp",
        "http://cdn.example/image.webp",
        "data:image/png;base64,AAAA",
        "file:///tmp/image.webp",
        "/absolute/image.webp",
        "../escape.webp",
        "storyboard/image.webp?token=secret",
        "storyboard\\image.webp",
    ],
)
def test_image_ref_rejects_url_absolute_or_credential_bearing_storage_keys(
    storage_key: str,
) -> None:
    with pytest.raises(ValidationError, match="storage_key"):
        StoryboardImageArtifactRefV1.model_validate(_image(0, storage_key=storage_key))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_beat_index", 16),
        ("source_beat_index", True),
        ("width", 0),
        ("height", 1.5),
        ("mime", "video/mp4"),
        ("generation_nonce", "not-a-uuid"),
        ("artifact_id", "x" * 241),
        ("artifact_id", "https://signed.example/image.webp"),
        ("artifact_id", " padded-artifact-id "),
    ],
)
def test_image_ref_rejects_noncanonical_fields(field: str, value: Any) -> None:
    payload = _image(0)
    payload[field] = value
    with pytest.raises(ValidationError):
        StoryboardImageArtifactRefV1.model_validate(payload)


def test_image_frame_plan_is_lossless_strict_beat_frame_plan_v1_projection() -> None:
    legacy = hiob_contracts.BeatFramePlanV1.create(
        run_id=RUN_ID,
        workspace_id=WORKSPACE_ID,
        beat_index=0,
        shot_list_digest=sha256_digest({"shot_list": 0}),
        render_mode="product_solo",
        ordered_refs=(),
        shot={"beat_index": 0, "shot_size": "mcu"},
        prompt="approved storyboard still prompt 0",
        prompt_constitution_version="visual-constitution.v1",
    )

    projected = hiob_contracts.StoryboardImageFramePlanV1.model_validate(
        legacy.to_dict()
    )

    assert projected.model_dump(mode="json") == legacy.to_dict()
    assert projected.plan_digest == legacy.plan_digest

    tampered = legacy.to_dict()
    tampered["prompt"] = "unsealed prompt mutation"
    with pytest.raises(ValidationError, match="plan_digest"):
        hiob_contracts.StoryboardImageFramePlanV1.model_validate(tampered)

    extra = legacy.to_dict()
    extra["engine"] = {"fallback": "gpt-image"}
    with pytest.raises(ValidationError, match="Extra inputs"):
        hiob_contracts.StoryboardImageFramePlanV1.model_validate(extra)


def test_image_provider_request_requires_fresh_profile_resolved_authority() -> None:
    script_revision, plan_revision = _ares_revision_pair()
    athena_receipt = _athena_frame_plan_receipt(script_revision, plan_revision)
    profile = _cost_profile()
    paid_receipt = _paid_approval_receipt_v2(
        "storyboard_draft",
        cost_profile_digest=profile["profile_digest"],
        pricing_policy_revision=profile["pricing_policy_revision"],
        max_total_cost_microunits=_profile_worst_case_cost(
            profile,
            purpose="storyboard_draft",
        ),
    )
    resolver = _ApprovalResolverV2()
    verified_authority = _verified_paid_authority_v2(
        paid_receipt,
        profile=profile,
        resolver=resolver,
    )
    payload = _image_provider_request(
        0,
        paid_budget_authority_digest=verified_authority.authority.authority_digest,
        authority_idempotency_key=verified_authority.authority.idempotency_key,
        cost_profile=profile,
        plan_digest=plan_revision.revision_digest,
        ares_script_revision_digest=script_revision.revision_digest,
        ares_beat_plan_revision_digest=plan_revision.revision_digest,
        athena_frame_plan_receipt_digest=athena_receipt["receipt_digest"],
    )
    evidence = {
        "script_revision": script_revision,
        "plan_revision": plan_revision,
        "athena_receipt": athena_receipt,
    }

    assert resolver.call_count == 1
    with pytest.raises(TypeError, match="VerifiedFactoryPaidBudgetAuthorityV2"):
        hiob_contracts.StoryboardImageProviderRequestV1.from_verified(
            payload,
            authority=verified_authority.authority,
            at_utc="2026-08-14T06:00:00Z",
            resolver=resolver,
            **evidence,
        )

    capability = hiob_contracts.StoryboardImageProviderRequestV1.from_verified(
        payload,
        authority=verified_authority,
        at_utc="2026-08-14T06:00:00Z",
        resolver=resolver,
        **evidence,
    )
    request = hiob_contracts.require_verified_storyboard_image_provider_request_v1(
        capability
    )

    assert resolver.call_count == 2
    assert request.operation_key == (
        f"reels:{WORKSPACE_ID}:{RUN_ID}:{plan_revision.revision_digest}:"
        f"{request.generation_nonce}:image:0"
    )
    assert request.expected_artifact_id == (
        hiob_contracts.derive_storyboard_image_expected_artifact_id_v1(request)
    )
    assert request.expected_storage_key == (
        hiob_contracts.derive_storyboard_image_expected_storage_key_v1(request)
    )
    assert request.execution_request_digest == (
        hiob_contracts.derive_storyboard_image_provider_execution_request_digest_v1(
            request
        )
    )
    assert request.idempotency_key == (
        hiob_contracts.derive_storyboard_image_provider_idempotency_key_v1(request)
    )
    with pytest.raises(TypeError, match="VerifiedStoryboardImageProviderRequestV1"):
        hiob_contracts.require_verified_storyboard_image_provider_request_v1(request)

    resolver.current = False
    with pytest.raises(ValueError, match="current durable approval"):
        hiob_contracts.StoryboardImageProviderRequestV1.from_verified(
            _image_provider_request(
                1,
                paid_budget_authority_digest=(
                    verified_authority.authority.authority_digest
                ),
                authority_idempotency_key=(
                    verified_authority.authority.idempotency_key
                ),
                cost_profile=profile,
                plan_digest=plan_revision.revision_digest,
                ares_script_revision_digest=script_revision.revision_digest,
                ares_beat_plan_revision_digest=plan_revision.revision_digest,
                athena_frame_plan_receipt_digest=athena_receipt["receipt_digest"],
            ),
            authority=verified_authority,
            at_utc="2026-08-14T06:01:00Z",
            resolver=resolver,
            **evidence,
        )
    assert resolver.call_count == 3

    resolver.current = True
    with pytest.raises(ValueError, match="current durable approval"):
        hiob_contracts.StoryboardImageProviderRequestV1.from_verified(
            payload,
            authority=verified_authority,
            at_utc=paid_receipt.expires_at_utc,
            resolver=resolver,
            **evidence,
        )


def test_image_provider_request_rejects_transport_or_plan_drift() -> None:
    script_revision, plan_revision = _ares_revision_pair()
    athena_receipt = _athena_frame_plan_receipt(script_revision, plan_revision)
    profile = _cost_profile()
    paid_receipt = _paid_approval_receipt_v2(
        "storyboard_draft",
        cost_profile_digest=profile["profile_digest"],
        pricing_policy_revision=profile["pricing_policy_revision"],
        max_total_cost_microunits=_profile_worst_case_cost(
            profile,
            purpose="storyboard_draft",
        ),
    )
    verified = _verified_paid_authority_v2(paid_receipt, profile=profile)
    payload = _image_provider_request(
        0,
        paid_budget_authority_digest=verified.authority.authority_digest,
        authority_idempotency_key=verified.authority.idempotency_key,
        cost_profile=profile,
        plan_digest=plan_revision.revision_digest,
        ares_script_revision_digest=script_revision.revision_digest,
        ares_beat_plan_revision_digest=plan_revision.revision_digest,
        athena_frame_plan_receipt_digest=athena_receipt["receipt_digest"],
    )
    evidence = {
        "script_revision": script_revision,
        "plan_revision": plan_revision,
        "athena_receipt": athena_receipt,
    }

    for mutation in (
        {"provider": "openai", "model": "gpt-image-2"},
        {"cost_profile_digest": sha256_digest({"profile": "alien"})},
        {"source_beat_index": 1},
        {"purpose": "final_production"},
    ):
        drift = deepcopy(payload)
        drift.update(mutation)
        _reseal_image_provider_request(drift)
        with pytest.raises((ValidationError, ValueError)):
            hiob_contracts.StoryboardImageProviderRequestV1.from_verified(
                drift,
                authority=verified,
                at_utc="2026-08-14T06:00:00Z",
                resolver=_ApprovalResolverV2(),
                **evidence,
            )

    frame_plan_drift = deepcopy(payload)
    frame_plan_drift["frame_plan"]["prompt"] = "tampered after Athena seal"
    with pytest.raises(ValidationError, match="plan_digest"):
        hiob_contracts.StoryboardImageProviderRequestV1.model_validate(frame_plan_drift)

    alternate_nonce = deepcopy(payload)
    alternate_nonce["generation_nonce"] = "00000000-0000-4000-8000-000000009999"
    _reseal_image_provider_request(alternate_nonce)
    with pytest.raises(ValueError, match="generation_nonce"):
        hiob_contracts.StoryboardImageProviderRequestV1.from_verified(
            alternate_nonce,
            authority=verified,
            at_utc="2026-08-14T06:00:00Z",
            resolver=_ApprovalResolverV2(),
            **evidence,
        )

    replay = hiob_contracts.StoryboardImageProviderRequestV1.from_verified(
        deepcopy(payload),
        authority=verified,
        at_utc="2026-08-14T06:00:00Z",
        resolver=_ApprovalResolverV2(),
        **evidence,
    )
    assert hiob_contracts.require_verified_storyboard_image_provider_request_v1(
        replay
    ) == hiob_contracts.StoryboardImageProviderRequestV1.model_validate(payload)

    alien_script, alien_plan = _ares_revision_pair(text_prefix="alien retargeted beat")
    alien_athena = _athena_frame_plan_receipt(alien_script, alien_plan)
    with pytest.raises(ValueError, match="Ares|revision|plan"):
        hiob_contracts.StoryboardImageProviderRequestV1.from_verified(
            payload,
            authority=verified,
            script_revision=alien_script,
            plan_revision=alien_plan,
            athena_receipt=alien_athena,
            at_utc="2026-08-14T06:00:00Z",
            resolver=_ApprovalResolverV2(),
        )

    athena_drift = deepcopy(athena_receipt)
    athena_drift["frame_plans"][0]["prompt"] = "self-hashed unapproved prompt"
    athena_drift["frame_plans"][0]["plan_digest"] = canonical_contract_digest_v1(
        athena_drift["frame_plans"][0],
        exclude={"plan_digest"},
    )
    athena_drift["receipt_digest"] = canonical_contract_digest_v1(
        athena_drift,
        exclude={"receipt_digest"},
    )
    drift_payload = deepcopy(payload)
    drift_payload["athena_frame_plan_receipt_digest"] = athena_drift["receipt_digest"]
    _reseal_image_provider_request(drift_payload)
    with pytest.raises(ValueError, match="Athena|frame plan"):
        hiob_contracts.StoryboardImageProviderRequestV1.from_verified(
            drift_payload,
            authority=verified,
            script_revision=script_revision,
            plan_revision=plan_revision,
            athena_receipt=athena_drift,
            at_utc="2026-08-14T06:00:00Z",
            resolver=_ApprovalResolverV2(),
        )


def test_image_provider_receipt_requires_retained_verified_request() -> None:
    script_revision, plan_revision = _ares_revision_pair()
    athena_receipt = _athena_frame_plan_receipt(script_revision, plan_revision)
    profile = _cost_profile()
    paid_receipt = _paid_approval_receipt_v2("storyboard_draft")
    verified_authority = _verified_paid_authority_v2(
        paid_receipt,
        profile=profile,
    )
    request_payload = _image_provider_request(
        0,
        paid_budget_authority_digest=verified_authority.authority.authority_digest,
        authority_idempotency_key=verified_authority.authority.idempotency_key,
        cost_profile=profile,
        plan_digest=plan_revision.revision_digest,
        ares_script_revision_digest=script_revision.revision_digest,
        ares_beat_plan_revision_digest=plan_revision.revision_digest,
        athena_frame_plan_receipt_digest=athena_receipt["receipt_digest"],
    )
    request_capability = hiob_contracts.StoryboardImageProviderRequestV1.from_verified(
        request_payload,
        authority=verified_authority,
        at_utc="2026-08-14T06:00:00Z",
        resolver=_ApprovalResolverV2(),
        script_revision=script_revision,
        plan_revision=plan_revision,
        athena_receipt=athena_receipt,
    )
    receipt_payload = _image_provider_receipt(request_payload, 0)

    receipt = hiob_contracts.StoryboardImageProviderReceiptV1.from_verified_request(
        receipt_payload,
        request=request_capability,
    )

    assert receipt.request == (
        hiob_contracts.require_verified_storyboard_image_provider_request_v1(
            request_capability
        )
    )
    assert receipt.operation_key == receipt.request.operation_key
    assert receipt.artifact_id == receipt.request.expected_artifact_id
    assert receipt.storage_key == receipt.request.expected_storage_key

    with pytest.raises(TypeError, match="VerifiedStoryboardImageProviderRequestV1"):
        hiob_contracts.StoryboardImageProviderReceiptV1.from_verified_request(
            receipt_payload,
            request=receipt.request,
        )

    for field, value in (
        ("artifact_id", "00000000-0000-4000-8000-000000009999"),
        ("storage_key", "synthetic/athena/output.webp"),
        ("operation_key", "authority-digest-as-operation-proof"),
        ("provider", "openai"),
        ("model", "gpt-image-2"),
    ):
        drift = deepcopy(receipt_payload)
        drift[field] = value
        drift["receipt_digest"] = (
            hiob_contracts.derive_storyboard_image_provider_receipt_digest_v1(drift)
        )
        with pytest.raises(ValidationError):
            hiob_contracts.StoryboardImageProviderReceiptV1.model_validate(drift)

    fallback = deepcopy(receipt_payload)
    fallback["fallback_provider"] = "openai"
    with pytest.raises(ValidationError, match="Extra inputs"):
        hiob_contracts.StoryboardImageProviderReceiptV1.model_validate(fallback)

    reversed_time = deepcopy(receipt_payload)
    reversed_time["completed_at_utc"] = "2026-08-14T05:00:00Z"
    reversed_time["receipt_digest"] = (
        hiob_contracts.derive_storyboard_image_provider_receipt_digest_v1(reversed_time)
    )
    with pytest.raises(ValidationError, match="completed_at_utc"):
        hiob_contracts.StoryboardImageProviderReceiptV1.model_validate(reversed_time)


def test_image_set_is_exactly_sixteen_unique_ordered_source_beats() -> None:
    image_set = _image_set()

    assert [image.source_beat_index for image in image_set.images] == list(range(16))
    assert [
        receipt.request.source_beat_index for receipt in image_set.provider_receipts
    ] == list(range(16))
    assert all(
        image.provider_receipt_digest == receipt.receipt_digest
        for image, receipt in zip(
            image_set.images,
            image_set.provider_receipts,
            strict=True,
        )
    )
    assert len({image.artifact_id for image in image_set.images}) == 16
    assert image_set.receipt_digest == derive_storyboard_image_set_receipt_digest_v1(
        image_set
    )


def test_image_set_allows_distinct_executions_with_identical_bytes() -> None:
    images = [_image(i) for i in range(16)]
    images[1] = _image(1, sha256=images[0]["sha256"])

    image_set = _image_set(images=images)

    assert image_set.images[0].sha256 == image_set.images[1].sha256
    assert image_set.images[0].artifact_digest == image_set.images[1].artifact_digest
    assert image_set.images[0].artifact_id != image_set.images[1].artifact_id
    assert image_set.images[0].storage_key != image_set.images[1].storage_key
    assert (
        image_set.images[0].provider_receipt_digest
        != image_set.images[1].provider_receipt_digest
    )
    assert image_set.images[0].generation_nonce != image_set.images[1].generation_nonce


def test_image_set_rejects_receipt_projection_execution_alias_or_early_seal() -> None:
    image_set = _image_set()
    body = image_set.model_dump(mode="json")

    projection_drift = deepcopy(body)
    projection_drift["images"][0]["provider_receipt_digest"] = sha256_digest(
        {"alien": "provider receipt"}
    )
    projection_drift["receipt_digest"] = derive_storyboard_image_set_receipt_digest_v1(
        projection_drift
    )
    with pytest.raises(ValidationError, match="provider receipt|projection"):
        StoryboardImageSetReceiptV1.model_validate(projection_drift)

    task_alias = deepcopy(body)
    task_alias["provider_receipts"][1]["provider_task_id"] = task_alias[
        "provider_receipts"
    ][0]["provider_task_id"]
    task_alias["provider_receipts"][1]["receipt_digest"] = (
        hiob_contracts.derive_storyboard_image_provider_receipt_digest_v1(
            task_alias["provider_receipts"][1]
        )
    )
    task_alias["images"][1]["provider_receipt_digest"] = task_alias[
        "provider_receipts"
    ][1]["receipt_digest"]
    task_alias["receipt_digest"] = derive_storyboard_image_set_receipt_digest_v1(
        task_alias
    )
    with pytest.raises(ValidationError, match="provider_task_id.*unique"):
        StoryboardImageSetReceiptV1.model_validate(task_alias)

    early = deepcopy(body)
    early["completed_at_utc"] = "2026-08-14T05:19:59Z"
    early["receipt_digest"] = derive_storyboard_image_set_receipt_digest_v1(early)
    with pytest.raises(ValidationError, match="completed_at_utc"):
        StoryboardImageSetReceiptV1.model_validate(early)


@pytest.mark.parametrize("mutation", ["missing", "duplicate_beat", "duplicate_asset"])
def test_image_set_rejects_partial_or_aliased_paid_results(mutation: str) -> None:
    images = [_image(i) for i in range(16)]
    if mutation == "missing":
        images.pop()
    elif mutation == "duplicate_beat":
        images[15] = _image(14, artifact_id="storyboard-image-alias")
    else:
        images[15] = _image(
            15,
            artifact_id=images[0]["artifact_id"],
            storage_key=images[0]["storage_key"],
            sha256=images[0]["sha256"],
            generation_nonce=images[0]["generation_nonce"],
        )

    with pytest.raises(ValidationError):
        _image_set(images=images)


def test_phase_a_completion_seals_initial_paid_output_and_public_summary() -> None:
    completion = _phase_a_completion()

    assert completion.input_storyboard_draft is None
    assert completion.paid_source_beat_indices == tuple(range(16))
    assert completion.ares_beat_plan_revision_digest == completion.plan_digest
    assert completion.output_storyboard_draft.revision == 1
    assert completion.output_storyboard_draft.binds_image_set(
        completion.output_image_set_receipt
    )
    assert completion.output_storyboard_carrier.storyboard_digest == (
        completion.output_storyboard_draft.draft_digest
    )
    assert completion.completed_at_utc >= (
        completion.output_image_set_receipt.completed_at_utc
    )

    summary = hiob_contracts.StoryboardPhaseACompletionSummaryV1.from_completion(
        completion
    )
    summary_json = summary.model_dump(mode="json")
    assert summary.binds(completion)
    assert summary.image_count == 16
    assert summary.completion_receipt_digest == completion.receipt_digest
    assert summary.output_storyboard_carrier_digest == (
        hiob_contracts.derive_factory_storyboard_carrier_digest_v1(
            completion.output_storyboard_carrier
        )
    )
    assert "output_image_set_receipt" not in summary_json
    assert "provider_receipts" not in json.dumps(summary_json)
    assert "storage_key" not in json.dumps(summary_json)
    assert "provider_task_id" not in json.dumps(summary_json)

    pointer_drift = completion.model_dump(mode="json")
    pointer_drift["output_storyboard_carrier"]["storyboard_digest"] = sha256_digest(
        {"alien": "pointer"}
    )
    pointer_drift["receipt_digest"] = (
        hiob_contracts.derive_storyboard_phase_a_completion_receipt_digest_v1(
            pointer_drift
        )
    )
    with pytest.raises(ValidationError, match="carrier|output storyboard"):
        hiob_contracts.StoryboardPhaseACompletionReceiptV1.model_validate(pointer_drift)

    early = completion.model_dump(mode="json")
    early["completed_at_utc"] = "2026-08-14T05:29:59Z"
    early["receipt_digest"] = (
        hiob_contracts.derive_storyboard_phase_a_completion_receipt_digest_v1(early)
    )
    with pytest.raises(ValidationError, match="completed_at_utc"):
        hiob_contracts.StoryboardPhaseACompletionReceiptV1.model_validate(early)


def test_phase_a_regen_binds_previous_draft_and_legitimate_successor() -> None:
    initial = _phase_a_completion()
    regenerated = _phase_a_completion(
        purpose="storyboard_regen",
        input_draft=initial.output_storyboard_draft,
        input_image_set=initial.output_image_set_receipt,
    )

    assert regenerated.paid_source_beat_indices == (0,)
    assert regenerated.paid_budget_authority.storyboard_draft_digest == (
        initial.output_storyboard_draft.draft_digest
    )
    assert regenerated.output_storyboard_draft.is_valid_successor_of(
        initial.output_storyboard_draft,
        replacement_image_set=regenerated.output_image_set_receipt,
    )
    assert regenerated.output_storyboard_draft.cards[0].selected_artifact != (
        initial.output_storyboard_draft.cards[0].selected_artifact
    )
    assert regenerated.output_storyboard_draft.cards[1].selected_artifact == (
        initial.output_storyboard_draft.cards[1].selected_artifact
    )

    alien_input = regenerated.model_dump(mode="json")
    alien_input["input_storyboard_draft"] = None
    alien_input["receipt_digest"] = (
        hiob_contracts.derive_storyboard_phase_a_completion_receipt_digest_v1(
            alien_input
        )
    )
    with pytest.raises(ValidationError, match="regen.*input|input.*regen"):
        hiob_contracts.StoryboardPhaseACompletionReceiptV1.model_validate(alien_input)

    unpaid_mutation = regenerated.model_dump(mode="json")
    unpaid_mutation["paid_source_beat_indices"] = [1]
    unpaid_mutation["receipt_digest"] = (
        hiob_contracts.derive_storyboard_phase_a_completion_receipt_digest_v1(
            unpaid_mutation
        )
    )
    with pytest.raises(ValidationError, match="paid source|authority"):
        hiob_contracts.StoryboardPhaseACompletionReceiptV1.model_validate(
            unpaid_mutation
        )


def test_draft_separates_immutable_source_identity_from_editor_sequence() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    reordered_cards = _cards(image_set, list(reversed(range(16))))
    reordered_cards[0] = _card(
        15,
        0,
        image=image_set.images[15],
        prompt_override="closer product framing",
        crop_mode="contain",
        focal_x_basis_points=7_500,
        focal_y_basis_points=3_000,
        motion_note="slow push-in; editorial note only",
    )
    revised = _draft(
        image_set,
        cards=reordered_cards,
        revision=2,
        parent_draft_digest=draft.draft_digest,
    )

    assert [card.sequence_index for card in revised.cards] == list(range(16))
    assert [card.source_beat_index for card in revised.cards] == list(
        reversed(range(16))
    )
    assert revised.is_valid_successor_of(draft)
    assert revised.cards[0].beat_identity_digest == draft.cards[15].beat_identity_digest
    assert revised.cards[0].selected_artifact == draft.cards[15].selected_artifact
    assert revised.cards[0].scene_id == draft.cards[15].scene_id


def test_successor_rejects_immutable_beat_retarget() -> None:
    image_set = _image_set()
    original = _draft(image_set)
    cards = _cards(image_set)
    changed_text = "retargeted beat text"
    changes = {
        "beat_text": changed_text,
        "beat_identity_digest": derive_storyboard_beat_identity_digest_v1(
            PLAN_DIGEST, 0, changed_text
        ),
    }
    cards[0] = _card(0, 0, image=image_set.images[0], **changes)
    candidate = _draft(
        image_set,
        cards=cards,
        revision=2,
        parent_draft_digest=original.draft_digest,
    )

    assert not candidate.is_valid_successor_of(original)


def test_successor_allows_server_verified_selected_artifact_replacement() -> None:
    image_set = _image_set()
    original = _draft(image_set)
    cards = _cards(image_set)
    replacement = _image(
        0,
        artifact_id="storyboard-image-00-replacement",
        storage_key=(
            f"workspaces/{WORKSPACE_ID}/runs/{RUN_ID}/storyboard/00-replacement.webp"
        ),
        sha256=sha256_digest({"replacement": 0}),
        provider_receipt_digest=sha256_digest({"regen_receipt": 0}),
        generation_nonce="00000000-0000-4000-8000-000000000900",
    )
    cards[0] = _card(
        0,
        0,
        image=image_set.images[0],
        selected_artifact={
            "artifact_id": replacement["artifact_id"],
            "artifact_digest": replacement["artifact_digest"],
        },
    )
    candidate = _draft(
        image_set,
        cards=cards,
        revision=2,
        parent_draft_digest=original.draft_digest,
    )

    assert candidate.is_valid_successor_of(original)
    assert candidate.binds_image_set(image_set)
    assert candidate.cards[0].selected_artifact.artifact_id.endswith("replacement")


@pytest.mark.parametrize(
    "mutation",
    ["missing", "duplicate_sequence", "duplicate_source", "identity"],
)
def test_draft_rejects_non_permutation_or_retargeted_card(mutation: str) -> None:
    image_set = _image_set()
    cards = _cards(image_set)
    if mutation == "missing":
        cards.pop()
    elif mutation == "duplicate_sequence":
        cards[15] = _card(15, 14, image=image_set.images[15])
    elif mutation == "duplicate_source":
        cards[15] = _card(14, 15, image=image_set.images[14])
    elif mutation == "identity":
        cards[0] = _card(
            0,
            0,
            image=image_set.images[0],
            beat_identity_digest=sha256_digest({"alien": "beat"}),
        )
    with pytest.raises(ValidationError):
        _draft(image_set, cards=cards)


def test_draft_revision_requires_parent_and_current_image_set_binding() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    assert draft.binds_image_set(image_set)

    with pytest.raises(ValidationError, match="parent_draft_digest"):
        _draft(image_set, revision=2)
    with pytest.raises(ValidationError, match="parent_draft_digest"):
        _draft(
            image_set,
            revision=1,
            parent_draft_digest=sha256_digest({"parent": "unexpected"}),
        )

    alien_set = _image_set(receipt_id="storyboard-image-set-alien")
    assert not draft.binds_image_set(alien_set)


def test_draft_rejects_one_scene_id_split_across_noncontiguous_runs() -> None:
    image_set = _image_set()
    cards = _cards(image_set)
    cards[4] = _card(
        4,
        4,
        image=image_set.images[4],
        scene_id="scene-00",
    )

    with pytest.raises(ValidationError, match="contiguous"):
        _draft(image_set, cards=cards)


def test_beat_identity_uses_hosted_db_purpose_envelope() -> None:
    assert derive_storyboard_beat_identity_digest_v1(
        PLAN_DIGEST,
        3,
        "immutable beat text 3",
    ) == canonical_contract_digest_v1(
        {
            "purpose": "storyboard-beat-identity.v1",
            "plan_digest": PLAN_DIGEST,
            "source_beat_index": 3,
            "beat_text": "immutable beat text 3",
        }
    )


def test_scene_projection_uses_first_card_as_deterministic_anchor() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    scenes = derive_storyboard_scenes_v1(draft.cards)

    assert len(scenes) == 8
    assert all(isinstance(scene, StoryboardSceneV1) for scene in scenes)
    first = scenes[0]
    assert first.scene_id == "scene-00"
    assert first.sequence_index == 0
    assert [scene.sequence_index for scene in scenes] == list(range(8))
    assert first.source_beat_indices == (0, 1)
    assert first.anchor_selected_artifact == draft.cards[0].selected_artifact
    assert first.scene_digest == derive_storyboard_scene_digest_v1(first)

    tampered = first.model_dump(mode="json")
    tampered["source_beat_indices"] = [1, 0]
    with pytest.raises(ValidationError, match="scene_digest"):
        StoryboardSceneV1.model_validate(tampered)


def test_scene_video_request_digest_binds_only_anchor_visual_fields() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    scene = derive_storyboard_scenes_v1(draft.cards)[0]
    anchor = draft.cards[0]
    execution_digest = sha256_digest({"execution_manifest": 1})
    authority_digest = sha256_digest({"final_authority": 1})

    observed = derive_storyboard_scene_video_request_digest_v1(
        scene=scene,
        anchor_card=anchor,
        storyboard_execution_manifest_digest=execution_digest,
        final_production_authority_digest=authority_digest,
    )
    assert observed == canonical_contract_digest_v1(
        {
            "purpose": "storyboard-scene-video-request.v1",
            "storyboard_execution_manifest_digest": execution_digest,
            "final_production_authority_digest": authority_digest,
            "scene_sequence_index": scene.sequence_index,
            "scene_id": scene.scene_id,
            "scene_digest": scene.scene_digest,
            "anchor": {
                "source_beat_index": anchor.source_beat_index,
                "beat_identity_digest": anchor.beat_identity_digest,
                "prompt_override": anchor.prompt_override,
                "crop_mode": anchor.crop_mode,
                "focal_x_basis_points": anchor.focal_x_basis_points,
                "focal_y_basis_points": anchor.focal_y_basis_points,
                "motion_note": anchor.motion_note,
                "selected_artifact": anchor.selected_artifact.model_dump(mode="json"),
            },
        }
    )


def test_approval_binds_exact_current_draft_revision_and_image_set() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)

    assert approval.binds(draft, image_set)
    assert approval.receipt_digest == derive_storyboard_approval_receipt_digest_v1(
        approval
    )

    revised = _draft(
        image_set,
        revision=2,
        parent_draft_digest=draft.draft_digest,
    )
    assert not approval.binds(revised, image_set)


def test_approval_rejects_rehashed_audit_or_scope_substitution() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    with pytest.raises(ValidationError, match="transaction_audit_id"):
        _approval(draft, image_set, transaction_audit_id="other-transaction")

    payload = _approval(draft, image_set).model_dump(mode="json")
    payload["storyboard_draft_digest"] = sha256_digest({"draft": "substitute"})
    with pytest.raises(ValidationError, match="receipt_digest"):
        StoryboardApprovalReceiptV1.model_validate(payload)


@pytest.mark.parametrize(
    ("purpose", "indices"),
    [
        ("storyboard_draft", list(range(16))),
        ("storyboard_regen", [2, 7]),
        ("final_production", []),
    ],
)
def test_paid_approval_receipt_v2_mints_only_a_current_verified_capability(
    purpose: str,
    indices: list[int],
) -> None:
    receipt = _paid_approval_receipt_v2(
        purpose,
        image_source_beat_indices=indices,
    )
    raw = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(receipt)
    )
    resolver = _ApprovalResolverV2()

    assert receipt.structurally_binds(raw)
    assert receipt.authorizes(
        raw,
        at_utc="2026-08-14T06:00:00Z",
        resolver=resolver,
    )
    assert not hasattr(FactoryPaidBudgetAuthorityV2, "from_verified")
    verified = _paid_resolution_v2(receipt).from_verified(
        at_utc="2026-08-14T06:00:00Z",
        resolver=resolver,
    )
    assert isinstance(verified, VerifiedFactoryPaidBudgetAuthorityV2)
    assert verified.authority == raw
    assert verified.cost_profile.profile_digest == raw.cost_profile_digest
    assert resolver.last_identity is not None
    assert resolver.last_identity["purpose"] == purpose
    assert resolver.last_identity["image_source_beat_indices"] == tuple(indices)

    with pytest.raises(TypeError):
        json.dumps(verified)
    with pytest.raises((TypeError, pickle.PicklingError)):
        pickle.dumps(verified)
    with pytest.raises(TypeError):
        copy(verified)
    with pytest.raises(TypeError, match="only be minted"):
        VerifiedFactoryPaidBudgetAuthorityV2(raw, _token=object())


@pytest.mark.parametrize(
    ("receipt_changes", "at_utc", "current"),
    [
        ({"revoked_at_utc": "2026-08-14T05:30:00Z"}, "2026-08-14T06:00:00Z", True),
        ({}, "2026-08-14T07:00:00Z", True),
        ({}, "2026-08-14T06:00:00Z", False),
    ],
)
def test_paid_authority_v2_rejects_revoked_expired_or_stale_receipt(
    receipt_changes: dict[str, Any],
    at_utc: str,
    current: bool,
) -> None:
    receipt = _paid_approval_receipt_v2("storyboard_draft", **receipt_changes)

    with pytest.raises(ValueError, match="current durable approval"):
        _paid_resolution_v2(receipt).from_verified(
            at_utc=at_utc,
            resolver=_ApprovalResolverV2(current),
        )


def test_paid_approval_receipt_v2_is_exact_phase_and_canonical_digest_bound() -> None:
    receipt = _paid_approval_receipt_v2(
        "storyboard_regen",
        image_source_beat_indices=[1, 5, 11],
    )
    assert receipt.policy_version == "factory-paid-budget.v2"
    assert receipt.receipt_digest == (
        derive_factory_paid_budget_approval_receipt_digest_v2(receipt)
    )

    payload = receipt.model_dump(mode="json")
    payload["paid_calls"]["video"] = 1
    payload["approval_subject_digest"] = (
        derive_factory_paid_budget_approval_subject_digest_v2(payload)
    )
    payload["receipt_digest"] = derive_factory_paid_budget_approval_receipt_digest_v2(
        payload
    )
    with pytest.raises(ValidationError, match="paid_calls"):
        FactoryPaidBudgetApprovalReceiptV2.model_validate(payload)

    wrong_policy = receipt.model_dump(mode="json")
    wrong_policy["policy_version"] = "factory-paid-budget.v1"
    wrong_policy["receipt_digest"] = (
        derive_factory_paid_budget_approval_receipt_digest_v2(wrong_policy)
    )
    with pytest.raises(ValidationError):
        FactoryPaidBudgetApprovalReceiptV2.model_validate(wrong_policy)


def test_paid_approval_receipt_v2_binds_final_scene_count_and_video_calls() -> None:
    receipt = _paid_approval_receipt_v2("final_production")
    assert receipt.storyboard_scene_count == 8
    assert receipt.paid_calls.video == 8

    payload = receipt.model_dump(mode="json")
    payload["storyboard_scene_count"] = 7
    payload["approval_subject_digest"] = (
        derive_factory_paid_budget_approval_subject_digest_v2(payload)
    )
    payload["receipt_digest"] = derive_factory_paid_budget_approval_receipt_digest_v2(
        payload
    )
    with pytest.raises(ValidationError, match="paid_calls"):
        FactoryPaidBudgetApprovalReceiptV2.model_validate(payload)


def test_v2_resolution_output_is_exact_and_binds_cost_profile_and_capability() -> None:
    profile = _cost_profile()
    receipt = _paid_approval_receipt_v2(
        "final_production",
        cost_profile_digest=profile["profile_digest"],
        max_total_cost_microunits=_profile_worst_case_cost(
            profile,
            purpose="final_production",
            scene_count=8,
        ),
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(receipt)
    )
    resolution = FactoryPaidBudgetResolutionV2.model_validate(
        {
            "approval_receipt": receipt,
            "cost_profile": profile,
            "paid_budget_authority": authority,
        }
    )

    assert set(resolution.model_dump(mode="json")) == {
        "approval_receipt",
        "cost_profile",
        "paid_budget_authority",
    }
    verified = resolution.from_verified(
        at_utc="2026-08-14T06:00:00Z",
        resolver=_ApprovalResolverV2(),
    )
    assert verified.authority == authority

    bad_profile = deepcopy(profile)
    bad_profile["operations"]["image"]["rate_microunits"] += 1
    with pytest.raises(ValidationError, match="cost_profile"):
        FactoryPaidBudgetResolutionV2.model_validate(
            {
                "approval_receipt": receipt,
                "cost_profile": bad_profile,
                "paid_budget_authority": authority,
            }
        )


def test_v2_resolution_requires_full_typed_current_cost_profile() -> None:
    profile_payload = _cost_profile()
    profile = FactoryCostProfileV1.model_validate(profile_payload)

    assert profile.all_beat_count == 16
    assert profile.purpose_policies is not None
    assert set(profile.operations.model_dump(mode="json")) == {
        "script",
        "image",
        "video",
        "voice",
        "render",
    }
    assert profile.operations.video.provider == "piapi"
    assert profile.operations.video.model == "kling-3.0-omni"
    assert profile.operations.video.billing_unit == "second"

    legacy_payload = deepcopy(profile_payload)
    legacy_payload.pop("all_beat_count")
    legacy_payload.pop("purpose_policies")
    legacy_payload["profile_digest"] = derive_factory_cost_profile_digest_v1(
        legacy_payload
    )
    legacy_profile = FactoryCostProfileV1.model_validate(legacy_payload)
    assert legacy_profile.all_beat_count is None
    assert legacy_profile.purpose_policies is None

    receipt = _paid_approval_receipt_v2(
        "final_production",
        cost_profile_digest=legacy_profile.profile_digest,
        max_total_cost_microunits=_profile_worst_case_cost(
            legacy_payload,
            purpose="final_production",
            scene_count=8,
        ),
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(receipt)
    )
    with pytest.raises(ValidationError, match="purpose policies"):
        FactoryPaidBudgetResolutionV2.model_validate(
            {
                "approval_receipt": receipt,
                "cost_profile": legacy_profile,
                "paid_budget_authority": authority,
            }
        )


def test_v2_resolution_rejects_currency_or_validity_drift() -> None:
    eur_payload = _cost_profile()
    eur_payload["currency"] = "EUR"
    eur_payload["profile_digest"] = derive_factory_cost_profile_digest_v1(eur_payload)
    receipt = _paid_approval_receipt_v2(
        "final_production",
        cost_profile_digest=eur_payload["profile_digest"],
        currency="USD",
        max_total_cost_microunits=_profile_worst_case_cost(
            eur_payload,
            purpose="final_production",
            scene_count=8,
        ),
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(receipt)
    )
    with pytest.raises(ValidationError, match="currency"):
        FactoryPaidBudgetResolutionV2.model_validate(
            {
                "approval_receipt": receipt,
                "cost_profile": eur_payload,
                "paid_budget_authority": authority,
            }
        )

    all_eur_profile = deepcopy(_cost_profile())
    all_eur_profile["currency"] = "EUR"
    all_eur_profile["profile_digest"] = derive_factory_cost_profile_digest_v1(
        all_eur_profile
    )
    all_eur_receipt = _paid_approval_receipt_v2(
        "final_production",
        currency="EUR",
        cost_profile_digest=all_eur_profile["profile_digest"],
        max_total_cost_microunits=_profile_worst_case_cost(
            all_eur_profile,
            purpose="final_production",
            scene_count=8,
        ),
    )
    all_eur_authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(all_eur_receipt)
    )
    with pytest.raises(ValidationError, match="USD"):
        FactoryPaidBudgetResolutionV2.model_validate(
            {
                "approval_receipt": all_eur_receipt,
                "cost_profile": all_eur_profile,
                "paid_budget_authority": all_eur_authority,
            }
        )

    expired_payload = _cost_profile()
    expired_payload["valid_until_utc"] = "2026-08-14T06:30:00Z"
    expired_payload["profile_digest"] = derive_factory_cost_profile_digest_v1(
        expired_payload
    )
    receipt = _paid_approval_receipt_v2(
        "final_production",
        cost_profile_digest=expired_payload["profile_digest"],
        max_total_cost_microunits=_profile_worst_case_cost(
            expired_payload,
            purpose="final_production",
            scene_count=8,
        ),
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(receipt)
    )
    resolution = FactoryPaidBudgetResolutionV2.model_validate(
        {
            "approval_receipt": receipt,
            "cost_profile": expired_payload,
            "paid_budget_authority": authority,
        }
    )
    with pytest.raises(ValueError, match="current cost profile"):
        resolution.from_verified(
            at_utc="2026-08-14T06:45:00Z",
            resolver=_ApprovalResolverV2(),
        )


@pytest.mark.parametrize(
    ("purpose", "indices", "scene_count"),
    [
        ("storyboard_draft", list(range(16)), None),
        ("storyboard_regen", [2, 7, 11], None),
        ("final_production", [], 8),
    ],
)
def test_v2_resolution_recomputes_exact_customer_cost_cap(
    purpose: str,
    indices: list[int],
    scene_count: int | None,
) -> None:
    profile = _cost_profile()
    exact_cost = _profile_worst_case_cost(
        profile,
        purpose=purpose,
        image_count=len(indices),
        scene_count=scene_count or 0,
    )
    receipt = _paid_approval_receipt_v2(
        purpose,
        image_source_beat_indices=indices,
        storyboard_scene_count=scene_count,
        max_total_cost_microunits=exact_cost + 1,
        cost_profile_digest=profile["profile_digest"],
        pricing_policy_revision=profile["pricing_policy_revision"],
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(receipt)
    )

    with pytest.raises(ValidationError, match="cost cap"):
        FactoryPaidBudgetResolutionV2.model_validate(
            {
                "approval_receipt": receipt,
                "cost_profile": profile,
                "paid_budget_authority": authority,
            }
        )


def test_typed_cost_profile_rejects_missing_operation_identity_or_policy_drift() -> (
    None
):
    missing_provider = _cost_profile()
    missing_provider["operations"]["video"].pop("provider")
    missing_provider["profile_digest"] = derive_factory_cost_profile_digest_v1(
        missing_provider
    )
    with pytest.raises(ValidationError):
        FactoryCostProfileV1.model_validate(missing_provider)

    wrong_selector = _cost_profile()
    wrong_selector["purpose_policies"]["final_production"]["video"] = 16
    wrong_selector["profile_digest"] = derive_factory_cost_profile_digest_v1(
        wrong_selector
    )
    with pytest.raises(ValidationError):
        FactoryCostProfileV1.model_validate(wrong_selector)


@pytest.mark.parametrize(
    ("purpose", "indices", "expected_calls"),
    [
        ("storyboard_draft", list(range(16)), (1, 16, 0, 0, 0)),
        ("storyboard_regen", [1], (0, 1, 0, 0, 0)),
        ("storyboard_regen", [1, 4, 9, 15], (0, 4, 0, 0, 0)),
        ("final_production", [], (0, 0, 8, 16, 1)),
    ],
)
def test_authority_v2_allows_only_exact_two_stage_or_regen_lanes(
    purpose: str,
    indices: list[int],
    expected_calls: tuple[int, int, int, int, int],
) -> None:
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority(purpose, image_source_beat_indices=indices)
    )

    calls = authority.paid_calls
    assert (calls.script, calls.image, calls.video, calls.voice, calls.render) == (
        expected_calls
    )
    assert calls.retries == calls.fallbacks == calls.character_lock == 0
    assert authority.storyboard_scene_count == (
        8 if purpose == "final_production" else None
    )
    assert authority.approval_subject_digest == (
        derive_factory_paid_budget_approval_subject_digest_v2(authority)
    )
    assert authority.idempotency_key == derive_factory_paid_budget_idempotency_key_v2(
        authority
    )
    assert authority.authority_digest == derive_factory_paid_budget_authority_digest_v2(
        authority
    )


@pytest.mark.parametrize(
    ("purpose", "indices", "field", "value"),
    [
        ("storyboard_draft", list(range(16)), "image", 15),
        ("storyboard_draft", list(range(16)), "video", 1),
        ("storyboard_regen", [1, 4], "script", 1),
        ("storyboard_regen", [1, 4], "image", 1),
        ("storyboard_regen", [1, 4], "render", 1),
        ("final_production", [], "image", 1),
        ("final_production", [], "video", 16),
        ("final_production", [], "voice", 15),
        ("final_production", [], "render", 0),
        ("final_production", [], "retries", 1),
        ("final_production", [], "fallbacks", 1),
    ],
)
def test_authority_v2_rejects_cross_phase_paid_call_smuggling(
    purpose: str,
    indices: list[int],
    field: str,
    value: int,
) -> None:
    payload = _authority(purpose, image_source_beat_indices=indices)
    payload["paid_calls"][field] = value
    payload["approval_subject_digest"] = (
        derive_factory_paid_budget_approval_subject_digest_v2(payload)
    )
    payload["idempotency_key"] = derive_factory_paid_budget_idempotency_key_v2(payload)
    payload["authority_digest"] = derive_factory_paid_budget_authority_digest_v2(
        payload
    )

    with pytest.raises(ValidationError, match="paid_calls"):
        FactoryPaidBudgetAuthorityV2.model_validate(payload)


@pytest.mark.parametrize(
    ("purpose", "indices", "changes"),
    [
        ("storyboard_draft", list(range(15)), {}),
        ("storyboard_draft", list(range(16)), {"plan_digest": PLAN_DIGEST}),
        ("storyboard_draft", list(range(16)), {"storyboard_draft_digest": PLAN_DIGEST}),
        ("storyboard_regen", [], {}),
        ("storyboard_regen", [1], {"plan_digest": None}),
        ("storyboard_regen", [1, 1], {}),
        ("storyboard_regen", [4, 1], {}),
        ("storyboard_regen", [16], {}),
        ("storyboard_regen", [1], {"storyboard_draft_digest": None}),
        (
            "storyboard_regen",
            [1],
            {"storyboard_approval_receipt_digest": PLAN_DIGEST},
        ),
        ("final_production", [1], {}),
        ("final_production", [], {"plan_digest": None}),
        ("final_production", [], {"storyboard_draft_digest": None}),
        (
            "final_production",
            [],
            {"storyboard_approval_receipt_digest": None},
        ),
    ],
)
def test_authority_v2_rejects_wrong_phase_bindings_or_regen_scope(
    purpose: str,
    indices: list[int],
    changes: dict[str, Any],
) -> None:
    payload = _authority(
        purpose,
        image_source_beat_indices=indices,
        **changes,
    )
    with pytest.raises(ValidationError):
        FactoryPaidBudgetAuthorityV2.model_validate(payload)


@pytest.mark.parametrize(
    ("purpose", "scene_count"),
    [
        ("storyboard_draft", 8),
        ("storyboard_regen", 8),
        ("final_production", None),
        ("final_production", 0),
        ("final_production", 17),
    ],
)
def test_authority_v2_rejects_scene_count_outside_final_production(
    purpose: str,
    scene_count: int | None,
) -> None:
    payload = _authority(
        purpose,
        storyboard_scene_count=scene_count,
    )
    with pytest.raises(ValidationError, match="storyboard_scene_count"):
        FactoryPaidBudgetAuthorityV2.model_validate(payload)


def test_final_authority_video_calls_equal_approved_storyboard_scene_count() -> None:
    payload = _authority(
        "final_production",
        storyboard_scene_count=3,
        paid_calls=_calls("final_production", storyboard_scene_count=3),
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(payload)
    assert authority.storyboard_scene_count == 3
    assert authority.paid_calls.video == 3

    tampered = deepcopy(payload)
    tampered["paid_calls"]["video"] = 4
    tampered["approval_subject_digest"] = (
        derive_factory_paid_budget_approval_subject_digest_v2(tampered)
    )
    tampered["idempotency_key"] = derive_factory_paid_budget_idempotency_key_v2(
        tampered
    )
    tampered["authority_digest"] = derive_factory_paid_budget_authority_digest_v2(
        tampered
    )
    with pytest.raises(ValidationError, match="paid_calls"):
        FactoryPaidBudgetAuthorityV2.model_validate(tampered)


@pytest.mark.parametrize("value", [True, 1.0, "0", -1])
def test_zero_capable_paid_lanes_remain_strict_safe_integers(value: Any) -> None:
    payload = _authority("final_production")
    payload["paid_calls"]["image"] = value
    with pytest.raises(ValidationError):
        FactoryPaidBudgetAuthorityV2.model_validate(payload)


def test_paid_call_helper_rejects_unknown_purpose_instead_of_falling_through() -> None:
    with pytest.raises(ValueError, match="unsupported paid budget purpose"):
        hiob_contracts.factory_paid_call_cardinality_v2("unknown")


def test_execution_manifest_binds_approved_cards_images_and_final_authority() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)
    paid_receipt = _paid_approval_receipt_v2(
        "final_production",
        storyboard_draft_digest=draft.draft_digest,
        storyboard_approval_receipt_digest=approval.receipt_digest,
    )
    final_authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(paid_receipt)
    )
    verified = _verified_paid_authority_v2(paid_receipt)
    manifest = _manifest(
        draft,
        image_set,
        approval,
        final_production_authority_digest=final_authority.authority_digest,
    )

    assert not manifest.binds(approval, draft, image_set, final_authority)
    assert manifest.binds(approval, draft, image_set, verified)


def test_full_storyboard_chain_allows_distinct_image_executions_with_same_bytes() -> (
    None
):
    images = [_image(i) for i in range(16)]
    images[1] = _image(1, sha256=images[0]["sha256"])
    image_set = _image_set(images=images)
    draft = _draft(image_set)
    approval = _approval(draft, image_set)
    manifest = _manifest(draft, image_set, approval)

    assert image_set.images[0].sha256 == image_set.images[1].sha256
    assert image_set.images[0].artifact_digest == image_set.images[1].artifact_digest
    assert image_set.images[0].artifact_id != image_set.images[1].artifact_id
    assert manifest.images[0].sha256 == manifest.images[1].sha256
    assert manifest.images[0].artifact_id != manifest.images[1].artifact_id
    assert manifest.manifest_digest == derive_storyboard_execution_manifest_digest_v1(
        manifest
    )
    assert manifest.cards[0].motion_note is None
    assert len(manifest.scenes) == 8
    assert manifest.scenes[0].source_beat_indices == (0, 1)
    assert manifest.scenes[0].anchor_selected_artifact == (
        manifest.cards[0].selected_artifact
    )


def test_execution_manifest_rejects_selected_artifact_or_card_tamper() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)
    cards = [card.model_dump(mode="json") for card in draft.cards]
    cards[0] = _card(0, 0, image=image_set.images[1])

    with pytest.raises(ValidationError):
        _manifest(draft, image_set, approval, cards=cards)

    scenes = [
        scene.model_dump(mode="json")
        for scene in derive_storyboard_scenes_v1(draft.cards)
    ]
    scenes[0]["anchor_selected_artifact"] = scenes[1]["anchor_selected_artifact"]
    scenes[0]["scene_digest"] = derive_storyboard_scene_digest_v1(scenes[0])
    with pytest.raises(ValidationError, match="derived scenes"):
        _manifest(draft, image_set, approval, scenes=scenes)


def test_execution_manifest_rich_images_follow_card_sequence_not_source_order() -> None:
    image_set = _image_set()
    draft = _draft(
        image_set,
        cards=_cards(image_set, list(reversed(range(16)))),
    )
    approval = _approval(draft, image_set)
    manifest = _manifest(draft, image_set, approval)

    expected_sources = list(reversed(range(16)))
    assert [card.source_beat_index for card in manifest.cards] == expected_sources
    assert [image.source_beat_index for image in manifest.images] == expected_sources

    with pytest.raises(ValidationError, match="sequence order"):
        _manifest(
            draft,
            image_set,
            approval,
            images=[image.model_dump(mode="json") for image in image_set.images],
        )


def test_execution_manifest_rejects_authority_for_a_different_scene_count() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)
    receipt = _paid_approval_receipt_v2(
        "final_production",
        storyboard_draft_digest=draft.draft_digest,
        storyboard_approval_receipt_digest=approval.receipt_digest,
        storyboard_scene_count=3,
        paid_calls=_calls("final_production", storyboard_scene_count=3),
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(receipt)
    )
    verified = _verified_paid_authority_v2(receipt)
    manifest = _manifest(
        draft,
        image_set,
        approval,
        final_production_authority_digest=authority.authority_digest,
    )

    assert len(manifest.scenes) == 8
    assert not manifest.binds(approval, draft, image_set, verified)


def test_scene_video_set_binds_exact_scenes_and_sixteen_beat_projection() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)
    paid_receipt = _paid_approval_receipt_v2(
        "final_production",
        storyboard_draft_digest=draft.draft_digest,
        storyboard_approval_receipt_digest=approval.receipt_digest,
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(paid_receipt)
    )
    verified = _verified_paid_authority_v2(paid_receipt)
    manifest = _manifest(
        draft,
        image_set,
        approval,
        final_production_authority_digest=authority.authority_digest,
    )
    receipt = _scene_video_set(manifest, authority)
    verified_requests = _verified_scene_video_requests(manifest, verified)

    assert len(receipt.scene_video_receipts) == len(manifest.scenes) == 8
    assert len(receipt.beat_projections) == 16
    assert [item.repeat_index for item in receipt.beat_projections[:4]] == [
        0,
        1,
        0,
        1,
    ]
    assert receipt.binds(manifest, verified, verified_requests)
    assert not receipt.binds(manifest, authority, verified_requests)
    assert not receipt.binds(manifest, verified, ())
    assert receipt.scene_video_receipts[0].binds_verified_request(verified_requests[0])
    assert receipt.scene_video_receipts[0].artifact.duration_ms == 4_000
    assert isinstance(
        receipt.scene_video_receipts[0].artifact,
        StoryboardSceneVideoArtifactRefV1,
    )
    assert isinstance(
        receipt.beat_projections[0],
        StoryboardBeatSceneVideoProjectionV1,
    )

    for field, value in (
        ("provider", "priced-provider-alien"),
        ("model", "priced-model-alien"),
        ("generation_nonce", "00000000-0000-4000-8000-000000009999"),
        ("cost_profile_digest", sha256_digest({"profile": "alien"})),
        ("pricing_policy_revision", 99),
    ):
        alien = receipt.model_dump(mode="json")
        request_payload = alien["scene_video_receipts"][0]["request"]
        request_payload[field] = value
        _reseal_scene_video_request(request_payload)
        alien["scene_video_receipts"][0]["receipt_digest"] = (
            derive_storyboard_scene_video_receipt_digest_v1(
                alien["scene_video_receipts"][0]
            )
        )
        alien["receipt_digest"] = derive_storyboard_scene_video_set_receipt_digest_v1(
            alien
        )
        alien_receipt = StoryboardSceneVideoSetReceiptV1.model_validate(alien)
        assert not alien_receipt.binds(manifest, verified, verified_requests)


def test_scene_video_set_and_fan_in_reject_alien_manifest_approval_subject() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)
    paid_receipt = _paid_approval_receipt_v2(
        "final_production",
        storyboard_draft_digest=draft.draft_digest,
        storyboard_approval_receipt_digest=approval.receipt_digest,
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(paid_receipt)
    )
    verified = _verified_paid_authority_v2(paid_receipt)
    alien_manifest = _manifest(
        draft,
        image_set,
        approval,
        storyboard_draft_digest=sha256_digest({"alien": "draft"}),
        storyboard_approval_receipt_digest=sha256_digest({"alien": "approval"}),
        final_production_authority_digest=authority.authority_digest,
    )
    assert not alien_manifest.binds(approval, draft, image_set, verified)

    scene_video_set = _scene_video_set(alien_manifest, authority)
    fan_in = _scene_fan_in(alien_manifest, authority, scene_video_set)

    assert not scene_video_set.binds(alien_manifest, verified, ())
    assert not fan_in.binds(alien_manifest, verified, ())


def test_scene_video_request_requires_verified_exact_manifest_capability() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)
    profile = _cost_profile()
    paid_receipt = _paid_approval_receipt_v2(
        "final_production",
        storyboard_draft_digest=draft.draft_digest,
        storyboard_approval_receipt_digest=approval.receipt_digest,
        cost_profile_digest=profile["profile_digest"],
        pricing_policy_revision=profile["pricing_policy_revision"],
        max_total_cost_microunits=_profile_worst_case_cost(
            profile,
            purpose="final_production",
            scene_count=8,
        ),
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(paid_receipt)
    )
    verified_authority = _verified_paid_authority_v2(
        paid_receipt,
        profile=profile,
    )
    manifest = _manifest(
        draft,
        image_set,
        approval,
        final_production_authority_digest=authority.authority_digest,
    )
    payload = _scene_video_request(manifest, authority)

    with pytest.raises(TypeError, match="VerifiedFactoryPaidBudgetAuthorityV2"):
        StoryboardSceneVideoRequestV1.from_verified(
            payload,
            manifest=manifest,
            authority=authority,
            at_utc="2026-08-14T06:00:00Z",
            resolver=_ApprovalResolverV2(),
        )

    capability = StoryboardSceneVideoRequestV1.from_verified(
        payload,
        manifest=manifest,
        authority=verified_authority,
        at_utc="2026-08-14T06:00:00Z",
        resolver=_ApprovalResolverV2(),
    )
    assert isinstance(capability, VerifiedStoryboardSceneVideoRequestV1)
    request = require_verified_storyboard_scene_video_request_v1(capability)
    assert set(request.model_dump(mode="json")) == {
        "contract_version",
        "workspace_id",
        "run_id",
        "factory_revision",
        "plan_digest",
        "storyboard_execution_manifest_digest",
        "final_production_authority_digest",
        "scene_sequence_index",
        "scene_id",
        "scene_digest",
        "anchor",
        "anchor_image",
        "generation_nonce",
        "duration_ms",
        "fps",
        "width",
        "height",
        "audio_mode",
        "provider",
        "model",
        "cost_profile_digest",
        "pricing_policy_revision",
        "request_digest",
        "execution_request_digest",
        "idempotency_key",
    }
    assert request.request_digest == payload["request_digest"]
    assert request.request_digest == derive_storyboard_scene_video_request_digest_v1(
        scene=manifest.scenes[0],
        anchor_card=manifest.cards[0],
        storyboard_execution_manifest_digest=manifest.manifest_digest,
        final_production_authority_digest=authority.authority_digest,
    )
    assert request.execution_request_digest == (
        derive_storyboard_scene_video_execution_request_digest_v1(request)
    )
    assert request.idempotency_key == payload["idempotency_key"]
    assert request.anchor.source_beat_index == manifest.scenes[0].source_beat_indices[0]
    assert request.fps == 24
    assert (request.width, request.height) == (720, 1_280)
    assert request.audio_mode == "none"
    assert request.cost_profile_digest == profile["profile_digest"]
    assert request.pricing_policy_revision == profile["pricing_policy_revision"]
    assert derive_storyboard_scene_video_provider_prompt_v1(request.anchor) == (
        "@image_1\n"
        "crop_mode: cover\n"
        "focal_x_basis_points: 5000\n"
        "focal_y_basis_points: 5000"
    )

    with pytest.raises(TypeError, match="VerifiedStoryboardSceneVideoRequestV1"):
        require_verified_storyboard_scene_video_request_v1(request)


def test_scene_video_request_rechecks_durable_approval_before_every_scene() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)
    profile = _cost_profile()
    paid_receipt = _paid_approval_receipt_v2(
        "final_production",
        storyboard_draft_digest=draft.draft_digest,
        storyboard_approval_receipt_digest=approval.receipt_digest,
        cost_profile_digest=profile["profile_digest"],
        pricing_policy_revision=profile["pricing_policy_revision"],
        max_total_cost_microunits=_profile_worst_case_cost(
            profile,
            purpose="final_production",
            scene_count=8,
        ),
    )
    resolver = _ApprovalResolverV2()
    verified_authority = _verified_paid_authority_v2(
        paid_receipt,
        profile=profile,
        resolver=resolver,
    )
    manifest = _manifest(
        draft,
        image_set,
        approval,
        final_production_authority_digest=verified_authority.authority.authority_digest,
    )

    assert resolver.call_count == 1
    capabilities = _verified_scene_video_requests(
        manifest,
        verified_authority,
        resolver=resolver,
    )
    assert len(capabilities) == len(manifest.scenes)
    assert resolver.call_count == 1 + len(manifest.scenes)

    resolver.current = False
    with pytest.raises(ValueError, match="current durable approval"):
        StoryboardSceneVideoRequestV1.from_verified(
            _scene_video_request(
                manifest,
                verified_authority.authority,
                cost_profile=verified_authority.cost_profile,
            ),
            manifest=manifest,
            authority=verified_authority,
            at_utc="2026-08-14T06:15:00Z",
            resolver=resolver,
        )
    assert resolver.call_count == 2 + len(manifest.scenes)

    resolver.current = True
    with pytest.raises(ValueError, match="current durable approval"):
        StoryboardSceneVideoRequestV1.from_verified(
            _scene_video_request(
                manifest,
                verified_authority.authority,
                cost_profile=verified_authority.cost_profile,
            ),
            manifest=manifest,
            authority=verified_authority,
            at_utc=paid_receipt.expires_at_utc,
            resolver=resolver,
        )


def test_scene_video_request_seals_transport_identity_and_rich_anchor_image() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)
    profile = _cost_profile()
    paid_receipt = _paid_approval_receipt_v2(
        "final_production",
        storyboard_draft_digest=draft.draft_digest,
        storyboard_approval_receipt_digest=approval.receipt_digest,
        cost_profile_digest=profile["profile_digest"],
        pricing_policy_revision=profile["pricing_policy_revision"],
        max_total_cost_microunits=_profile_worst_case_cost(
            profile,
            purpose="final_production",
            scene_count=8,
        ),
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(paid_receipt)
    )
    verified_authority = _verified_paid_authority_v2(
        paid_receipt,
        profile=profile,
    )
    manifest = _manifest(
        draft,
        image_set,
        approval,
        final_production_authority_digest=authority.authority_digest,
    )
    payload = _scene_video_request(manifest, authority)

    provider_drift = deepcopy(payload)
    provider_drift["model"] = "unpriced-model"
    with pytest.raises(ValidationError, match="execution_request_digest"):
        StoryboardSceneVideoRequestV1.model_validate(provider_drift)

    rehashed_provider_drift = deepcopy(provider_drift)
    _reseal_scene_video_request(rehashed_provider_drift)
    with pytest.raises(ValueError, match="cost profile"):
        StoryboardSceneVideoRequestV1.from_verified(
            rehashed_provider_drift,
            manifest=manifest,
            authority=verified_authority,
            at_utc="2026-08-14T06:00:00Z",
            resolver=_ApprovalResolverV2(),
        )

    alien_image = deepcopy(payload)
    alien_image["anchor_image"]["storage_key"] = (
        "workspaces/alien/runs/alien/storyboard/00.webp"
    )
    _reseal_scene_video_request(alien_image)
    with pytest.raises(ValueError, match="anchor image"):
        StoryboardSceneVideoRequestV1.from_verified(
            alien_image,
            manifest=manifest,
            authority=verified_authority,
            at_utc="2026-08-14T06:00:00Z",
            resolver=_ApprovalResolverV2(),
        )

    wrong_output_profile = deepcopy(payload)
    wrong_output_profile["width"] = 1_080
    wrong_output_profile["height"] = 1_920
    _reseal_scene_video_request(wrong_output_profile)
    with pytest.raises(ValidationError, match="width|height"):
        StoryboardSceneVideoRequestV1.model_validate(wrong_output_profile)

    wrong_fps = deepcopy(payload)
    wrong_fps["fps"] = 30
    _reseal_scene_video_request(wrong_fps)
    with pytest.raises(ValidationError, match="fps"):
        StoryboardSceneVideoRequestV1.model_validate(wrong_fps)

    long_prompt = deepcopy(payload)
    long_prompt["anchor"]["prompt_override"] = "x" * 2_500
    _reseal_scene_video_request(long_prompt)
    with pytest.raises(ValidationError, match="provider prompt.*2500"):
        StoryboardSceneVideoRequestV1.model_validate(long_prompt)

    extra_image_ref = deepcopy(payload)
    extra_image_ref["anchor"]["motion_note"] = "pan from @image_2"
    with pytest.raises(ValueError, match="sole.*@image_1"):
        derive_storyboard_scene_video_provider_prompt_v1(extra_image_ref["anchor"])

    for field, value in (
        ("audio_mode", "source"),
        ("cost_profile_digest", sha256_digest({"profile": "alien"})),
        ("pricing_policy_revision", profile["pricing_policy_revision"] + 1),
    ):
        drift = deepcopy(payload)
        drift[field] = value
        _reseal_scene_video_request(drift)
        with pytest.raises(
            (ValidationError, ValueError), match=field.replace("_", " ") + "|literal"
        ):
            StoryboardSceneVideoRequestV1.from_verified(
                drift,
                manifest=manifest,
                authority=verified_authority,
                at_utc="2026-08-14T06:00:00Z",
                resolver=_ApprovalResolverV2(),
            )

    extra_non_anchor = deepcopy(payload)
    extra_non_anchor["non_anchor_prompts"] = [draft.cards[1].prompt_override]
    with pytest.raises(ValidationError, match="Extra inputs"):
        StoryboardSceneVideoRequestV1.model_validate(extra_non_anchor)


def test_scene_video_set_rejects_repeat_or_video_alias_tampering() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)
    paid_receipt = _paid_approval_receipt_v2(
        "final_production",
        storyboard_draft_digest=draft.draft_digest,
        storyboard_approval_receipt_digest=approval.receipt_digest,
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(paid_receipt)
    )
    manifest = _manifest(
        draft,
        image_set,
        approval,
        final_production_authority_digest=authority.authority_digest,
    )
    receipt = _scene_video_set(manifest, authority)

    repeat_tamper = receipt.model_dump(mode="json")
    repeat_tamper["beat_projections"][1]["repeat_index"] = 0
    repeat_tamper["beat_projections"][1]["projection_digest"] = (
        derive_storyboard_beat_scene_video_projection_digest_v1(
            repeat_tamper["beat_projections"][1]
        )
    )
    repeat_tamper["receipt_digest"] = (
        derive_storyboard_scene_video_set_receipt_digest_v1(repeat_tamper)
    )
    with pytest.raises(ValidationError, match="repeat_index"):
        StoryboardSceneVideoSetReceiptV1.model_validate(repeat_tamper)

    aliased = receipt.model_dump(mode="json")
    aliased["scene_video_receipts"][1]["artifact"] = deepcopy(
        aliased["scene_video_receipts"][0]["artifact"]
    )
    aliased["scene_video_receipts"][1]["receipt_digest"] = (
        derive_storyboard_scene_video_receipt_digest_v1(
            aliased["scene_video_receipts"][1]
        )
    )
    aliased["receipt_digest"] = derive_storyboard_scene_video_set_receipt_digest_v1(
        aliased
    )
    with pytest.raises(ValidationError, match="unique"):
        StoryboardSceneVideoSetReceiptV1.model_validate(aliased)


def test_scene_video_set_allows_distinct_executions_with_identical_bytes() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)
    paid_receipt = _paid_approval_receipt_v2(
        "final_production",
        storyboard_draft_digest=draft.draft_digest,
        storyboard_approval_receipt_digest=approval.receipt_digest,
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(paid_receipt)
    )
    manifest = _manifest(
        draft,
        image_set,
        approval,
        final_production_authority_digest=authority.authority_digest,
    )
    payload = _scene_video_set(manifest, authority).model_dump(mode="json")
    shared_digest = payload["scene_video_receipts"][0]["artifact"]["sha256"]
    second_receipt = payload["scene_video_receipts"][1]
    second_receipt["artifact"]["sha256"] = shared_digest
    second_receipt["artifact"]["artifact_digest"] = shared_digest
    second_receipt["receipt_digest"] = derive_storyboard_scene_video_receipt_digest_v1(
        second_receipt
    )
    for projection in payload["beat_projections"]:
        if projection["scene_sequence_index"] == 1:
            projection["video_artifact_digest"] = shared_digest
            projection["projection_digest"] = (
                derive_storyboard_beat_scene_video_projection_digest_v1(projection)
            )
    payload["receipt_digest"] = derive_storyboard_scene_video_set_receipt_digest_v1(
        payload
    )

    receipt = StoryboardSceneVideoSetReceiptV1.model_validate(payload)

    first = receipt.scene_video_receipts[0]
    second = receipt.scene_video_receipts[1]
    assert first.artifact.sha256 == second.artifact.sha256
    assert first.artifact.artifact_digest == second.artifact.artifact_digest
    assert first.artifact.artifact_id != second.artifact.artifact_id
    assert first.artifact.storage_key != second.artifact.storage_key
    assert first.provider_job_id != second.provider_job_id
    assert first.request.generation_nonce != second.request.generation_nonce


def test_scene_video_receipt_requires_exact_four_second_immutable_video() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)
    paid_receipt = _paid_approval_receipt_v2(
        "final_production",
        storyboard_draft_digest=draft.draft_digest,
        storyboard_approval_receipt_digest=approval.receipt_digest,
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(paid_receipt)
    )
    verified = _verified_paid_authority_v2(paid_receipt)
    manifest = _manifest(
        draft,
        image_set,
        approval,
        final_production_authority_digest=authority.authority_digest,
    )
    request_capability = _verified_scene_video_requests(manifest, verified)[0]
    request = require_verified_storyboard_scene_video_request_v1(request_capability)
    payload = _scene_video_receipt(request.model_dump(mode="json"), 0)
    value = StoryboardSceneVideoReceiptV1.from_verified_request(
        payload,
        request=request_capability,
    )
    with pytest.raises(ValueError, match="verified request"):
        StoryboardSceneVideoReceiptV1.from_verified_request(
            payload,
            request=request,
        )

    assert value.request == request
    assert set(value.model_dump(mode="json")) == {
        "contract_version",
        "request",
        "provider_job_id",
        "status",
        "artifact",
        "receipt_digest",
    }

    payload["artifact"]["duration_ms"] = 3_999
    payload["artifact"]["artifact_digest"] = (
        derive_storyboard_scene_video_artifact_digest_v1(payload["artifact"])
    )
    payload["receipt_digest"] = derive_storyboard_scene_video_receipt_digest_v1(payload)

    with pytest.raises(ValidationError):
        StoryboardSceneVideoReceiptV1.model_validate(payload)

    alien_request = deepcopy(value.model_dump(mode="json"))
    alien_request["request"]["generation_nonce"] = (
        "00000000-0000-4000-8000-000000009999"
    )
    _reseal_scene_video_request(alien_request["request"])
    alien_request["receipt_digest"] = derive_storyboard_scene_video_receipt_digest_v1(
        alien_request
    )
    with pytest.raises(ValueError, match="verified request"):
        StoryboardSceneVideoReceiptV1.from_verified_request(
            alien_request,
            request=request_capability,
        )


def test_scene_fan_in_binds_nested_scene_set_and_sequence_ordered_audio() -> None:
    image_set = _image_set()
    draft = _draft(
        image_set,
        cards=_cards(image_set, list(reversed(range(16)))),
    )
    approval = _approval(draft, image_set)
    paid_receipt = _paid_approval_receipt_v2(
        "final_production",
        storyboard_draft_digest=draft.draft_digest,
        storyboard_approval_receipt_digest=approval.receipt_digest,
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(paid_receipt)
    )
    verified = _verified_paid_authority_v2(paid_receipt)
    manifest = _manifest(
        draft,
        image_set,
        approval,
        final_production_authority_digest=authority.authority_digest,
    )
    scene_video_set = _scene_video_set(manifest, authority)
    verified_requests = _verified_scene_video_requests(manifest, verified)
    fan_in = _scene_fan_in(manifest, authority, scene_video_set)

    expected_source_order = list(reversed(range(16)))
    assert [item.beat_index for item in fan_in.audio_artifacts] == (
        expected_source_order
    )
    assert [
        item.source_beat_index
        for item in fan_in.storyboard_scene_video_set_receipt.beat_projections
    ] == expected_source_order
    assert all(
        isinstance(item, StrictAllBeatArtifactRefV1) for item in fan_in.audio_artifacts
    )
    assert fan_in.binds(manifest, verified, verified_requests)


def test_scene_fan_in_rejects_audio_order_or_mix_digest_drift() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)
    paid_receipt = _paid_approval_receipt_v2(
        "final_production",
        storyboard_draft_digest=draft.draft_digest,
        storyboard_approval_receipt_digest=approval.receipt_digest,
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(paid_receipt)
    )
    manifest = _manifest(
        draft,
        image_set,
        approval,
        final_production_authority_digest=authority.authority_digest,
    )
    scene_video_set = _scene_video_set(manifest, authority)
    fan_in = _scene_fan_in(manifest, authority, scene_video_set)
    payload = fan_in.model_dump(mode="json")
    payload["audio_artifacts"][0], payload["audio_artifacts"][1] = (
        payload["audio_artifacts"][1],
        payload["audio_artifacts"][0],
    )
    payload["audio_mix_digest"] = canonical_contract_digest_v1(
        {"audio_artifacts": payload["audio_artifacts"]}
    )
    payload["manifest_digest"] = derive_storyboard_scene_fan_in_manifest_digest_v1(
        payload
    )

    with pytest.raises(ValidationError, match="projection source order"):
        StoryboardSceneFanInManifestV1.model_validate(payload)


def test_scene_fan_in_allows_deduplicated_audio_bytes_but_not_identity_aliases() -> (
    None
):
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)
    paid_receipt = _paid_approval_receipt_v2(
        "final_production",
        storyboard_draft_digest=draft.draft_digest,
        storyboard_approval_receipt_digest=approval.receipt_digest,
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(paid_receipt)
    )
    manifest = _manifest(
        draft,
        image_set,
        approval,
        final_production_authority_digest=authority.authority_digest,
    )
    fan_in = _scene_fan_in(
        manifest,
        authority,
        _scene_video_set(manifest, authority),
    )

    duplicate_bytes = fan_in.model_dump(mode="json")
    duplicate_bytes["audio_artifacts"][1]["sha256"] = duplicate_bytes[
        "audio_artifacts"
    ][0]["sha256"]
    duplicate_bytes["audio_mix_digest"] = canonical_contract_digest_v1(
        {"audio_artifacts": duplicate_bytes["audio_artifacts"]}
    )
    duplicate_bytes["manifest_digest"] = (
        derive_storyboard_scene_fan_in_manifest_digest_v1(duplicate_bytes)
    )
    accepted = StoryboardSceneFanInManifestV1.model_validate(duplicate_bytes)
    assert accepted.audio_artifacts[0].sha256 == accepted.audio_artifacts[1].sha256

    for field in ("artifact_id", "uri", "execution_id"):
        aliased = fan_in.model_dump(mode="json")
        aliased["audio_artifacts"][1][field] = aliased["audio_artifacts"][0][field]
        aliased["audio_mix_digest"] = canonical_contract_digest_v1(
            {"audio_artifacts": aliased["audio_artifacts"]}
        )
        aliased["manifest_digest"] = derive_storyboard_scene_fan_in_manifest_digest_v1(
            aliased
        )
        with pytest.raises(ValidationError, match=field):
            StoryboardSceneFanInManifestV1.model_validate(aliased)


def test_reels_factory_receipt_v3_replaces_beat_artifact_set_linkage() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)
    paid_receipt = _paid_approval_receipt_v2(
        "final_production",
        storyboard_draft_digest=draft.draft_digest,
        storyboard_approval_receipt_digest=approval.receipt_digest,
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(paid_receipt)
    )
    verified = _verified_paid_authority_v2(paid_receipt)
    manifest = _manifest(
        draft,
        image_set,
        approval,
        final_production_authority_digest=authority.authority_digest,
    )
    scene_video_set = _scene_video_set(manifest, authority)
    verified_requests = _verified_scene_video_requests(manifest, verified)
    fan_in = _scene_fan_in(manifest, authority, scene_video_set)
    receipt = ReelsFactoryReceiptV3.model_validate(
        _factory_receipt_v3(manifest, authority, scene_video_set, fan_in)
    )

    assert "beat_artifact_set_receipt_digest" not in receipt.model_fields_set
    assert receipt.storyboard_scene_video_set_receipt_digest == (
        scene_video_set.receipt_digest
    )
    assert receipt.binds_scene_video_set(scene_video_set)
    assert receipt.binds_chain(
        fan_in,
        scene_video_set,
        manifest=manifest,
        authority=verified,
        verified_requests=verified_requests,
    )


def test_star_reels_view_v3_ready_requires_scene_video_set_receipt_chain() -> None:
    phase_a_completion = _phase_a_completion()
    image_set = phase_a_completion.output_image_set_receipt
    draft = phase_a_completion.output_storyboard_draft
    approval = _approval(draft, image_set)
    paid_receipt = _paid_approval_receipt_v2(
        "final_production",
        storyboard_draft_digest=draft.draft_digest,
        storyboard_approval_receipt_digest=approval.receipt_digest,
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(paid_receipt)
    )
    manifest = _manifest(
        draft,
        image_set,
        approval,
        final_production_authority_digest=authority.authority_digest,
    )
    scene_video_set = _scene_video_set(manifest, authority)
    fan_in = _scene_fan_in(manifest, authority, scene_video_set)
    factory = _factory_receipt_v3(
        manifest,
        authority,
        scene_video_set,
        fan_in,
    )
    carrier = FactoryStoryboardCarrierV1.model_validate(
        {
            "contract_version": "FactoryStoryboardCarrier.v1",
            "storyboard_revision": draft.revision,
            "storyboard_digest": draft.draft_digest,
            "image_set_receipt_digest": image_set.receipt_digest,
            "approval_receipt_digest": approval.receipt_digest,
            "execution_manifest_digest": manifest.manifest_digest,
        }
    )
    payload: dict[str, Any] = {
        "contract_version": "StarReelsView.v3",
        "section": "RunStatus",
        "status": "ready",
        "revision": 12,
        "stage_output": None,
        "budget": {
            "purpose": "final_production",
            "purpose_label": "최종 영상 제작",
            **_calls("final_production", storyboard_scene_count=8),
            "all_beat_count": 16,
            "storyboard_scene_count": 8,
            "paid_budget_authority_digest": authority.authority_digest,
            "storyboard_scene_video_set_receipt": scene_video_set,
        },
        "review_digest": None,
        "receipts": {
            "factory": factory,
            "script_approval": None,
            "plan_approval": None,
            "paid_budget_approval_receipt": paid_receipt,
            "paid_budget_authority": authority,
            "storyboard_phase_a_completion_summary": (
                hiob_contracts.StoryboardPhaseACompletionSummaryV1.from_completion(
                    phase_a_completion
                )
            ),
        },
        "provider_call": "confirmed",
        "error": None,
        "storyboard": carrier,
    }
    view = StarReelsViewV3.model_validate(payload)
    assert isinstance(view.receipts.factory, ReelsFactoryReceiptV3)
    assert view.budget.storyboard_scene_video_set_receipt == scene_video_set

    missing_set = deepcopy(payload)
    missing_set["budget"]["storyboard_scene_video_set_receipt"] = None
    with pytest.raises(ValidationError, match="scene video budget"):
        StarReelsViewV3.model_validate(missing_set)


def test_registry_and_root_exports_are_additive_and_v1_remains_unchanged() -> None:
    assert hiob_contracts.FactoryPaidBudgetAuthorityV1 is FactoryPaidBudgetAuthorityV1
    assert hiob_contracts.FactoryPaidBudgetAuthorityV2 is FactoryPaidBudgetAuthorityV2
    assert (
        hiob_contracts.FactoryPaidBudgetApprovalResolverV2
        is FactoryPaidBudgetApprovalResolverV2
    )
    assert hiob_contracts.StoryboardDraftV1 is StoryboardDraftV1
    assert {
        "FactoryPaidBudgetAuthority",
        "FactoryPaidBudgetAuthorityV2",
        "FactoryPaidBudgetApprovalReceiptV2",
        "FactoryPaidBudgetResolutionV2",
        "FactoryCostProfile",
        "ReelsFactoryProgressReceiptV3",
        "ReelsFactoryFailureReceiptV3",
        "AthenaFramePlanReceipt",
        "StoryboardImageArtifactRef",
        "StoryboardImageProviderRequest",
        "StoryboardImageProviderReceipt",
        "StoryboardImageSetReceipt",
        "StoryboardPhaseACompletionReceipt",
        "StoryboardPhaseACompletionSummary",
        "StoryboardScene",
        "StoryboardSceneVideoReceipt",
        "StoryboardSceneVideoRequest",
        "StoryboardSceneVideoSetReceipt",
        "StoryboardSceneFanInManifest",
        "StoryboardDraft",
        "StoryboardApprovalReceipt",
        "StoryboardExecutionManifest",
        "ReelsFactoryReceiptV3",
    }.issubset(registered_contracts())

    authority_result = validate_payload(
        "FactoryPaidBudgetAuthorityV2", _authority("storyboard_draft")
    )
    assert authority_result.ok is True
    assert isinstance(authority_result.obj, FactoryPaidBudgetAuthorityV2)

    image_set = _image_set()
    draft = _draft(image_set)
    draft_result = validate_payload("StoryboardDraft", draft.model_dump(mode="json"))
    assert draft_result.ok is True
    assert isinstance(draft_result.obj, StoryboardDraftV1)


def test_digest_derivations_use_exact_top_level_exclusion_only() -> None:
    image = _image(0)
    assert image["artifact_digest"] == image["sha256"]
    assert derive_storyboard_image_artifact_digest_v1(image) == image["sha256"]

    authority = _authority("storyboard_regen", image_source_beat_indices=[2, 7])
    assert authority["authority_digest"] == canonical_contract_digest_v1(
        authority, exclude={"authority_digest"}
    )

    changed = deepcopy(authority)
    changed["purpose"] = "final_production"
    assert (
        derive_factory_paid_budget_authority_digest_v2(changed)
        != authority["authority_digest"]
    )


def test_phase_a_image_execution_identity_preimages_are_stable_and_acyclic() -> None:
    nonce = hiob_contracts.derive_storyboard_image_generation_nonce_v1(
        authority_idempotency_key=DRAFT_AUTHORITY_IDEMPOTENCY_KEY,
        purpose="storyboard_draft",
        source_beat_index=3,
    )
    assert nonce == str(
        uuid5(
            NAMESPACE_URL,
            (
                "hiob:storyboard-image-generation.v1:"
                f"{DRAFT_AUTHORITY_IDEMPOTENCY_KEY}:storyboard_draft:image:3"
            ),
        )
    )
    request = _image_provider_request(3, generation_nonce=nonce)
    assert request["operation_key"] == (
        f"reels:{WORKSPACE_ID}:{RUN_ID}:{PLAN_DIGEST}:{nonce}:image:3"
    )
    assert request["expected_artifact_id"] == str(
        uuid5(
            NAMESPACE_URL,
            (
                "hiob:storyboard-image-artifact.v1:"
                f"{request['operation_key']}:{request['request_digest']}"
            ),
        )
    )
    assert request["expected_storage_key"] == (
        f"workspaces/{WORKSPACE_ID}/runs/{RUN_ID}/storyboard/images/03/"
        f"{request['expected_artifact_id']}"
    )

    expected_drift = deepcopy(request)
    expected_drift["expected_storage_key"] += "-alien"
    assert (
        hiob_contracts.derive_storyboard_image_provider_request_digest_v1(
            expected_drift
        )
        == request["request_digest"]
    )
    assert (
        hiob_contracts.derive_storyboard_image_provider_execution_request_digest_v1(
            expected_drift
        )
        != request["execution_request_digest"]
    )


def _historical_paid_operation_evidence(
    *,
    resolution: FactoryPaidBudgetResolutionV2,
    receipt: StoryboardImageProviderReceiptV1 | StoryboardSceneVideoReceiptV1,
) -> dict[str, Any]:
    if isinstance(receipt, StoryboardImageProviderReceiptV1):
        operation = "image"
        source_index = receipt.request.source_beat_index
        operation_key = receipt.request.operation_key
        provider_operation_id = receipt.provider_task_id
    else:
        operation = "video"
        source_index = receipt.request.scene_sequence_index
        operation_key = hiob_contracts.derive_storyboard_scene_video_operation_key_v1(
            receipt.request
        )
        provider_operation_id = receipt.provider_job_id
    output_digest = hiob_contracts.derive_factory_paid_operation_claim_output_digest_v2(
        receipt
    )
    body: dict[str, Any] = {
        "contract_version": "FactoryPaidOperationHistoricalEvidence.v2",
        "evidence_id": f"historical-{operation}-{source_index:02d}",
        "workspace_id": receipt.request.workspace_id,
        "run_id": receipt.request.run_id,
        "factory_revision": receipt.request.factory_revision,
        "purpose": resolution.paid_budget_authority.purpose,
        "operation": operation,
        "source_index": source_index,
        "resolution": resolution,
        "paid_budget_authority_digest": (
            resolution.paid_budget_authority.authority_digest
        ),
        "cost_profile_digest": resolution.cost_profile.profile_digest,
        "pricing_policy_revision": resolution.cost_profile.pricing_policy_revision,
        "provider": receipt.request.provider,
        "model": receipt.request.model,
        "operation_key": operation_key,
        "execution_request_digest": receipt.request.execution_request_digest,
        "provider_operation_id": provider_operation_id,
        "provider_binding_receipt_digest": sha256_digest(
            {"provider_binding": operation_key}
        ),
        "provider_result_receipt_id": f"leaf-result-{operation}-{source_index:02d}",
        "provider_result_receipt_digest": sha256_digest(
            {"leaf_result_receipt": operation_key}
        ),
        "provider_result_output_digest": output_digest,
        "provider_result_recorded_at_utc": "2026-08-14T06:20:00Z",
        "completed_claim_output_digest": output_digest,
        "claim_status": "completed",
        "reserved_at_utc": "2026-08-14T06:00:00Z",
        "completed_at_utc": "2026-08-14T06:21:00Z",
    }
    body["evidence_digest"] = (
        hiob_contracts.derive_factory_paid_operation_historical_evidence_digest_v2(body)
    )
    return body


def _verified_historical_evidence(
    *,
    resolution: FactoryPaidBudgetResolutionV2,
    receipt: StoryboardImageProviderReceiptV1 | StoryboardSceneVideoReceiptV1,
    resolver: _PaidOperationEvidenceResolverV2 | None = None,
) -> Any:
    return hiob_contracts.FactoryPaidOperationHistoricalEvidenceV2.from_verified(
        _historical_paid_operation_evidence(
            resolution=resolution,
            receipt=receipt,
        ),
        resolver=resolver or _PaidOperationEvidenceResolverV2(),
    )


def test_initial_image_set_rejects_one_current_and_fifteen_alien_authorities() -> None:
    current_receipt = _paid_approval_receipt_v2("storyboard_draft")
    alien_receipt = _paid_approval_receipt_v2(
        "storyboard_draft",
        approver_account_id="alien-account",
    )
    current = _image_set_for_paid_receipt(current_receipt)
    alien = _image_set_for_paid_receipt(alien_receipt)
    payload = current.model_dump(mode="json")
    payload["images"][1:] = [
        image.model_dump(mode="json") for image in alien.images[1:]
    ]
    payload["provider_receipts"][1:] = [
        receipt.model_dump(mode="json") for receipt in alien.provider_receipts[1:]
    ]
    payload["receipt_digest"] = derive_storyboard_image_set_receipt_digest_v1(payload)

    with pytest.raises(ValidationError, match="all 16|current authority"):
        StoryboardImageSetReceiptV1.model_validate(payload)


def test_historical_image_evidence_is_reconciliation_only_and_binds_completion() -> (
    None
):
    completion = _phase_a_completion()
    resolution = _paid_resolution_v2(completion.paid_budget_approval_receipt)
    resolver = _PaidOperationEvidenceResolverV2()
    proofs = tuple(
        _verified_historical_evidence(
            resolution=resolution,
            receipt=receipt,
            resolver=resolver,
        )
        for receipt in completion.output_image_set_receipt.provider_receipts
    )

    assert resolver.call_count == 16
    with pytest.raises(TypeError, match="VerifiedStoryboardImageProviderRequestV1"):
        hiob_contracts.require_verified_storyboard_image_provider_request_v1(proofs[0])
    reconciled = (
        hiob_contracts.StoryboardImageProviderReceiptV1.from_historical_evidence(
            completion.output_image_set_receipt.provider_receipts[0],
            request=completion.output_image_set_receipt.provider_receipts[0].request,
            evidence=proofs[0],
        )
    )
    assert reconciled == completion.output_image_set_receipt.provider_receipts[0]
    assert completion.binds_paid_operations(resolution, proofs)
    summary = hiob_contracts.StoryboardPhaseACompletionSummaryV1.from_completion(
        completion,
        authority=resolution,
        operation_proofs=proofs,
    )
    assert summary.binds(completion, authority=resolution, operation_proofs=proofs)

    rejected = _PaidOperationEvidenceResolverV2(verified=False)
    with pytest.raises(ValueError, match="historical|completed operation"):
        hiob_contracts.FactoryPaidOperationHistoricalEvidenceV2.from_verified(
            _historical_paid_operation_evidence(
                resolution=resolution,
                receipt=completion.output_image_set_receipt.provider_receipts[0],
            ),
            resolver=rejected,
        )


def test_historical_scene_evidence_binds_terminal_chain_without_provider_authority() -> (
    None
):
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)
    paid_receipt = _paid_approval_receipt_v2(
        "final_production",
        storyboard_draft_digest=draft.draft_digest,
        storyboard_approval_receipt_digest=approval.receipt_digest,
    )
    resolution = _paid_resolution_v2(paid_receipt)
    authority = resolution.paid_budget_authority
    manifest = _manifest(
        draft,
        image_set,
        approval,
        final_production_authority_digest=authority.authority_digest,
    )
    scene_set = _scene_video_set(manifest, authority)
    proofs = tuple(
        _verified_historical_evidence(
            resolution=resolution,
            receipt=receipt,
        )
        for receipt in scene_set.scene_video_receipts
    )
    fan_in = _scene_fan_in(manifest, authority, scene_set)
    factory = ReelsFactoryReceiptV3.model_validate(
        _factory_receipt_v3(manifest, authority, scene_set, fan_in)
    )

    with pytest.raises(TypeError, match="VerifiedStoryboardSceneVideoRequestV1"):
        require_verified_storyboard_scene_video_request_v1(proofs[0])
    assert (
        StoryboardSceneVideoReceiptV1.from_reconciled_claim(
            scene_set.scene_video_receipts[0],
            request=scene_set.scene_video_receipts[0].request,
            reconciliation=proofs[0],
        )
        == scene_set.scene_video_receipts[0]
    )
    assert scene_set.binds(manifest, resolution, proofs)
    assert fan_in.binds(manifest, resolution, proofs)
    assert factory.binds_chain(
        fan_in,
        scene_set,
        manifest=manifest,
        authority=resolution,
        verified_requests=proofs,
    )


def test_v3_ready_summaries_redact_server_only_provider_and_storage_proofs() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)
    paid_receipt = _paid_approval_receipt_v2(
        "final_production",
        storyboard_draft_digest=draft.draft_digest,
        storyboard_approval_receipt_digest=approval.receipt_digest,
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(paid_receipt)
    )
    verified = _verified_paid_authority_v2(paid_receipt)
    manifest = _manifest(
        draft,
        image_set,
        approval,
        final_production_authority_digest=authority.authority_digest,
    )
    scene_set = _scene_video_set(manifest, authority)
    requests = _verified_scene_video_requests(manifest, verified)
    fan_in = _scene_fan_in(manifest, authority, scene_set)
    factory = ReelsFactoryReceiptV3.model_validate(
        _factory_receipt_v3(manifest, authority, scene_set, fan_in)
    )
    scene_summary = hiob_contracts.StoryboardSceneVideoSetSummaryV1.from_receipt(
        scene_set,
        manifest=manifest,
        authority=verified,
        operation_proofs=requests,
    )
    factory_summary = hiob_contracts.ReelsFactoryCompletionSummaryV3.from_receipt(
        factory,
        scene_video_set_summary=scene_summary,
        manifest=manifest,
        authority=verified,
        operation_proofs=requests,
    )

    public_json = json.dumps(
        {
            "scene_set": scene_summary.model_dump(mode="json"),
            "factory": factory_summary.model_dump(mode="json"),
        }
    )
    for forbidden in (
        "provider_job_id",
        "storage_key",
        "anchor_image",
        "prompt_override",
        "audio_artifacts",
        "provider_result",
    ):
        assert forbidden not in public_json
    assert factory_summary.output_url == factory.output_url
    assert factory_summary.output_sha256 == factory.output_sha256
    assert len(scene_summary.beat_projections) == 16


def test_canonical_digest_vector_is_stable_across_db_and_runtime_ports() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)
    paid_receipt = _paid_approval_receipt_v2(
        "final_production",
        storyboard_draft_digest=draft.draft_digest,
        storyboard_approval_receipt_digest=approval.receipt_digest,
        cost_profile_digest=COST_PROFILE_DIGEST,
        max_total_cost_microunits=20_000_000,
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(paid_receipt)
    )
    manifest = _manifest(
        draft,
        image_set,
        approval,
        final_production_authority_digest=authority.authority_digest,
    )

    assert (
        image_set.receipt_digest
        == "sha256:7ea540078dca90d90a33ef05c521c4dc3e1912775493a6bd6a60c80bff0940a6"
    )
    assert (
        draft.draft_digest
        == "sha256:75467b94a2cb8ec8a163f875c3bfd4df3cbac1c3e9607f2f56cf1ac7ae28fba8"
    )
    assert (
        approval.receipt_digest
        == "sha256:6742980902ac7679df57e7054761ab386d6a53c0968a64be937d20ad858f0e4d"
    )
    assert (
        paid_receipt.approval_subject_digest
        == "sha256:bc272e590ad0e06bf571ef15981d9719b96c57c568248a6c141ee1baeb4bfa2b"
    )
    assert (
        paid_receipt.receipt_digest
        == "sha256:bd5bf0484ec54d3eaca6f80d270345d26b72315f9f6ebe972ecd4a9c8a5032cf"
    )
    assert (
        authority.idempotency_key
        == "sha256:b9cf4c7cd70dab409203bda63db47e5cb518dd3b0e2659abe3ed1412ae191a38"
    )
    assert (
        authority.authority_digest
        == "sha256:568e8623cae6ba693ecfbf7fc4e1059b4eba1a78f0c5cff9f442692ed2975ade"
    )
    assert (
        manifest.manifest_digest
        == "sha256:c825f1bcfb0b114322c1026e67a4697cb54abe60adf4e9bcc42f2f3b4627b6b3"
    )
    assert (
        manifest.scenes[0].scene_digest
        == "sha256:e03ac098953cddea4e179f40874a788c5d5a58c0b8d5b24c35f13ebe82f6acb7"
    )


def test_all_new_wire_models_forbid_unknown_preview_or_provider_fields() -> None:
    image = _image(0)
    image["preview_url"] = "https://signed.example/image.webp?token=secret"
    with pytest.raises(ValidationError, match="extra"):
        StoryboardImageArtifactRefV1.model_validate(image)

    selected = {
        "artifact_id": "image-1",
        "artifact_digest": sha256_digest({"image": 1}),
        "storage_key": "must-not-cross-browser-boundary.webp",
    }
    with pytest.raises(ValidationError, match="extra"):
        StoryboardSelectedArtifactV1.model_validate(selected)
