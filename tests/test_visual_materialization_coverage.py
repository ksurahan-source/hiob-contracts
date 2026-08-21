"""Fail-closed edge coverage for visual materialization contracts."""

from dataclasses import replace

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
    assert_visual_provider_key_reuse_safe_v2,
)
from hiob_contracts.factory import sha256_digest
from hiob_contracts.visual_materialization import _deep_freeze, _deep_thaw
from tests.test_visual_materialization import (
    _production_piapi_receipt,
    _ref,
    _v1_plan,
)


def _v2_request() -> VisualMaterializationRequestV2:
    plan = BeatFramePlanV2.from_v1(
        _v1_plan(),
        visual_bridge_digest=sha256_digest("visual-bridge"),
        visual_policy={"allow_all_persona": False},
    )
    return VisualMaterializationRequestV2(
        plan,
        "11111111-1111-4111-8111-111111111111",
    )


def test_frozen_json_mapping_supports_read_protocol_and_blocks_mutation() -> None:
    frozen = _deep_freeze({"nested": {"values": {1, 2}}})
    assert len(frozen) == 1
    assert "nested" in repr(frozen)
    assert frozen != ["nested"]
    with pytest.raises(KeyError):
        frozen["missing"]
    with pytest.raises(TypeError, match="cannot be mutated"):
        setattr(frozen, "new_value", 1)
    assert sorted(_deep_thaw(frozen)["nested"]["values"]) == [1, 2]


def test_reference_and_cast_validation_reports_all_invalid_authority() -> None:
    invalid_reference = ReferenceSnapshotV1(
        owner="artemis",
        workspace_id="",
        master_id="",
        version=0,
        approval_status="draft",
        storage_key="",
        content_digest="invalid",
        ref_kind="character",
        subject_id="",
    )
    errors = invalid_reference.validate()
    for expected in (
        "workspace_id is required",
        "master_id is required",
        "storage_key is required",
        "subject_id is required",
        "version must be >= 1",
        "reference must be approved",
        "content_digest must be a sha256 digest",
        "character references must be owned by parzifal",
    ):
        assert expected in errors

    required = CastRoleIntentV1("lead", "", "required")
    forbidden = CastRoleIntentV1("product", "", "forbidden")
    cast = BeatCastIntentV1(
        beat_index=0,
        render_mode="duet",
        roles=(required, required, forbidden),
    )
    assert cast.required_roles() == (required, required)
    assert cast.forbidden_roles() == (forbidden,)
    errors = cast.validate()
    assert any("duplicate role" in error for error in errors)
    assert any("subject_id is required" in error for error in errors)


def test_v1_plan_validation_reports_scope_engine_reference_and_lock_drift() -> None:
    valid = _v1_plan()
    duplicate = valid.ordered_refs[0]
    cross_workspace = PlannedReferenceV1(
        "co_star",
        True,
        replace(_ref(subject="child"), workspace_id="other-workspace"),
    )
    invalid = replace(
        valid,
        run_id="",
        workspace_id="",
        shot_list_digest="invalid",
        provider="other",
        model="other",
        prompt=" ",
        prompt_constitution_version=" ",
        shot={"beat_index": 99},
        lock_policy="soft",
        max_refs=0,
        ordered_refs=(duplicate, duplicate, cross_workspace),
        plan_digest="invalid",
    )
    errors = invalid.validate()
    for expected in (
        "run_id and workspace_id are required",
        "shot_list_digest must be a sha256 digest",
        "materialization engine",
        "compiled prompt is required",
        "prompt_constitution_version is required",
        "matching beat_index",
        "lock_policy",
        "max_refs",
        "exceeds max_refs",
        "duplicate storage keys",
        "cross-workspace reference",
        "plan_digest",
    ):
        assert any(expected in error for error in errors)


def test_v2_plan_from_dict_rejects_each_unsealed_reference_shape() -> None:
    plan = _v2_request().plan
    payload = plan.to_dict()

    downgraded = {**payload, "contract_version": "visual-materialization.v1"}
    with pytest.raises(ValueError, match="downgrade"):
        BeatFramePlanV2.from_dict(downgraded)

    object_ref = {**payload, "ordered_refs": [plan.ordered_refs[0]]}
    assert BeatFramePlanV2.from_dict(object_ref).ordered_refs == plan.ordered_refs

    raw_ref = payload["ordered_refs"][0]
    with pytest.raises(ValueError, match="ordered_ref must be an object"):
        BeatFramePlanV2.from_dict({**payload, "ordered_refs": ["invalid"]})

    non_boolean = {**raw_ref, "required": 1}
    with pytest.raises(ValueError, match="must be a boolean"):
        BeatFramePlanV2.from_dict({**payload, "ordered_refs": [non_boolean]})

    snapshot_object = {**raw_ref, "snapshot": plan.ordered_refs[0].snapshot}
    restored = BeatFramePlanV2.from_dict(
        {**payload, "ordered_refs": [snapshot_object]}
    )
    assert restored.ordered_refs[0].snapshot == plan.ordered_refs[0].snapshot

    missing_snapshot = {**raw_ref, "snapshot": None}
    with pytest.raises(ValueError, match="snapshot must be an object"):
        BeatFramePlanV2.from_dict(
            {**payload, "ordered_refs": [missing_snapshot]}
        )


def test_v1_and_v2_requests_reject_nonce_version_and_policy_types() -> None:
    assert "generation_nonce is required" in VisualMaterializationRequestV1(
        _v1_plan(), ""
    ).validate()
    assert "generation_nonce must be a UUID" in VisualMaterializationRequestV1(
        _v1_plan(), "not-a-uuid"
    ).validate()

    request = _v2_request()
    assert any(
        "contract_version" in error
        for error in replace(
            request.plan,
            contract_version="visual-materialization.v1",
        ).validate()
    )
    invalid = replace(
        request,
        generation_nonce="",
        requires_human_review=1,
        contract_version="visual-materialization.v1",
    )
    errors = invalid.validate()
    assert any("contract_version" in error for error in errors)
    assert "generation_nonce is required" in errors
    assert "requires_human_review must be a boolean" in errors


def test_v2_request_parser_rejects_downgrades_bad_plans_and_digest_drift() -> None:
    request = _v2_request()
    payload = request.to_dict()

    with pytest.raises(ValueError, match="downgrade"):
        VisualMaterializationRequestV2.from_dict(
            {**payload, "contract_version": "visual-materialization.v1"}
        )
    with pytest.raises(ValueError, match="must be a boolean"):
        VisualMaterializationRequestV2.from_dict(
            {**payload, "requires_human_review": 1}
        )
    with pytest.raises(ValueError, match="invalid VisualMaterializationRequestV2"):
        VisualMaterializationRequestV2.from_dict(
            {**payload, "generation_nonce": ""}
        )

    with pytest.raises(ValueError, match="BeatFramePlanV1 downgrade"):
        VisualMaterializationRequestV2.from_dict(
            {**payload, "plan": _v1_plan()}
        )
    restored = VisualMaterializationRequestV2.from_dict(
        {**payload, "plan": request.plan}
    )
    assert restored == request
    with pytest.raises(ValueError, match="requires BeatFramePlanV2"):
        VisualMaterializationRequestV2.from_dict({**payload, "plan": 1})

    for field in (
        "provider_idempotency_key",
        "command_digest",
        "idempotency_key",
    ):
        altered = {**payload, field: sha256_digest({"wrong": field})}
        with pytest.raises(ValueError, match=field):
            VisualMaterializationRequestV2.from_dict(altered)


def test_provider_guard_accepts_serialized_equal_commands() -> None:
    payload = _v2_request().to_dict()
    assert assert_visual_provider_key_reuse_safe_v2(payload, payload) == (
        payload["provider_idempotency_key"]
    )


def test_receipt_rejects_invalid_request_and_plan_digests() -> None:
    errors = _production_piapi_receipt(
        idempotency_key="invalid",
        plan_digest="invalid",
    ).validate()
    assert "idempotency_key and plan_digest must be sha256 digests" in errors
