from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    FactoryStoryboardCarrierV1,
    StarReelsBudgetV3,
    StarReelsViewV2,
    StarReelsViewV3,
    derive_reels_factory_progress_receipt_digest_v1,
)


DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
DIGEST_D = "sha256:" + "d" * 64


def _budget(purpose: str) -> dict[str, object]:
    calls = {
        "storyboard_draft": {
            "script": 1,
            "image": 16,
            "video": 0,
            "voice": 0,
            "render": 0,
        },
        "storyboard_regen": {
            "script": 0,
            "image": 1,
            "video": 0,
            "voice": 0,
            "render": 0,
        },
        "final_production": {
            "script": 0,
            "image": 0,
            "video": 8,
            "voice": 16,
            "render": 1,
        },
    }[purpose]
    labels = {
        "storyboard_draft": "스토리보드 이미지 16장",
        "storyboard_regen": "선택 이미지 재생성",
        "final_production": "최종 영상 제작",
    }
    return {
        "purpose": purpose,
        "purpose_label": labels[purpose],
        **calls,
        "retries": 0,
        "fallbacks": 0,
        "character_lock": 0,
        "all_beat_count": 16,
        "storyboard_scene_count": (8 if purpose == "final_production" else None),
        "paid_budget_authority_digest": None,
        "storyboard_scene_video_set_receipt": None,
    }


def _carrier(*, approved: bool, executable: bool = False) -> dict[str, object]:
    return {
        "contract_version": "FactoryStoryboardCarrier.v1",
        "storyboard_revision": 2,
        "storyboard_digest": DIGEST_B,
        "image_set_receipt_digest": DIGEST_C,
        "approval_receipt_digest": DIGEST_D if approved else None,
        "execution_manifest_digest": DIGEST_A if executable else None,
    }


def _receipts() -> dict[str, None]:
    return {
        "factory": None,
        "script_approval": None,
        "plan_approval": None,
    }


def _final_progress_receipt() -> dict[str, object]:
    body: dict[str, object] = {
        "contract_version": "ReelsFactoryProgressReceipt.v2",
        "run_id": "00000000-0000-4000-8000-000000000002",
        "idempotency_key": "star.reels.factory:final",
        "revision": 9,
        "stage": "video",
        "provider_attempts": {
            "script": 0,
            "image": 0,
            "video": 1,
            "voice": 0,
            "render": 0,
        },
    }
    return {
        **body,
        "receipt_digest": derive_reels_factory_progress_receipt_digest_v1(body),
    }


def _storyboard_review_view(*, purpose: str = "storyboard_draft") -> dict:
    carrier = _carrier(approved=False)
    return {
        "contract_version": "StarReelsView.v3",
        "section": "StoryboardReview",
        "status": "awaiting_storyboard_review",
        "revision": 7,
        "stage_output": carrier,
        "budget": _budget(purpose),
        "review_digest": DIGEST_B,
        "receipts": _receipts(),
        "provider_call": "confirmed",
        "error": None,
        "storyboard": carrier,
    }


def test_v3_storyboard_review_is_exact_and_digest_bound() -> None:
    value = StarReelsViewV3.model_validate(_storyboard_review_view())

    assert isinstance(value.storyboard, FactoryStoryboardCarrierV1)
    assert value.stage_output == value.storyboard
    assert value.review_digest == value.storyboard.storyboard_digest
    assert value.budget.purpose == "storyboard_draft"

    extra = _storyboard_review_view()
    extra["preview_url"] = "https://signed.example/credential"
    with pytest.raises(ValidationError, match="Extra inputs"):
        StarReelsViewV3.model_validate(extra)


@pytest.mark.parametrize(
    ("purpose", "image_count"),
    [
        ("storyboard_draft", 16),
        ("storyboard_regen", 1),
        ("final_production", 0),
    ],
)
def test_v3_budget_has_exact_purpose_discriminator_and_lane_mask(
    purpose: str,
    image_count: int,
) -> None:
    value = StarReelsBudgetV3.model_validate(_budget(purpose))

    assert value.purpose == purpose
    assert value.image == image_count
    assert value.storyboard_scene_count == (
        8 if purpose == "final_production" else None
    )

    tampered = _budget(purpose)
    tampered["voice"] = 1
    with pytest.raises(ValidationError, match="paid call mask"):
        StarReelsBudgetV3.model_validate(tampered)


def test_v3_budget_rejects_wrong_label_and_unknown_purpose() -> None:
    wrong_label = _budget("storyboard_draft")
    wrong_label["purpose_label"] = "최종 영상 제작"
    with pytest.raises(ValidationError, match="purpose_label"):
        StarReelsBudgetV3.model_validate(wrong_label)

    unknown = _budget("storyboard_draft")
    unknown["purpose"] = "storyboard"
    with pytest.raises(ValidationError):
        StarReelsBudgetV3.model_validate(unknown)


def test_v3_final_budget_video_lane_equals_storyboard_scene_count() -> None:
    payload = _budget("final_production")
    payload["storyboard_scene_count"] = 3
    payload["video"] = 3
    value = StarReelsBudgetV3.model_validate(payload)
    assert value.video == value.storyboard_scene_count == 3

    payload["video"] = 4
    with pytest.raises(ValidationError, match="paid call mask"):
        StarReelsBudgetV3.model_validate(payload)


def test_v3_production_gate_requires_approved_non_executable_pointer() -> None:
    carrier = _carrier(approved=True)
    view = {
        "contract_version": "StarReelsView.v3",
        "section": "ProductionBudgetApproval",
        "status": "awaiting_production_budget_approval",
        "revision": 8,
        "stage_output": carrier,
        "budget": _budget("final_production"),
        "review_digest": DIGEST_D,
        "receipts": _receipts(),
        "provider_call": "none",
        "error": None,
        "storyboard": carrier,
    }
    value = StarReelsViewV3.model_validate(view)
    assert value.storyboard is not None
    assert value.storyboard.approval_receipt_digest == DIGEST_D
    assert value.budget.paid_budget_authority_digest is None

    premature_authority = deepcopy(view)
    premature_authority["budget"]["paid_budget_authority_digest"] = DIGEST_A
    with pytest.raises(ValidationError, match="unapproved final budget"):
        StarReelsViewV3.model_validate(premature_authority)

    executable = deepcopy(view)
    executable_carrier = _carrier(approved=True, executable=True)
    executable["storyboard"] = executable_carrier
    executable["stage_output"] = executable_carrier
    with pytest.raises(ValidationError, match="execution manifest"):
        StarReelsViewV3.model_validate(executable)


def test_v3_carrier_rejects_execution_without_storyboard_approval() -> None:
    payload = _carrier(approved=False, executable=True)
    with pytest.raises(ValidationError, match="requires approval"):
        FactoryStoryboardCarrierV1.model_validate(payload)


def test_v3_run_status_requires_approved_manifest_and_final_authority() -> None:
    carrier = _carrier(approved=True, executable=True)
    budget = _budget("final_production")
    budget["paid_budget_authority_digest"] = DIGEST_A
    payload = {
        "contract_version": "StarReelsView.v3",
        "section": "RunStatus",
        "status": "rendering",
        "revision": 9,
        "stage_output": None,
        "budget": budget,
        "review_digest": None,
        "receipts": {
            **_receipts(),
            "factory": _final_progress_receipt(),
        },
        "provider_call": "confirmed",
        "error": None,
        "storyboard": carrier,
    }
    value = StarReelsViewV3.model_validate(payload)
    assert value.budget.video == value.budget.storyboard_scene_count == 8

    payload["budget"]["paid_budget_authority_digest"] = None
    with pytest.raises(ValidationError, match="requires final paid authority"):
        StarReelsViewV3.model_validate(payload)


def test_v3_rejects_section_status_and_budget_purpose_drift() -> None:
    wrong_status = _storyboard_review_view()
    wrong_status["status"] = "awaiting_production_budget_approval"
    with pytest.raises(ValidationError, match="section does not match"):
        StarReelsViewV3.model_validate(wrong_status)

    wrong_purpose = _storyboard_review_view()
    wrong_purpose["budget"] = _budget("final_production")
    with pytest.raises(ValidationError, match="budget purpose"):
        StarReelsViewV3.model_validate(wrong_purpose)

    premature_phase_b_authority = _storyboard_review_view()
    premature_phase_b_authority["budget"]["paid_budget_authority_digest"] = DIGEST_A
    with pytest.raises(ValidationError, match="cannot carry authority"):
        StarReelsViewV3.model_validate(premature_phase_b_authority)


def test_v2_remains_strict_and_has_no_storyboard_or_purpose_fields() -> None:
    legacy = {
        "contract_version": "StarReelsView.v2",
        "section": "LockGate",
        "status": "missing",
        "revision": 0,
        "stage_output": None,
        "budget": {
            "script": 1,
            "image": 2,
            "video": 2,
            "voice": 2,
            "render": 1,
            "retries": 0,
            "fallbacks": 0,
            "character_lock": 0,
            "all_beat_count": 2,
            "paid_budget_authority_digest": DIGEST_A,
            "beat_artifact_set_receipt": None,
        },
        "review_digest": None,
        "receipts": _receipts(),
        "provider_call": "none",
        "error": "PRODUCT_LOCK_MISSING",
    }
    value = StarReelsViewV2.model_validate(legacy)
    assert "purpose" not in value.budget.model_fields_set

    with pytest.raises(ValidationError, match="Extra inputs"):
        StarReelsViewV2.model_validate({**legacy, "storyboard": None})
