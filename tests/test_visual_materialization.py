from hiob_contracts import (
    BeatCastIntentV1,
    BeatFramePlanV1,
    CastRoleIntentV1,
    PlannedReferenceV1,
    ReferenceSnapshotV1,
    VisualMaterializationRequestV1,
    VisualMaterializationReceiptV1,
    SEEDREAM_5_PRO_MODEL_ID,
)
from hiob_contracts.factory import sha256_digest


def _ref(kind="character", owner="parzifal", subject="mom"):
    return ReferenceSnapshotV1(
        owner=owner,
        workspace_id="ws-1",
        master_id=f"master-{subject}",
        version=1,
        approval_status="approved",
        storage_key=f"sealed/{subject}/front.png",
        content_digest=sha256_digest({"subject": subject}),
        ref_kind=kind,
        subject_id=subject,
    )


def test_reference_ownership_and_cast_roundtrip():
    product = _ref("product", "artemis", "sku-1")
    assert product.validate() == []
    bad = _ref("product", "parzifal", "sku-1")
    assert any("artemis" in error for error in bad.validate())

    cast = BeatCastIntentV1(
        beat_index=2,
        render_mode="duet",
        roles=(
            CastRoleIntentV1("lead", "mom"),
            CastRoleIntentV1("co_star", "child"),
        ),
    )
    assert BeatCastIntentV1.from_dict(cast.to_dict()) == cast
    assert ReferenceSnapshotV1.from_dict({
        **product.to_dict(), "compatibility_metadata": {"legacy": True}
    }) == product


def test_plan_digest_request_idempotency_and_roundtrip():
    plan = BeatFramePlanV1.create(
        run_id="run-1",
        workspace_id="ws-1",
        beat_index=2,
        shot_list_digest=sha256_digest({"shots": [2]}),
        render_mode="duet",
        ordered_refs=(PlannedReferenceV1("lead", True, _ref()),),
        shot={"beat_index": 2, "shot_size": "mcu"},
        prompt="Image 1 is the approved lead. Preserve identity exactly.",
        prompt_constitution_version="visual-constitution.v1",
    )
    assert plan.validate() == []
    assert BeatFramePlanV1.from_dict(plan.to_dict()) == plan

    request = VisualMaterializationRequestV1(plan, "11111111-1111-4111-8111-111111111111")
    assert request.validate() == []
    assert request.requires_human_review is True
    assert request.idempotency_key == VisualMaterializationRequestV1.from_dict(
        request.to_dict()
    ).idempotency_key
    assert VisualMaterializationRequestV1(
        plan, "22222222-2222-4222-8222-222222222222"
    ).idempotency_key != request.idempotency_key


def test_receipt_rejects_fallback_and_false_green():
    receipt = VisualMaterializationReceiptV1(
        idempotency_key=sha256_digest("request"),
        plan_digest=sha256_digest("plan"),
        status="committed",
        requested_provider="seedream",
        requested_model=SEEDREAM_5_PRO_MODEL_ID,
        resolved_provider="openai",
        resolved_model="gpt-image-2",
    )
    errors = receipt.validate()
    assert any("fallback" in error for error in errors)
    assert any("artifact_sha256" in error for error in errors)
    assert any("semantic_validation" in error for error in errors)
