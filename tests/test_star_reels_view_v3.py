from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

import hiob_contracts
from hiob_contracts import (
    FactoryPaidBudgetApprovalReceiptV2,
    FactoryPaidBudgetAuthorityV2,
    FactoryStoryboardCarrierV1,
    ReelsFactoryFailureReceiptV3,
    ReelsFactoryProgressReceiptV3,
    StarReelsBudgetV3,
    StarReelsViewV2,
    StarReelsViewV3,
    derive_factory_paid_budget_approval_receipt_digest_v2,
    derive_factory_paid_budget_approval_subject_digest_v2,
    derive_factory_paid_budget_authority_digest_v2,
    derive_factory_paid_budget_idempotency_key_v2,
    derive_reels_factory_failure_receipt_digest_v3,
    derive_reels_factory_progress_receipt_digest_v3,
)


DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
DIGEST_D = "sha256:" + "d" * 64
WORKSPACE_ID = "00000000-0000-4000-8000-000000000001"
RUN_ID = "00000000-0000-4000-8000-000000000002"


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
        "storyboard_scene_video_set_summary": None,
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


def _paid_pair(
    purpose: str,
) -> tuple[FactoryPaidBudgetApprovalReceiptV2, FactoryPaidBudgetAuthorityV2]:
    image_source_beat_indices = (
        list(range(16))
        if purpose == "storyboard_draft"
        else [0]
        if purpose == "storyboard_regen"
        else []
    )
    paid_calls = {
        key: value
        for key, value in _budget(purpose).items()
        if key
        in {
            "script",
            "image",
            "video",
            "voice",
            "render",
            "retries",
            "fallbacks",
            "character_lock",
        }
    }
    scope: dict[str, object] = {
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "all_beat_count": 16,
        "purpose": purpose,
        "plan_digest": None if purpose == "storyboard_draft" else DIGEST_C,
        "storyboard_draft_digest": (
            None if purpose == "storyboard_draft" else DIGEST_B
        ),
        "storyboard_approval_receipt_digest": (
            DIGEST_D if purpose == "final_production" else None
        ),
        "storyboard_scene_count": (8 if purpose == "final_production" else None),
        "image_source_beat_indices": image_source_beat_indices,
        "paid_calls": paid_calls,
        "max_total_cost_microunits": 20_000_000,
        "currency": "USD",
        "cost_profile_digest": DIGEST_A,
        "pricing_policy_revision": 4,
    }
    approval_subject_digest = derive_factory_paid_budget_approval_subject_digest_v2(
        scope
    )
    receipt_body: dict[str, object] = {
        "contract_version": "FactoryPaidBudgetApprovalReceipt.v2",
        "receipt_id": f"paid-{purpose}",
        **scope,
        "approval_subject_digest": approval_subject_digest,
        "approver_account_id": "account-owner",
        "decision": "approved",
        "policy_version": "factory-paid-budget.v2",
        "state_revision": 2,
        "approved_at_utc": "2026-08-14T05:00:00Z",
        "expires_at_utc": "2026-08-14T07:00:00Z",
        "revoked_at_utc": None,
        "transaction_audit_id": f"paid-{purpose}",
    }
    receipt_body["receipt_digest"] = (
        derive_factory_paid_budget_approval_receipt_digest_v2(receipt_body)
    )
    receipt = FactoryPaidBudgetApprovalReceiptV2.model_validate(receipt_body)
    authority_body: dict[str, object] = {
        "contract_version": "FactoryPaidBudgetAuthority.v2",
        **scope,
        "approval_receipt_id": receipt.receipt_id,
        "approval_receipt_digest": receipt.receipt_digest,
        "approval_subject_digest": approval_subject_digest,
    }
    authority_body["idempotency_key"] = derive_factory_paid_budget_idempotency_key_v2(
        authority_body
    )
    authority_body["authority_digest"] = derive_factory_paid_budget_authority_digest_v2(
        authority_body
    )
    return receipt, FactoryPaidBudgetAuthorityV2.model_validate(authority_body)


def _completion_summary(
    *,
    purpose: str = "storyboard_draft",
    authority_digest: str | None = None,
    carrier: dict[str, object] | None = None,
) -> dict[str, object]:
    output = carrier if carrier is not None else _carrier(approved=False)
    phase_a_authority = _paid_pair(purpose)[1]
    phase_a_authority_digest = (
        authority_digest
        if authority_digest is not None
        else phase_a_authority.authority_digest
    )
    body: dict[str, object] = {
        "contract_version": "StoryboardPhaseACompletionSummary.v1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "purpose": purpose,
        "plan_digest": DIGEST_C,
        "paid_budget_authority_digest": phase_a_authority_digest,
        "max_total_cost_microunits": phase_a_authority.max_total_cost_microunits,
        "currency": "USD",
        "output_storyboard_revision": output["storyboard_revision"],
        "output_storyboard_digest": output["storyboard_digest"],
        "output_image_set_receipt_digest": output["image_set_receipt_digest"],
        "output_storyboard_carrier_digest": (
            hiob_contracts.derive_factory_storyboard_carrier_digest_v1(output)
        ),
        "image_count": 16,
        "completed_at_utc": "2026-08-14T05:40:00Z",
        "completion_receipt_digest": DIGEST_A,
    }
    body["summary_digest"] = (
        hiob_contracts.derive_storyboard_phase_a_completion_summary_digest_v1(body)
    )
    return body


def _receipts(
    pair: tuple[FactoryPaidBudgetApprovalReceiptV2, FactoryPaidBudgetAuthorityV2]
    | None = None,
    *,
    factory: dict[str, object] | None = None,
    completion_summary: dict[str, object] | None = None,
) -> dict[str, object | None]:
    return {
        "factory": factory,
        "script_approval": None,
        "plan_approval": None,
        "paid_budget_approval_receipt": pair[0] if pair is not None else None,
        "paid_budget_authority": pair[1] if pair is not None else None,
        "storyboard_phase_a_completion_summary": completion_summary,
    }


def _progress_receipt_v3(
    authority: FactoryPaidBudgetAuthorityV2,
    *,
    revision: int,
    stage: str,
    provider_attempts: dict[str, int],
    storyboard_execution_manifest_digest: str | None,
) -> dict[str, object]:
    body: dict[str, object] = {
        "contract_version": "ReelsFactoryProgressReceipt.v3",
        "workspace_id": authority.workspace_id,
        "run_id": authority.run_id,
        "factory_revision": authority.factory_revision,
        "idempotency_key": authority.idempotency_key,
        "revision": revision,
        "purpose": authority.purpose,
        "stage": stage,
        "all_beat_count": 16,
        "storyboard_scene_count": authority.storyboard_scene_count,
        "paid_budget_authority_digest": authority.authority_digest,
        "storyboard_execution_manifest_digest": (storyboard_execution_manifest_digest),
        "provider_attempts": provider_attempts,
        "provider_replays": {
            "script": 0,
            "image": 0,
            "video": 0,
            "voice": 0,
            "render": 0,
        },
        "fallbacks": 0,
    }
    return {
        **body,
        "receipt_digest": derive_reels_factory_progress_receipt_digest_v3(body),
    }


def _failure_receipt_v3(
    authority: FactoryPaidBudgetAuthorityV2,
    *,
    revision: int,
    stage: str,
    provider_attempts: dict[str, int],
    storyboard_execution_manifest_digest: str | None,
    provider_call: str = "confirmed",
) -> dict[str, object]:
    body = _progress_receipt_v3(
        authority,
        revision=revision,
        stage=stage,
        provider_attempts=provider_attempts,
        storyboard_execution_manifest_digest=storyboard_execution_manifest_digest,
    )
    body.pop("receipt_digest")
    body["contract_version"] = "ReelsFactoryFailureReceipt.v3"
    body["code"] = "PROVIDER_TERMINAL"
    body["provider_call"] = provider_call
    return {
        **body,
        "receipt_digest": derive_reels_factory_failure_receipt_digest_v3(body),
    }


def _storyboard_review_view(*, purpose: str = "storyboard_draft") -> dict:
    carrier = _carrier(approved=False)
    pair = _paid_pair(purpose)
    budget = _budget(purpose)
    budget["paid_budget_authority_digest"] = pair[1].authority_digest
    attempts = (
        {"script": 1, "image": 16, "video": 0, "voice": 0, "render": 0}
        if purpose == "storyboard_draft"
        else {"script": 0, "image": 1, "video": 0, "voice": 0, "render": 0}
    )
    factory = _progress_receipt_v3(
        pair[1],
        revision=7,
        stage="image",
        provider_attempts=attempts,
        storyboard_execution_manifest_digest=None,
    )
    return {
        "contract_version": "StarReelsView.v3",
        "section": "StoryboardReview",
        "status": "awaiting_storyboard_review",
        "revision": 7,
        "stage_output": carrier,
        "budget": budget,
        "review_digest": DIGEST_B,
        "receipts": _receipts(
            pair,
            factory=factory,
            completion_summary=_completion_summary(
                purpose=purpose,
                authority_digest=pair[1].authority_digest,
                carrier=carrier,
            ),
        ),
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
    assert value.receipts.paid_budget_authority is not None
    assert value.receipts.paid_budget_approval_receipt is not None
    assert value.receipts.storyboard_phase_a_completion_summary is not None
    assert isinstance(value.receipts.factory, ReelsFactoryProgressReceiptV3)

    extra = _storyboard_review_view()
    extra["preview_url"] = "https://signed.example/credential"
    with pytest.raises(ValidationError, match="Extra inputs"):
        StarReelsViewV3.model_validate(extra)

    missing_completion = _storyboard_review_view()
    missing_completion["receipts"]["storyboard_phase_a_completion_summary"] = None
    with pytest.raises(ValidationError, match="Phase.?A completion"):
        StarReelsViewV3.model_validate(missing_completion)


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
        "receipts": _receipts(
            completion_summary=_completion_summary(carrier=_carrier(approved=False))
        ),
        "provider_call": "none",
        "error": None,
        "storyboard": carrier,
    }
    value = StarReelsViewV3.model_validate(view)
    assert value.storyboard is not None
    assert value.storyboard.approval_receipt_digest == DIGEST_D
    assert value.budget.paid_budget_authority_digest is None
    assert value.receipts.storyboard_phase_a_completion_summary is not None
    assert (
        value.receipts.storyboard_phase_a_completion_summary.paid_budget_authority_digest
        != value.budget.paid_budget_authority_digest
    )

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
    pair = _paid_pair("final_production")
    budget = _budget("final_production")
    budget["paid_budget_authority_digest"] = pair[1].authority_digest
    progress = _progress_receipt_v3(
        pair[1],
        revision=9,
        stage="video",
        provider_attempts={
            "script": 0,
            "image": 0,
            "video": 1,
            "voice": 0,
            "render": 0,
        },
        storyboard_execution_manifest_digest=DIGEST_A,
    )
    payload = {
        "contract_version": "StarReelsView.v3",
        "section": "RunStatus",
        "status": "rendering",
        "revision": 9,
        "stage_output": None,
        "budget": budget,
        "review_digest": None,
        "receipts": {
            **_receipts(
                pair,
                factory=progress,
                completion_summary=_completion_summary(
                    carrier=_carrier(approved=False)
                ),
            ),
        },
        "provider_call": "confirmed",
        "error": None,
        "storyboard": carrier,
    }
    value = StarReelsViewV3.model_validate(payload)
    assert value.budget.video == value.budget.storyboard_scene_count == 8
    assert value.receipts.storyboard_phase_a_completion_summary is not None
    assert (
        value.receipts.storyboard_phase_a_completion_summary.paid_budget_authority_digest
        != value.receipts.paid_budget_authority.authority_digest
    )

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

    authority_drift = _storyboard_review_view()
    authority_drift["budget"]["paid_budget_authority_digest"] = DIGEST_C
    with pytest.raises(ValidationError, match="authority"):
        StarReelsViewV3.model_validate(authority_drift)


def test_v3_storyboard_draft_generating_forbids_every_storyboard_projection() -> None:
    payload = _storyboard_review_view()
    payload["status"] = "storyboard_generating"
    payload["review_digest"] = None
    payload["storyboard"] = None
    payload["stage_output"] = None
    payload["receipts"]["storyboard_phase_a_completion_summary"] = None

    value = StarReelsViewV3.model_validate(payload)
    assert value.storyboard is value.stage_output is value.review_digest is None

    for carrier in (
        _carrier(approved=False),
        _carrier(approved=True),
        _carrier(approved=True, executable=True),
    ):
        projected = deepcopy(payload)
        projected["storyboard"] = carrier
        projected["stage_output"] = carrier
        with pytest.raises(ValidationError, match="draft.*cannot carry|projection"):
            StarReelsViewV3.model_validate(projected)


def test_v3_storyboard_regen_generating_requires_authority_bound_pointer() -> None:
    payload = _storyboard_review_view(purpose="storyboard_regen")
    payload["status"] = "storyboard_generating"
    payload["review_digest"] = None
    payload["receipts"]["storyboard_phase_a_completion_summary"] = None

    value = StarReelsViewV3.model_validate(payload)
    assert value.storyboard == value.stage_output
    assert value.storyboard is not None

    missing = deepcopy(payload)
    missing["storyboard"] = None
    missing["stage_output"] = None
    with pytest.raises(ValidationError, match="regen.*(pointer|current storyboard)"):
        StarReelsViewV3.model_validate(missing)

    alien = deepcopy(payload)
    alien["storyboard"]["storyboard_digest"] = DIGEST_C
    alien["stage_output"] = alien["storyboard"]
    with pytest.raises(ValidationError, match="regen authority"):
        StarReelsViewV3.model_validate(alien)


def test_v3_progress_and_failure_attempts_cannot_exceed_paid_authority_mask() -> None:
    pair = _paid_pair("final_production")
    exact_attempts = {
        "script": 0,
        "image": 0,
        "video": 8,
        "voice": 0,
        "render": 1,
    }
    progress = ReelsFactoryProgressReceiptV3.model_validate(
        _progress_receipt_v3(
            pair[1],
            revision=9,
            stage="render",
            provider_attempts=exact_attempts,
            storyboard_execution_manifest_digest=DIGEST_A,
        )
    )
    assert progress.provider_attempts.video == 8

    overflow = _progress_receipt_v3(
        pair[1],
        revision=9,
        stage="video",
        provider_attempts={**exact_attempts, "video": 999},
        storyboard_execution_manifest_digest=DIGEST_A,
    )
    with pytest.raises(ValidationError, match="attempt"):
        ReelsFactoryProgressReceiptV3.model_validate(overflow)

    failure_overflow = _failure_receipt_v3(
        pair[1],
        revision=9,
        stage="voice",
        provider_attempts={**exact_attempts, "voice": 17},
        storyboard_execution_manifest_digest=DIGEST_A,
    )
    with pytest.raises(ValidationError, match="attempt"):
        ReelsFactoryFailureReceiptV3.model_validate(failure_overflow)


def test_v3_failed_view_requires_authority_bound_v3_failure_receipt() -> None:
    carrier = _carrier(approved=True, executable=True)
    pair = _paid_pair("final_production")
    budget = _budget("final_production")
    budget["paid_budget_authority_digest"] = pair[1].authority_digest
    failure = _failure_receipt_v3(
        pair[1],
        revision=10,
        stage="video",
        provider_attempts={
            "script": 0,
            "image": 0,
            "video": 1,
            "voice": 0,
            "render": 0,
        },
        storyboard_execution_manifest_digest=DIGEST_A,
    )
    payload = {
        "contract_version": "StarReelsView.v3",
        "section": "RunStatus",
        "status": "failed",
        "revision": 10,
        "stage_output": None,
        "budget": budget,
        "review_digest": None,
        "receipts": _receipts(
            pair,
            factory=failure,
            completion_summary=_completion_summary(carrier=_carrier(approved=False)),
        ),
        "provider_call": "confirmed",
        "error": "PROVIDER_TERMINAL",
        "storyboard": carrier,
    }

    value = StarReelsViewV3.model_validate(payload)
    assert isinstance(value.receipts.factory, ReelsFactoryFailureReceiptV3)

    purpose_drift = deepcopy(payload)
    purpose_drift["receipts"]["factory"]["purpose"] = "storyboard_draft"
    purpose_drift["receipts"]["factory"]["storyboard_scene_count"] = None
    purpose_drift["receipts"]["factory"]["storyboard_execution_manifest_digest"] = None
    purpose_drift["receipts"]["factory"]["provider_attempts"] = {
        "script": 1,
        "image": 0,
        "video": 0,
        "voice": 0,
        "render": 0,
    }
    purpose_drift["receipts"]["factory"]["receipt_digest"] = (
        derive_reels_factory_failure_receipt_digest_v3(
            purpose_drift["receipts"]["factory"]
        )
    )
    with pytest.raises(ValidationError, match="purpose|authority"):
        StarReelsViewV3.model_validate(purpose_drift)


def test_v3_view_rejects_missing_or_cross_purpose_paid_pair_and_receipt() -> None:
    payload = _storyboard_review_view()
    payload["receipts"]["paid_budget_approval_receipt"] = None
    with pytest.raises(ValidationError, match="paid budget pair"):
        StarReelsViewV3.model_validate(payload)

    cross_purpose = _storyboard_review_view()
    final_pair = _paid_pair("final_production")
    cross_purpose["receipts"]["paid_budget_approval_receipt"] = final_pair[0]
    cross_purpose["receipts"]["paid_budget_authority"] = final_pair[1]
    with pytest.raises(ValidationError, match="purpose|authority"):
        StarReelsViewV3.model_validate(cross_purpose)

    receipt_drift = _storyboard_review_view()
    receipt_drift["receipts"]["factory"]["paid_budget_authority_digest"] = DIGEST_D
    receipt_drift["receipts"]["factory"]["receipt_digest"] = (
        derive_reels_factory_progress_receipt_digest_v3(
            receipt_drift["receipts"]["factory"]
        )
    )
    with pytest.raises(ValidationError, match="factory.*authority|authority.*factory"):
        StarReelsViewV3.model_validate(receipt_drift)


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
        "receipts": {
            "factory": None,
            "script_approval": None,
            "plan_approval": None,
        },
        "provider_call": "none",
        "error": "PRODUCT_LOCK_MISSING",
    }
    value = StarReelsViewV2.model_validate(legacy)
    assert "purpose" not in value.budget.model_fields_set

    with pytest.raises(ValidationError, match="Extra inputs"):
        StarReelsViewV2.model_validate({**legacy, "storyboard": None})
