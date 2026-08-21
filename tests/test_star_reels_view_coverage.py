"""Fail-closed coverage for Star Reels view state projections."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    FactoryStoryboardCarrierV1,
    ProductElementLockDraftV1,
    ReelsFactoryCompletionSummaryV3,
    StarReelsBudgetV3,
    StarReelsViewV1,
    StarReelsViewV2,
    StarReelsViewV3,
    StoryboardPhaseACompletionSummaryV1,
    canonical_contract_digest_v1,
    derive_star_product_lock_review_digest_v1,
)
from hiob_contracts.star_reels_view_v1 import (
    _ReelsFactoryReadyReceiptV1,
    _StarReelsBudgetV2,
)
from tests.test_all_beat_video_contracts import (
    AUTHORITY_DIGEST,
    _artifact_set,
    _factory_receipt,
)
from tests.test_star_reels_view_v1 import (
    DIGEST,
    _budget as _v1_budget,
    _product_draft,
    _progress,
    _ready,
)
from tests.test_star_reels_view_v3 import (
    DIGEST_A,
    DIGEST_B,
    DIGEST_C,
    DIGEST_D,
    _budget,
    _carrier,
    _completion_summary,
    _paid_pair,
    _progress_receipt_v3,
    _receipts,
    _storyboard_review_view,
)
from tests.test_storyboard_two_stage_v1 import _phase_a_completion


def _v1_payload(
    *,
    section: str = "RunStatus",
    status: str = "pending",
    stage_output: object = None,
    review_digest: str | None = None,
    factory: object = None,
    provider_call: str = "none",
    error: str | None = None,
) -> dict[str, object]:
    return {
        "contract_version": "StarReelsView.v1",
        "section": section,
        "status": status,
        "revision": 1,
        "stage_output": stage_output,
        "budget": _v1_budget(),
        "review_digest": review_digest,
        "receipts": {
            "factory": factory,
            "script_approval": None,
            "plan_approval": None,
        },
        "provider_call": provider_call,
        "error": error,
    }


def test_v1_ready_receipt_rejects_transport_scope_attempt_and_digest_drift() -> None:
    non_https = _ready()
    non_https["render_receipt"]["output_url"] = "http://cdn.example/reel.mp4"
    with pytest.raises(ValidationError, match="durable HTTPS"):
        _ReelsFactoryReadyReceiptV1.model_validate(non_https)

    bad_render_digest = _ready()
    bad_render_digest["render_receipt"]["receipt_digest"] = DIGEST
    with pytest.raises(ValidationError, match="render receipt digest"):
        _ReelsFactoryReadyReceiptV1.model_validate(bad_render_digest)

    bad_attempts = _ready()
    bad_attempts["provider_attempts"]["image"] = 0
    with pytest.raises(ValidationError, match="exactly one attempt"):
        _ReelsFactoryReadyReceiptV1.model_validate(bad_attempts)

    bad_scope = _ready()
    bad_scope["render_receipt"]["run_id"] = (
        "00000000-0000-4000-8000-000000000099"
    )
    render_body = dict(bad_scope["render_receipt"])
    render_body.pop("receipt_digest")
    bad_scope["render_receipt"]["receipt_digest"] = (
        canonical_contract_digest_v1(render_body)
    )
    ready_body = dict(bad_scope)
    ready_body.pop("receipt_digest")
    bad_scope["receipt_digest"] = canonical_contract_digest_v1(ready_body)
    with pytest.raises(ValidationError, match="scope mismatch"):
        _ReelsFactoryReadyReceiptV1.model_validate(bad_scope)

    bad_ready_digest = _ready()
    bad_ready_digest["receipt_digest"] = DIGEST
    with pytest.raises(ValidationError, match="ready receipt digest"):
        _ReelsFactoryReadyReceiptV1.model_validate(bad_ready_digest)


def test_v1_view_rejects_every_invalid_review_and_run_shape() -> None:
    cases = (
        (
            _v1_payload(
                section="ScriptReview",
                status="pending",
                stage_output={"revision": 1},
                review_digest=DIGEST,
                provider_call="confirmed",
            ),
            "section does not match",
        ),
        (
            _v1_payload(
                factory=_progress(),
                provider_call="confirmed",
                stage_output={"unexpected": True},
            ),
            "non-review state",
        ),
        (
            _v1_payload(
                section="ScriptReview",
                status="awaiting_script_approval",
                stage_output={"revision": 1},
                review_digest=DIGEST,
                provider_call="none",
            ),
            "confirmed script call",
        ),
        (
            _v1_payload(
                section="LockGate",
                status="awaiting_product_approval",
                stage_output={"untyped": True},
                review_digest=DIGEST,
            ),
            "typed product draft",
        ),
        (
            _v1_payload(
                section="LockGate",
                status="missing",
                factory=_progress(),
                provider_call="confirmed",
                error="MISSING",
            ),
            "cannot carry provider work",
        ),
        (
            _v1_payload(section="LockGate", status="missing"),
            "error does not match",
        ),
        (
            _v1_payload(status="ready", provider_call="none"),
            "ready state requires",
        ),
        (
            _v1_payload(
                section="ScriptReview",
                status="awaiting_script_approval",
                stage_output={"revision": 1},
                review_digest=DIGEST,
                factory=_progress(),
                provider_call="confirmed",
            ),
            "review state cannot carry factory",
        ),
    )
    for payload, message in cases:
        with pytest.raises(ValidationError, match=message):
            StarReelsViewV1.model_validate(payload)


def test_v2_budget_and_ready_view_bind_all_paid_lanes() -> None:
    invalid_budget = {
        "script": 1,
        "image": 2,
        "video": 1,
        "voice": 2,
        "render": 1,
        "retries": 0,
        "fallbacks": 0,
        "character_lock": 0,
        "all_beat_count": 2,
        "paid_budget_authority_digest": DIGEST,
        "beat_artifact_set_receipt": None,
    }
    with pytest.raises(ValidationError, match="all-beat paid lanes"):
        _StarReelsBudgetV2.model_validate(invalid_budget)

    view = StarReelsViewV2.model_validate(
        {
            "contract_version": "StarReelsView.v2",
            "section": "RunStatus",
            "status": "ready",
            "revision": 1,
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
                "paid_budget_authority_digest": AUTHORITY_DIGEST,
                "beat_artifact_set_receipt": _artifact_set(),
            },
            "review_digest": None,
            "receipts": {
                "factory": _factory_receipt(),
                "script_approval": None,
                "plan_approval": None,
            },
            "provider_call": "confirmed",
            "error": None,
        }
    )
    unsealed = view.model_copy(
        update={
            "budget": view.budget.model_copy(
                update={"beat_artifact_set_receipt": None}
            )
        }
    )
    with pytest.raises(ValueError, match="sealed all-beat budget"):
        unsealed._bind_budget_to_ready_authority()


def test_phase_a_completion_rejects_lineage_evidence_and_terminal_drift() -> None:
    initial = _phase_a_completion()
    invalid_initial = initial.model_copy(
        update={
            "output_storyboard_draft": initial.output_storyboard_draft.model_copy(
                update={"revision": 2}
            )
        }
    )
    with pytest.raises(ValueError, match="initial output"):
        invalid_initial._assert_purpose_lineage()

    cross_scope = initial.model_copy(
        update={
            "output_image_set_receipt": initial.output_image_set_receipt.model_copy(
                update={"workspace_id": "00000000-0000-4000-8000-000000000099"}
            )
        }
    )
    with pytest.raises(ValueError, match="does not bind output draft"):
        cross_scope._assert_output_evidence()

    first_receipt = initial.output_image_set_receipt.provider_receipts[0]
    drifted_request = first_receipt.request.model_copy(
        update={"ares_script_revision_digest": DIGEST_A}
    )
    drifted_receipt = first_receipt.model_copy(update={"request": drifted_request})
    drifted_image_set = initial.output_image_set_receipt.model_copy(
        update={
            "provider_receipts": (
                drifted_receipt,
                *initial.output_image_set_receipt.provider_receipts[1:],
            )
        }
    )
    request_drift = initial.model_copy(
        update={"output_image_set_receipt": drifted_image_set}
    )
    with pytest.raises(ValueError, match="revision evidence drifted"):
        request_drift._assert_output_evidence()

    first_card = initial.output_storyboard_draft.cards[0]
    changed_card = first_card.model_copy(update={"voice_text": "changed"})
    changed_draft = initial.output_storyboard_draft.model_copy(
        update={"cards": (changed_card, *initial.output_storyboard_draft.cards[1:])}
    )
    text_drift = initial.model_copy(
        update={"output_storyboard_draft": changed_draft}
    )
    with pytest.raises(ValueError, match="card text"):
        text_drift._assert_output_evidence()

    paid_drift = initial.model_copy(
        update={"paid_image_provider_receipt_digests": (DIGEST_A,) * 16}
    )
    with pytest.raises(ValueError, match="paid source receipts"):
        paid_drift._assert_paid_receipts_and_carrier()

    digest_drift = initial.model_copy(update={"receipt_digest": DIGEST_A})
    with pytest.raises(ValueError, match="receipt_digest"):
        digest_drift._assert_completion_terminal()


def test_phase_a_regen_preserves_every_unpaid_card_image_and_receipt() -> None:
    initial = _phase_a_completion()
    regen = _phase_a_completion(
        purpose="storyboard_regen",
        input_draft=initial.output_storyboard_draft,
        input_image_set=initial.output_image_set_receipt,
    )

    unpaid_card = regen.output_storyboard_draft.cards[1].model_copy(
        update={"caption_text": "changed unpaid card"}
    )
    changed_draft = regen.output_storyboard_draft.model_copy(
        update={
            "cards": (
                regen.output_storyboard_draft.cards[0],
                unpaid_card,
                *regen.output_storyboard_draft.cards[2:],
            )
        }
    )
    with pytest.raises(ValueError, match="unpaid storyboard card"):
        regen._assert_regen_cards_unchanged(
            initial.output_storyboard_draft,
            changed_draft,
        )

    missing_input = regen.model_copy(update={"input_storyboard_draft": None})
    with pytest.raises(ValueError, match="valid successor"):
        missing_input._assert_regen_image_preservation()

    prior_drift = regen.model_copy(
        update={
            "output_image_set_receipt": regen.output_image_set_receipt.model_copy(
                update={"previous_image_set_receipt_digest": DIGEST_A}
            )
        }
    )
    with pytest.raises(ValueError, match="prior sealed image set"):
        prior_drift._assert_regen_image_preservation()

    unpaid_image = regen.output_image_set_receipt.images[1].model_copy(
        update={"artifact_id": "alien-artifact"}
    )
    replaced_set = regen.output_image_set_receipt.model_copy(
        update={
            "images": (
                regen.output_image_set_receipt.images[0],
                unpaid_image,
                *regen.output_image_set_receipt.images[2:],
            )
        }
    )
    replaced = regen.model_copy(update={"output_image_set_receipt": replaced_set})
    with pytest.raises(ValueError, match="replaced an unpaid image"):
        replaced._assert_regen_image_preservation()


def test_phase_a_summary_rejects_digest_and_unverified_operation_proof() -> None:
    summary = StoryboardPhaseACompletionSummaryV1.model_validate(
        _completion_summary()
    )
    with pytest.raises(ValueError, match="summary_digest"):
        summary.model_copy(update={"summary_digest": DIGEST_A})._bind_summary_digest()

    with pytest.raises(ValueError, match="verified live or historical"):
        StoryboardPhaseACompletionSummaryV1.from_completion(
            _phase_a_completion(),
            authority=object(),
            operation_proofs=(),
        )


def test_v3_budget_rejects_cross_phase_or_mismatched_scene_summary() -> None:
    draft_budget = StarReelsBudgetV3.model_validate(_budget("storyboard_draft"))
    with pytest.raises(ValueError, match="cannot carry scene video summary"):
        draft_budget.model_copy(
            update={"storyboard_scene_video_set_summary": object()}
        )._bind_purpose_label_and_paid_call_mask()

    final_budget = StarReelsBudgetV3.model_validate(_budget("final_production"))
    mismatched_summary = SimpleNamespace(
        storyboard_scene_count=7,
        final_production_authority_digest=DIGEST_A,
    )
    with pytest.raises(ValueError, match="does not match final paid budget"):
        final_budget.model_copy(
            update={
                "paid_budget_authority_digest": DIGEST_B,
                "storyboard_scene_video_set_summary": mismatched_summary,
            }
        )._bind_purpose_label_and_paid_call_mask()


def _valid_v3_lock_gate() -> StarReelsViewV3:
    base = StarReelsViewV3.model_validate(_storyboard_review_view())
    draft = ProductElementLockDraftV1.model_validate(_product_draft())
    receipts = base.receipts.model_copy(
        update={
            "factory": None,
            "storyboard_phase_a_completion_summary": None,
        }
    )
    return base.model_copy(
        update={
            "section": "LockGate",
            "status": "awaiting_product_approval",
            "stage_output": draft,
            "review_digest": derive_star_product_lock_review_digest_v1(draft),
            "receipts": receipts,
            "provider_call": "none",
            "error": None,
            "storyboard": None,
        }
    )


def test_v3_typed_output_and_every_legacy_gate_guard() -> None:
    typed = StarReelsViewV3._freeze_typed_review_output(_product_draft())
    assert isinstance(typed, ProductElementLockDraftV1)
    unknown = {"contract_version": "Unknown.v1", "value": 1}
    assert StarReelsViewV3._freeze_typed_review_output(unknown) is unknown

    lock = _valid_v3_lock_gate()
    assert lock._bind_view_shape_to_state() is lock

    base = StarReelsViewV3.model_validate(_storyboard_review_view())
    final_budget = StarReelsBudgetV3.model_validate(_budget("final_production"))
    with pytest.raises(ValueError, match="draft budget purpose"):
        base.model_copy(update={"budget": final_budget})._bind_legacy_gate()
    with pytest.raises(ValueError, match="cannot carry storyboard pointer"):
        base.model_copy(update={"section": "ScriptReview"})._bind_legacy_gate()
    with pytest.raises(ValueError, match="stage_output and review_digest"):
        base.model_copy(
            update={"section": "ScriptReview", "storyboard": None, "stage_output": None}
        )._bind_legacy_gate()
    with pytest.raises(ValueError, match="confirmed script call"):
        base.model_copy(
            update={"section": "ScriptReview", "storyboard": None, "provider_call": "none"}
        )._bind_legacy_gate()
    with pytest.raises(ValueError, match="V3 progress receipt"):
        base.model_copy(
            update={
                "section": "ScriptReview",
                "storyboard": None,
                "receipts": base.receipts.model_copy(update={"factory": None}),
            }
        )._bind_legacy_gate()

    with pytest.raises(ValueError, match="typed product draft"):
        lock.model_copy(update={"stage_output": {"untyped": True}})._bind_lock_gate()
    with pytest.raises(ValueError, match="does not bind the draft"):
        lock.model_copy(update={"review_digest": DIGEST_A})._bind_lock_gate()
    with pytest.raises(ValueError, match="non-review state"):
        lock.model_copy(update={"status": "ready"})._bind_lock_gate()
    with pytest.raises(ValueError, match="cannot carry provider work"):
        lock.model_copy(update={"provider_call": "confirmed"})._bind_lock_gate()
    with pytest.raises(ValueError, match="error does not match"):
        lock.model_copy(update={"status": "missing", "stage_output": None, "review_digest": None, "error": None})._bind_lock_gate()


def test_v3_storyboard_review_and_generation_guards() -> None:
    base = StarReelsViewV3.model_validate(_storyboard_review_view())
    with pytest.raises(ValueError, match="confirmed image work"):
        base.model_copy(update={"provider_call": "none"})._bind_storyboard_review()

    regen = StarReelsViewV3.model_validate(
        _storyboard_review_view(purpose="storyboard_regen")
    )
    executable = FactoryStoryboardCarrierV1.model_validate(
        _carrier(approved=True, executable=True)
    )
    with pytest.raises(ValueError, match="approval or execution manifest"):
        regen.model_copy(
            update={"storyboard": executable, "stage_output": executable}
        )._bind_storyboard_generating(executable)
    with pytest.raises(ValueError, match="echoed without review digest"):
        regen.model_copy(update={"stage_output": None})._bind_storyboard_generating(
            regen.storyboard
        )

    with pytest.raises(ValueError, match="current storyboard pointer"):
        base._bind_storyboard_ready_for_review(None)
    approved = FactoryStoryboardCarrierV1.model_validate(_carrier(approved=True))
    with pytest.raises(ValueError, match="cannot carry approval"):
        base.model_copy(update={"stage_output": approved})._bind_storyboard_ready_for_review(
            approved
        )
    malformed_executable = FactoryStoryboardCarrierV1.model_construct(
        **{
            **_carrier(approved=False),
            "execution_manifest_digest": DIGEST_A,
        }
    )
    with pytest.raises(ValueError, match="execution manifest"):
        base.model_copy(
            update={"stage_output": malformed_executable}
        )._bind_storyboard_ready_for_review(malformed_executable)
    with pytest.raises(ValueError, match="review_digest"):
        base.model_copy(update={"review_digest": DIGEST_A})._bind_storyboard_ready_for_review(
            base.storyboard
        )


def test_v3_production_budget_and_run_status_guards() -> None:
    review = StarReelsViewV3.model_validate(_storyboard_review_view())
    with pytest.raises(ValueError, match="budget purpose is invalid"):
        review._bind_production_budget_gate()

    final_budget = StarReelsBudgetV3.model_validate(_budget("final_production"))
    gate = review.model_copy(update={"budget": final_budget})
    with pytest.raises(ValueError, match="requires storyboard pointer"):
        gate.model_copy(update={"storyboard": None})._bind_production_budget_gate()
    with pytest.raises(ValueError, match="requires storyboard approval"):
        gate._bind_production_budget_gate()

    approved = FactoryStoryboardCarrierV1.model_validate(_carrier(approved=True))
    gate = gate.model_copy(update={"storyboard": approved, "stage_output": approved})
    with pytest.raises(ValueError, match="review_digest"):
        gate.model_copy(update={"review_digest": DIGEST_A})._bind_production_budget_gate()
    with pytest.raises(ValueError, match="cannot carry provider work"):
        gate.model_copy(update={"review_digest": DIGEST_D, "provider_call": "confirmed"})._bind_production_budget_gate()

    with pytest.raises(ValueError, match="must be final_production"):
        review._bind_two_stage_run()
    executable = FactoryStoryboardCarrierV1.model_validate(
        _carrier(approved=True, executable=True)
    )
    run = gate.model_copy(
        update={
            "section": "RunStatus",
            "status": "rendering",
            "storyboard": executable,
            "stage_output": None,
            "review_digest": None,
            "budget": final_budget.model_copy(
                update={"paid_budget_authority_digest": DIGEST_A}
            ),
        }
    )
    with pytest.raises(ValueError, match="approved execution manifest"):
        run._bind_two_stage_pointer(None)
    with pytest.raises(ValueError, match="review-only fields"):
        run.model_copy(update={"stage_output": {"review": True}})._bind_two_stage_pointer(executable)
    with pytest.raises(ValueError, match="failure receipt"):
        run.model_copy(update={"status": "failed", "error": None})._bind_two_stage_error()
    with pytest.raises(ValueError, match="non-failed state"):
        run.model_copy(update={"error": "STALE"})._bind_two_stage_error()
    with pytest.raises(ValueError, match="progress receipt"):
        run.model_copy(
            update={"receipts": run.receipts.model_copy(update={"factory": None})}
        )._bind_two_stage_factory()
    with pytest.raises(ValueError, match="final factory summary"):
        run.model_copy(
            update={"status": "ready", "receipts": run.receipts.model_copy(update={"factory": None})}
        )._bind_two_stage_factory()


def test_v3_paid_budget_authority_and_factory_guards() -> None:
    base = StarReelsViewV3.model_validate(_storyboard_review_view())
    draft_pair = _paid_pair("storyboard_draft")
    final_pair = _paid_pair("final_production")

    with pytest.raises(ValueError, match="unapproved final budget"):
        base._bind_unapproved_budget_evidence(draft_pair[0], draft_pair[1])
    with pytest.raises(ValueError, match="structurally bind"):
        base._bind_paid_authority_budget(draft_pair[0], final_pair[1])
    with pytest.raises(ValueError, match="purpose does not match"):
        base._bind_paid_authority_budget(final_pair[0], final_pair[1])

    calls_drift = base.model_copy(
        update={"budget": base.budget.model_copy(update={"image": 15})}
    )
    with pytest.raises(ValueError, match="calls do not match"):
        calls_drift._bind_paid_authority_budget(draft_pair[0], draft_pair[1])

    with pytest.raises(ValueError, match="current storyboard"):
        base._bind_paid_authority_storyboard(_paid_pair("storyboard_regen")[1], None)
    with pytest.raises(ValueError, match="approved storyboard"):
        base._bind_paid_authority_storyboard(final_pair[1], None)

    progress = base.receipts.factory.model_copy(update={"revision": 99})
    revision_drift = base.model_copy(
        update={"receipts": base.receipts.model_copy(update={"factory": progress})}
    )
    with pytest.raises(ValueError, match="revision does not match"):
        revision_drift._bind_paid_factory(draft_pair[1], base.storyboard)

    final_pointer = FactoryStoryboardCarrierV1.model_validate(
        _carrier(approved=True, executable=True)
    )
    manifest_drift = _progress_receipt_v3(
        final_pair[1],
        revision=7,
        stage="video",
        provider_attempts={
            "script": 0,
            "image": 0,
            "video": 1,
            "voice": 0,
            "render": 0,
        },
        storyboard_execution_manifest_digest=DIGEST_B,
    )
    final_view = base.model_copy(
        update={
            "revision": 7,
            "receipts": base.receipts.model_copy(
                update={
                    "factory": base.receipts.factory.__class__.model_validate(
                        manifest_drift
                    )
                }
            ),
        }
    )
    with pytest.raises(ValueError, match="execution manifest"):
        final_view._bind_paid_factory(final_pair[1], final_pointer)

    malformed_success = ReelsFactoryCompletionSummaryV3.model_construct(
        workspace_id="wrong",
        run_id="wrong",
        factory_revision=0,
        plan_digest=DIGEST_A,
        paid_budget_authority_digest=DIGEST_A,
        storyboard_execution_manifest_digest=DIGEST_A,
    )
    success_view = base.model_copy(
        update={
            "receipts": base.receipts.model_copy(update={"factory": malformed_success})
        }
    )
    with pytest.raises(ValueError, match="factory success"):
        success_view._bind_paid_factory(final_pair[1], final_pointer)


def test_v3_phase_a_summary_and_provider_state_guards() -> None:
    base = StarReelsViewV3.model_validate(_storyboard_review_view())
    summary = base.receipts.storyboard_phase_a_completion_summary
    assert summary is not None
    lock = _valid_v3_lock_gate()
    with pytest.raises(ValueError, match="pre-completion state"):
        lock.model_copy(
            update={
                "receipts": lock.receipts.model_copy(
                    update={"storyboard_phase_a_completion_summary": summary}
                )
            }
        )._bind_phase_a_completion_summary()
    with pytest.raises(ValueError, match="requires storyboard pointer"):
        base.model_copy(update={"storyboard": None})._bind_phase_a_completion_summary()

    pointer = base.storyboard
    assert pointer is not None
    with pytest.raises(ValueError, match="storyboard lineage"):
        StarReelsViewV3._bind_phase_a_summary_lineage(
            summary.model_copy(update={"output_image_set_receipt_digest": DIGEST_A}),
            pointer,
        )
    with pytest.raises(ValueError, match="current storyboard"):
        StarReelsViewV3._bind_phase_a_summary_lineage(
            summary.model_copy(update={"output_storyboard_digest": DIGEST_A}),
            pointer,
        )

    newer_pointer = pointer.model_copy(
        update={"storyboard_revision": pointer.storyboard_revision + 1}
    )
    assert base._bind_phase_a_review_authority(summary, newer_pointer) is None
    with pytest.raises(ValueError, match="carrier digest drifted"):
        base._bind_phase_a_review_authority(
            summary.model_copy(update={"output_storyboard_carrier_digest": DIGEST_A}),
            pointer,
        )

    with pytest.raises(ValueError, match="provider_call"):
        base.model_copy(
            update={"provider_call": "none"}
        )._bind_factory_receipt_provider_state()
