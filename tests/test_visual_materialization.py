from copy import deepcopy
from dataclasses import asdict
import json
import pickle

import pytest

from hiob_contracts import (
    BeatCastIntentV1,
    BeatFramePlanV1,
    BeatFramePlanV2,
    CastRoleIntentV1,
    PlannedReferenceV1,
    ReferenceSnapshotV1,
    VisualMaterializationRequestV1,
    VisualMaterializationRequestV2,
    VisualMaterializationReceiptV1,
    SEEDREAM_5_PRO_MODEL_ID,
    VISUAL_CONTRACT_VERSION_V2,
    VISUAL_RENDER_MODES_V1,
    assert_visual_provider_key_reuse_safe_v2,
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


def _v1_plan():
    return BeatFramePlanV1.create(
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


def test_v2_binds_ares_visual_bridge_and_policy_into_plan_digest():
    v1 = _v1_plan()
    bridge = sha256_digest({"visual_seal": "sealed", "beat_plan": "sealed"})
    plan = BeatFramePlanV2.from_v1(
        v1,
        visual_bridge_digest=bridge,
        visual_policy={"allow_all_persona": False},
    )

    assert plan.validate() == []
    assert plan.contract_version == VISUAL_CONTRACT_VERSION_V2
    assert plan.visual_bridge_digest == bridge
    assert plan.visual_policy == {"allow_all_persona": False}
    assert BeatFramePlanV2.from_dict(plan.to_dict()) == plan

    other_bridge = BeatFramePlanV2.from_v1(
        v1,
        visual_bridge_digest=sha256_digest({"visual_seal": "other"}),
        visual_policy={"allow_all_persona": False},
    )
    other_policy = BeatFramePlanV2.from_v1(
        v1,
        visual_bridge_digest=bridge,
        visual_policy={"allow_all_persona": True},
    )
    assert other_bridge.plan_digest != plan.plan_digest
    assert other_policy.plan_digest != plan.plan_digest


def test_v2_rejects_unsealed_bridge_policy_and_tampering():
    v1 = _v1_plan()
    bridge = sha256_digest({"visual_seal": "sealed"})

    bad_bridge = BeatFramePlanV2.from_v1(
        v1,
        visual_bridge_digest="not-a-digest",
        visual_policy={"allow_all_persona": False},
    )
    assert any("visual_bridge_digest" in error for error in bad_bridge.validate())

    bad_policy = BeatFramePlanV2.from_v1(
        v1,
        visual_bridge_digest=bridge,
        visual_policy={"allow_all_persona": "false"},
    )
    assert any("boolean" in error for error in bad_policy.validate())

    extra_policy = BeatFramePlanV2.from_v1(
        v1,
        visual_bridge_digest=bridge,
        visual_policy={"allow_all_persona": False, "invent_persona": True},
    )
    assert any("only allow_all_persona" in error for error in extra_policy.validate())

    tampered = BeatFramePlanV2.from_dict({
        **BeatFramePlanV2.from_v1(
            v1,
            visual_bridge_digest=bridge,
            visual_policy={"allow_all_persona": False},
        ).to_dict(),
        "visual_policy": {"allow_all_persona": True},
    })
    assert any("plan_digest" in error for error in tampered.validate())


def test_v1_plan_remains_v1_without_v2_fields():
    plan = _v1_plan()
    assert plan.validate() == []
    assert "contract_version" not in plan.to_dict()
    assert "visual_bridge_digest" not in plan.to_dict()
    assert "visual_policy" not in plan.to_dict()


def test_v2_request_roundtrip_preserves_paid_command_identity_and_rejects_downgrade():
    plan = BeatFramePlanV2.from_v1(
        _v1_plan(),
        visual_bridge_digest=sha256_digest("visual-bridge"),
        visual_policy={"allow_all_persona": False},
    )
    request = VisualMaterializationRequestV2(
        plan,
        "11111111-1111-4111-8111-111111111111",
    )
    payload = request.to_dict()
    restored = VisualMaterializationRequestV2.from_dict(payload)

    assert restored.validate() == []
    assert restored.plan.plan_digest == plan.plan_digest
    assert restored.idempotency_key == request.idempotency_key
    assert restored.to_dict() == payload

    v1_request = VisualMaterializationRequestV1(
        _v1_plan(),
        "11111111-1111-4111-8111-111111111111",
    )
    with pytest.raises(ValueError, match="V2|downgrade"):
        VisualMaterializationRequestV2.from_dict(v1_request.to_dict())
    direct_downgrade = VisualMaterializationRequestV2(
        v1_request.plan,  # type: ignore[arg-type]
        "11111111-1111-4111-8111-111111111111",
    )
    assert any("BeatFramePlanV2" in error for error in direct_downgrade.validate())

    downgraded = deepcopy(payload)
    downgraded["plan"]["contract_version"] = "visual-materialization.v1"
    with pytest.raises(ValueError, match="V2|downgrade"):
        VisualMaterializationRequestV2.from_dict(downgraded)


def test_v2_upgrade_rejects_tampered_v1_plan():
    v1 = _v1_plan()
    tampered = BeatFramePlanV1.from_dict({
        **v1.to_dict(),
        "prompt": "tampered after the V1 digest was sealed",
    })
    assert any("plan_digest" in error for error in tampered.validate())

    with pytest.raises(ValueError, match="invalid BeatFramePlanV1"):
        BeatFramePlanV2.from_v1(
            tampered,
            visual_bridge_digest=sha256_digest("visual-bridge"),
            visual_policy={"allow_all_persona": False},
        )


def test_v2_nested_inputs_and_serialized_outputs_cannot_mutate_sealed_plan():
    source_shot = {
        "beat_index": 2,
        "composition": {
            "layers": [{"role": "lead", "weight": 1}],
        },
    }
    source_policy = {"allow_all_persona": False}
    v1 = BeatFramePlanV1.create(
        run_id="run-1",
        workspace_id="ws-1",
        beat_index=2,
        shot_list_digest=sha256_digest({"shots": [2]}),
        render_mode="duet",
        ordered_refs=(PlannedReferenceV1("lead", True, _ref()),),
        shot=source_shot,
        prompt="Preserve identity exactly.",
        prompt_constitution_version="visual-constitution.v1",
    )
    plan = BeatFramePlanV2.from_v1(
        v1,
        visual_bridge_digest=sha256_digest("visual-bridge"),
        visual_policy=source_policy,
    )
    sealed_digest = plan.plan_digest

    source_shot["composition"]["layers"][0]["weight"] = 99
    source_policy["allow_all_persona"] = True
    output = plan.to_dict()
    output["shot"]["composition"]["layers"][0]["weight"] = 77
    output["visual_policy"]["allow_all_persona"] = True

    fresh = plan.to_dict()
    assert fresh["shot"]["composition"]["layers"][0]["weight"] == 1
    assert fresh["visual_policy"] == {"allow_all_persona": False}
    assert plan.plan_digest == sealed_digest
    assert plan.validate() == []
    with pytest.raises(TypeError):
        plan.shot["composition"]["layers"][0]["weight"] = 55


def test_v2_command_identity_binds_review_toggle_and_guards_provider_key_reuse():
    plan = BeatFramePlanV2.from_v1(
        _v1_plan(),
        visual_bridge_digest=sha256_digest("visual-bridge"),
        visual_policy={"allow_all_persona": False},
    )
    reviewed = VisualMaterializationRequestV2(
        plan,
        "11111111-1111-4111-8111-111111111111",
        requires_human_review=True,
    )
    no_review = VisualMaterializationRequestV2(
        plan,
        "11111111-1111-4111-8111-111111111111",
        requires_human_review=False,
    )

    assert reviewed.provider_idempotency_key == no_review.provider_idempotency_key
    assert reviewed.command_digest != no_review.command_digest
    assert reviewed.idempotency_key != no_review.idempotency_key
    with pytest.raises(ValueError, match="provider_idempotency_key reuse"):
        assert_visual_provider_key_reuse_safe_v2(reviewed, no_review)
    assert (
        assert_visual_provider_key_reuse_safe_v2(
            reviewed,
            VisualMaterializationRequestV2.from_dict(reviewed.to_dict()),
        )
        == reviewed.provider_idempotency_key
    )


def test_v2_immutable_json_supports_asdict_deepcopy_and_pickle():
    plan = BeatFramePlanV2.from_v1(
        _v1_plan(),
        visual_bridge_digest=sha256_digest("visual-bridge"),
        visual_policy={"allow_all_persona": False},
    )

    request = VisualMaterializationRequestV2(
        plan,
        "11111111-1111-4111-8111-111111111111",
    )
    dataclass_value = asdict(plan)
    request_dataclass_value = asdict(request)
    copied = deepcopy(plan)
    restored = pickle.loads(pickle.dumps(plan))

    assert isinstance(dataclass_value["shot"], dict)
    assert isinstance(dataclass_value["visual_policy"], dict)
    assert isinstance(request_dataclass_value["plan"]["shot"], dict)
    json.dumps(dataclass_value, sort_keys=True)
    json.dumps(request_dataclass_value, sort_keys=True)
    assert dataclass_value["shot"]["beat_index"] == 2
    assert copied == plan
    assert restored == plan
    assert copied.validate() == []
    assert restored.validate() == []
    with pytest.raises(TypeError):
        copied.shot["beat_index"] = 9


def test_provider_key_guard_validates_direct_request_objects_before_comparison():
    plan = BeatFramePlanV2.from_v1(
        _v1_plan(),
        visual_bridge_digest=sha256_digest("visual-bridge"),
        visual_policy={"allow_all_persona": False},
    )
    valid = VisualMaterializationRequestV2(
        plan,
        "11111111-1111-4111-8111-111111111111",
    )
    invalid_nonce = VisualMaterializationRequestV2(plan, "not-a-uuid")
    downgraded = VisualMaterializationRequestV2(
        _v1_plan(),  # type: ignore[arg-type]
        "11111111-1111-4111-8111-111111111111",
    )

    with pytest.raises(ValueError, match="invalid|generation_nonce"):
        assert_visual_provider_key_reuse_safe_v2(invalid_nonce, valid)
    with pytest.raises(ValueError, match="invalid|downgrade|BeatFramePlanV2"):
        assert_visual_provider_key_reuse_safe_v2(valid, downgraded)


def test_v2_paid_boundary_rejects_unknown_outer_and_plan_fields():
    request = VisualMaterializationRequestV2(
        BeatFramePlanV2.from_v1(
            _v1_plan(),
            visual_bridge_digest=sha256_digest("visual-bridge"),
            visual_policy={"allow_all_persona": False},
        ),
        "11111111-1111-4111-8111-111111111111",
    )
    extra_outer = {**request.to_dict(), "retry_hint": "unsafe"}
    with pytest.raises(ValueError, match="unexpected|extra"):
        VisualMaterializationRequestV2.from_dict(extra_outer)

    extra_plan = deepcopy(request.to_dict())
    extra_plan["plan"]["provider_override"] = "other"
    with pytest.raises(ValueError, match="unexpected|extra"):
        VisualMaterializationRequestV2.from_dict(extra_plan)

    extra_snapshot = deepcopy(request.to_dict())
    extra_snapshot["plan"]["ordered_refs"][0]["snapshot"]["provider_hint"] = "unsafe"
    with pytest.raises(ValueError, match="unexpected|extra"):
        VisualMaterializationRequestV2.from_dict(extra_snapshot)


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
