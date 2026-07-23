from hiob_contracts import (
    BeatCastIntentV1,
    BeatFramePlanV1,
    CastRoleIntentV1,
    PlannedReferenceV1,
    ReferenceSnapshotV1,
    VisualMaterializationRequestV1,
    VisualMaterializationReceiptV1,
    SEEDREAM_5_PRO_MODEL_ID,
    VISUAL_RENDER_MODES_V1,
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


def test_v1_render_modes_are_one_shared_contract():
    assert VISUAL_RENDER_MODES_V1 == frozenset({
        "persona_talk",
        "duet",
        "hands_demo",
        "product_solo",
        "social_proof",
        "scene_no_person",
        "situation_pov",
        "before_after",
    })


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
        transport="piapi",
    )
    errors = receipt.validate()
    assert any("fallback" in error for error in errors)
    assert any("artifact_sha256" in error for error in errors)
    assert any("semantic_validation" in error for error in errors)


def _production_piapi_receipt(**overrides):
    """Production-shaped committed receipt matching live Seedream worker fields."""
    refs = (
        {"role": "lead", "storage_key": "sealed/mom/front.png", "content_digest": sha256_digest("mom")},
        {"role": "co_star", "storage_key": "sealed/child/front.png", "content_digest": sha256_digest("child")},
        {"role": "product", "storage_key": "sealed/sku/hero.png", "content_digest": sha256_digest("sku")},
    )
    base = dict(
        idempotency_key=sha256_digest("request-live"),
        plan_digest=sha256_digest("plan-live"),
        status="committed",
        requested_provider="seedream",
        requested_model=SEEDREAM_5_PRO_MODEL_ID,
        resolved_provider="seedream",
        resolved_model=SEEDREAM_5_PRO_MODEL_ID,
        transport="piapi",
        planned_refs=refs,
        downloaded_refs=refs,
        sent_refs=refs,
        provider_task_id="ddce02d0-d7ec-42e8-a69c-6fd68e91ab7d",
        actual_width=1440,
        actual_height=2560,
        artifact_sha256=sha256_digest("artifact-bytes"),
        semantic_validation={"ok": True, "roles_matched": True},
        human_review_status="not_required",
    )
    base.update(overrides)
    return VisualMaterializationReceiptV1(**base)


def test_production_piapi_receipt_validates_when_lineage_and_semantic_ok():
    from hiob_contracts import SEEDREAM_V1_TRANSPORT

    receipt = _production_piapi_receipt()
    assert receipt.transport == SEEDREAM_V1_TRANSPORT == "piapi"
    assert receipt.validate() == []
    # Round-trip must preserve transport so consumers see piapi SSOT.
    assert VisualMaterializationReceiptV1.from_dict(receipt.to_dict()).validate() == []


def test_receipt_rejects_byteplus_and_wrong_engine_transports():
    errors = _production_piapi_receipt(transport="byteplus_modelark").validate()
    assert any("transport" in e and "piapi" in e for e in errors)

    errors = _production_piapi_receipt(transport="openai").validate()
    assert any("transport" in e for e in errors)


def test_receipt_rejects_degrade_and_lineage_drift():
    errors = _production_piapi_receipt(degraded_reason="used_neighbor_beat").validate()
    assert any("degraded" in e for e in errors)

    drifted = (
        {"role": "lead", "storage_key": "other.png", "content_digest": sha256_digest("x")},
    )
    errors = _production_piapi_receipt(sent_refs=drifted).validate()
    assert any("lineage" in e for e in errors)

    errors = _production_piapi_receipt(
        requested_model=SEEDREAM_5_PRO_MODEL_ID,
        resolved_model="gpt-image-1",
    ).validate()
    assert any("fallback" in e or "model" in e for e in errors)

    errors = _production_piapi_receipt(human_review_status="pending").validate()
    assert any("human" in e for e in errors)
