"""Ares V3 pure I/O contract: producer authority in, semantic script out."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    AresAuthorityArtifactRefV3,
    AresCreateScriptRequestV3,
    AresCreateScriptResultV3,
    AresP2ATargetProjectionV3,
    AresRequestScopeV3,
    AresSemanticBeatV3,
    ScriptPackageV3,
    SemanticBeatPlanV3,
    ares_create_script_request_v3_schema_digest,
    ares_create_script_result_v3_schema_digest,
    canonical_contract_digest_v1,
    request_content_digest_v3,
    sha256_digest,
    authority_ref_receipt_digest_v3,
    ares_p2a_target_projection_v3_schema_descriptor,
    ares_p2a_target_projection_v3_schema_digest,
    karma_receipt_digest_v3,
)
from hiob_contracts.ares_create_script_v3 import (
    AresGenerateProvenanceV3,
    AresGenerateUsageV3,
    AresQualityFindingV3,
)
from hiob_contracts.factory import KarmaEdgeReceipt


WORKSPACE_ID = "ws-v3-1"
RUN_ID = "run-v3-1"
IDENTITY_DIGEST = sha256_digest({"identity": "lock-1"})
PRODUCT_DIGEST = sha256_digest({"product": "truth-1"})
EVIDENCE_DIGEST = sha256_digest({"evidence": "approved-1"})
HOOK_DIGEST = sha256_digest({"hook": "metis-1"})
STAR_COMMAND_OUTPUT_DIGEST = sha256_digest({"star": "ares-v3-command-1"})
KARMA_OUTPUT_DIGEST = sha256_digest({"karma": "p2a-output-1"})


def identity_payload() -> dict:
    return {
        "identity_lock_digest": IDENTITY_DIGEST,
        "cast_sheet_digest": sha256_digest({"cast": "sheet-1"}),
        "speakers": [
            {
                "role": "lead",
                "subject_id": "mom",
                "display_name": "정원이",
                "voice_id": None,
                "face_id": None,
                "identity_binding_digest": None,
            }
        ],
        "voice_spec": None,
        "locale": "ko",
        "audience_lock": None,
    }


def product_payload() -> dict:
    return {
        "product_truth_digest": PRODUCT_DIGEST,
        "brand_slug": "viewok",
        "brand_display_name": "뷰옥",
        "product_name": "XL 세럼",
        "listing_slug": None,
        "listing_pitch": None,
        "price_text": None,
        "refund_policy_text": None,
        "usp_lines": [],
        "regulation_notes": None,
        "facts_block": {},
    }


def evidence_payload() -> dict:
    return {
        "evidence_bundle_digest": EVIDENCE_DIGEST,
        "claims": [
            {
                "claim_id": "c1",
                "text": "빠른 흡수",
                "claim_kind": "product_fact",
                "provenance": None,
                "evidence_ref": None,
            }
        ],
        "voc_quotes": [],
        "allowed_claim_ids": ["c1"],
    }


def hook_payload() -> dict:
    return {
        "directive_digest": HOOK_DIGEST,
        "archetype_id": "gossip_reveal",
        "hook_line": None,
        "hook_register": None,
        "experiment_id": None,
        "rationale": None,
    }


def accepted_p2a_receipt(
    target_input: dict,
    source_output_digests: list[str],
) -> dict:
    return {
        "receipt_id": "karma-p2a-rcpt-1",
        "edge_id": "p2a",
        "run_id": RUN_ID,
        "factory_revision": 3,
        "workspace_id": WORKSPACE_ID,
        "source_output_digests": source_output_digests,
        "target_contract": {
            "name": "AresP2ATargetProjection",
            "version": "v3",
            "schema_digest": ares_p2a_target_projection_v3_schema_digest(),
        },
        "decision": "accepted",
        "target_input": target_input,
        "target_input_digest": sha256_digest(target_input),
        "transform_log": [],
        "violations": [],
        "waiver_receipt_refs": [],
        "mapper": {
            "planet": "karma",
            "node_id": "karma.edge.refine",
            "revision": "r3",
            "policy_digest": sha256_digest({"policy": "p2a-r3"}),
        },
        "created_at": "2026-07-26T00:00:00Z",
    }


def authority_ref(
    producer: str,
    artifact_type: str,
    artifact_digest: str,
    payload: dict,
) -> dict:
    body = {
        "producer": producer,
        "artifact_type": artifact_type,
        "artifact_digest": artifact_digest,
        "source_output_digest": sha256_digest(
            {"producer_output": f"{producer}-{artifact_type}-1"}
        ),
        "payload_digest": sha256_digest(payload),
        "receipt_id": f"{producer}-{artifact_type}-receipt-1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
    }
    body["receipt_digest"] = authority_ref_receipt_digest_v3(
        receipt_id=body["receipt_id"],
        producer=producer,
        artifact_type=artifact_type,
        artifact_digest=artifact_digest,
        source_output_digest=body["source_output_digest"],
        payload_digest=body["payload_digest"],
        workspace_id=WORKSPACE_ID,
        run_id=RUN_ID,
    )
    return body


def request_data() -> dict:
    identity = identity_payload()
    product = product_payload()
    evidence = evidence_payload()
    hook = hook_payload()
    scope = {
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "operation_id": "op-script-v3-1",
        "idempotency_key": "ares-script-v3:ws-v3-1:run-v3-1:op-script-v3-1",
    }
    identity_ref = authority_ref("parzifal", "identity_lock", IDENTITY_DIGEST, identity)
    product_ref = authority_ref("janus", "product_truth", PRODUCT_DIGEST, product)
    evidence_ref = authority_ref(
        "artemis", "evidence_bundle", EVIDENCE_DIGEST, evidence
    )
    hook_ref = authority_ref("metis", "hook_directive", HOOK_DIGEST, hook)
    projection = AresP2ATargetProjectionV3.model_validate(
        {
            "contract_version": "AresP2ATargetProjection.v3",
            "scope": scope,
            "command_source_output_digest": STAR_COMMAND_OUTPUT_DIGEST,
            "identity_ref": identity_ref,
            "product_ref": product_ref,
            "evidence_ref": evidence_ref,
            "hook_ref": hook_ref,
            "creative_constraints": {
                "n_beats": 2,
                "format_mode": None,
                "style_mode": None,
                "vertical_mode": None,
                "goal": None,
                "fixed_hook": None,
                "human_instruction": "",
                "prior_script_package_digest": None,
                "banned_phrases": [],
                "required_phrases": [],
            },
        }
    )
    target_input = projection.model_dump(mode="json")
    receipt_body = accepted_p2a_receipt(
        target_input,
        [
            identity_ref["source_output_digest"],
            product_ref["source_output_digest"],
            evidence_ref["source_output_digest"],
            hook_ref["source_output_digest"],
            STAR_COMMAND_OUTPUT_DIGEST,
        ],
    )
    receipt = KarmaEdgeReceipt.model_validate(receipt_body)
    receipt_digest = karma_receipt_digest_v3(receipt)
    p2a_payload_digest = receipt.target_input_digest
    assert p2a_payload_digest is not None
    return {
        "contract_version": "AresCreateScriptRequest.v3",
        "scope": scope,
        "authority": {
            "identity_ref": identity_ref,
            "product_ref": product_ref,
            "evidence_ref": evidence_ref,
            "hook_ref": hook_ref,
            "p2a_ref": {
                **authority_ref(
                    "karma",
                    "p2a_receipt",
                    p2a_payload_digest,
                    receipt.target_input or {},
                ),
                "receipt_id": receipt.receipt_id,
                "receipt_digest": receipt_digest,
                "source_output_digest": KARMA_OUTPUT_DIGEST,
            },
            "accepted_p2a_receipt": receipt_body,
        },
        "identity": identity,
        "product_facts": product,
        "evidence_and_claims": evidence,
        "hook_directive": hook,
        "creative_constraints": {"n_beats": 2},
    }


@pytest.mark.parametrize(
    ("ref_name", "field", "value"),
    [
        ("identity_ref", "workspace_id", "ws-other"),
        ("product_ref", "run_id", "run-other"),
        ("evidence_ref", "producer", "janus"),
        ("hook_ref", "artifact_type", "product_truth"),
    ],
)
def test_v3_projection_rejects_cross_scope_and_wrong_owner_refs(
    ref_name: str,
    field: str,
    value: str,
):
    projection = deepcopy(
        request_data()["authority"]["accepted_p2a_receipt"]["target_input"]
    )
    projection[ref_name][field] = value
    ref = projection[ref_name]
    ref["receipt_digest"] = authority_ref_receipt_digest_v3(
        receipt_id=ref["receipt_id"],
        producer=ref["producer"],
        artifact_type=ref["artifact_type"],
        artifact_digest=ref["artifact_digest"],
        source_output_digest=ref["source_output_digest"],
        payload_digest=ref["payload_digest"],
        workspace_id=ref["workspace_id"],
        run_id=ref["run_id"],
    )

    with pytest.raises(ValidationError):
        AresP2ATargetProjectionV3.model_validate(projection)


def _with_digest(body: dict, field: str) -> dict:
    value = deepcopy(body)
    value[field] = sha256_digest(value)
    return value


def script_package_data() -> dict:
    return _with_digest(
        {
            "contract_version": "AresScriptPackage.v3",
            "master_sales_script": {
                "title": "XL",
                "cta": "확인해 보세요.",
                "beats": [
                    {
                        "beat_index": 0,
                        "text": "엄마, 이건 꼭 보세요.",
                        "caption": "꼭 보세요",
                    }
                ],
            },
            "voice_script": [{"beat_index": 0, "text": "엄마, 이건 꼭 보세요."}],
            "caption_script": [{"beat_index": 0, "text": "꼭 보세요"}],
            "pronunciation_overrides": {},
        },
        "package_digest",
    )


def semantic_plan_data(package_digest: str) -> dict:
    return _with_digest(
        {
            "contract_version": "AresSemanticBeatPlan.v3",
            "script_package_digest": package_digest,
            "beats": [
                {
                    "beat_index": 0,
                    "text": "엄마, 이건 꼭 보세요.",
                    "caption": "꼭 보세요",
                    "scene_intent": "엄마가 제품의 핵심 효용을 발견한다",
                    "role_intents": ["lead", "product"],
                }
            ],
        },
        "plan_digest",
    )


def bind_result_digest(body: dict) -> dict:
    partial = deepcopy(body)
    partial.pop("content_digest", None)
    placeholder = "sha256:" + "0" * 64
    constructed = AresCreateScriptResultV3.model_construct(
        **{
            **partial,
            "script_package": (
                ScriptPackageV3.model_validate(partial["script_package"])
                if partial.get("script_package") is not None
                else None
            ),
            "semantic_beat_plan": (
                SemanticBeatPlanV3.model_validate(partial["semantic_beat_plan"])
                if partial.get("semantic_beat_plan") is not None
                else None
            ),
            "quality_findings": tuple(
                AresQualityFindingV3.model_validate(item)
                for item in partial.get("quality_findings") or ()
            ),
            "provenance": AresGenerateProvenanceV3.model_validate(
                partial["provenance"]
            ),
            "usage": AresGenerateUsageV3.model_validate(partial.get("usage") or {}),
            "content_digest": placeholder,
        }
    )
    payload = constructed.model_dump(mode="json")
    payload["content_digest"] = canonical_contract_digest_v1(
        constructed, exclude={"content_digest"}
    )
    return payload


def ok_result_data() -> dict:
    package = script_package_data()
    request = AresCreateScriptRequestV3.model_validate(request_data())
    return bind_result_digest(
        {
            "contract_version": "AresCreateScriptResult.v3",
            "status": "ok",
            "script_package": package,
            "semantic_beat_plan": semantic_plan_data(package["package_digest"]),
            "quality_findings": [],
            "provenance": {
                "producer": "ares",
                "contract_version": "AresCreateScriptResult.v3",
                "request_content_digest": request_content_digest_v3(request),
            },
            "usage": {},
        }
    )


def test_v3_accepts_five_producer_issued_refs_and_full_scope():
    request = AresCreateScriptRequestV3.model_validate(request_data())
    assert request.scope.operation_id == "op-script-v3-1"
    assert request.authority.identity_ref.producer == "parzifal"
    assert request.authority.p2a_ref.producer == "karma"
    assert set(request.authority.accepted_p2a_receipt.source_output_digests) >= {
        request.authority.identity_ref.source_output_digest,
        request.authority.product_ref.source_output_digest,
        request.authority.evidence_ref.source_output_digest,
        request.authority.hook_ref.source_output_digest,
        request.authority.accepted_p2a_receipt.target_input[
            "command_source_output_digest"
        ],
    }
    assert request_content_digest_v3(request).startswith("sha256:")


@pytest.mark.parametrize(
    ("ref_name", "producer"),
    [
        ("identity_ref", "janus"),
        ("product_ref", "parzifal"),
        ("evidence_ref", "metis"),
        ("hook_ref", "artemis"),
        ("p2a_ref", "star"),
    ],
)
def test_v3_rejects_wrong_authority_owner(ref_name: str, producer: str):
    body = request_data()
    body["authority"][ref_name]["producer"] = producer
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV3.model_validate(body)


@pytest.mark.parametrize("field", ["workspace_id", "run_id"])
def test_v3_rejects_cross_scope_authority_ref(field: str):
    body = request_data()
    body["authority"]["product_ref"][field] = f"other-{field}"
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV3.model_validate(body)


def test_v3_rejects_cross_scope_p2a_receipt():
    body = request_data()
    body["authority"]["accepted_p2a_receipt"]["workspace_id"] = "other-workspace"
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV3.model_validate(body)


@pytest.mark.parametrize(
    ("ref_name", "payload_name", "payload_field", "tampered_value"),
    [
        ("identity_ref", "identity", "audience_lock", "다른 고객"),
        ("product_ref", "product_facts", "product_name", "다른 제품"),
        ("evidence_ref", "evidence_and_claims", "voc_quotes", ["새 VOC"]),
        ("hook_ref", "hook_directive", "hook_line", "새 훅"),
    ],
)
def test_v3_rejects_payload_digest_mismatch(
    ref_name: str,
    payload_name: str,
    payload_field: str,
    tampered_value: object,
):
    body = request_data()
    body[payload_name][payload_field] = tampered_value
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV3.model_validate(body)


def test_v3_rejects_native_artifact_digest_mismatch():
    body = request_data()
    body["authority"]["identity_ref"]["artifact_digest"] = sha256_digest(
        {"identity": "other-lock"}
    )
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV3.model_validate(body)


def test_v3_source_output_coverage_does_not_accept_artifact_digests():
    body = request_data()
    receipt_body = body["authority"]["accepted_p2a_receipt"]
    receipt_body["source_output_digests"] = [
        IDENTITY_DIGEST,
        PRODUCT_DIGEST,
        EVIDENCE_DIGEST,
        HOOK_DIGEST,
        STAR_COMMAND_OUTPUT_DIGEST,
    ]
    receipt = KarmaEdgeReceipt.model_validate(receipt_body)
    receipt_digest = karma_receipt_digest_v3(receipt)
    body["authority"]["p2a_ref"]["receipt_digest"] = receipt_digest
    body["authority"]["p2a_ref"]["source_output_digest"] = receipt_digest

    with pytest.raises(ValidationError, match="four authority outputs"):
        AresCreateScriptRequestV3.model_validate(body)


def test_v3_rejects_missing_star_command_source_output():
    body = request_data()
    receipt_body = body["authority"]["accepted_p2a_receipt"]
    receipt_body["source_output_digests"].remove(STAR_COMMAND_OUTPUT_DIGEST)
    receipt = KarmaEdgeReceipt.model_validate(receipt_body)
    receipt_digest = karma_receipt_digest_v3(receipt)
    body["authority"]["p2a_ref"]["receipt_digest"] = receipt_digest
    body["authority"]["p2a_ref"]["source_output_digest"] = receipt_digest

    with pytest.raises(ValidationError, match="Star command output"):
        AresCreateScriptRequestV3.model_validate(body)


def test_v3_rejects_p2a_receipt_digest_mismatch():
    body = request_data()
    body["authority"]["p2a_ref"]["receipt_digest"] = sha256_digest({"fake": True})
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV3.model_validate(body)


def test_v3_keeps_karma_output_and_receipt_digests_distinct():
    request = AresCreateScriptRequestV3.model_validate(request_data())

    assert request.authority.p2a_ref.source_output_digest == KARMA_OUTPUT_DIGEST
    assert (
        request.authority.p2a_ref.source_output_digest
        != request.authority.p2a_ref.receipt_digest
    )


def test_v3_rejects_generic_authority_receipt_digest_drift():
    body = request_data()
    body["authority"]["identity_ref"]["receipt_id"] = "different-receipt-id"
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV3.model_validate(body)


def test_v3_authority_receipt_subject_rejects_source_output_digest_drift():
    ref = deepcopy(request_data()["authority"]["identity_ref"])
    ref["source_output_digest"] = sha256_digest({"forged": "producer-output"})

    with pytest.raises(
        ValidationError,
        match="canonical authority reference",
    ):
        AresAuthorityArtifactRefV3.model_validate(ref)


def test_v3_freezes_embedded_karma_target_projection():
    request = AresCreateScriptRequestV3.model_validate(request_data())
    before = request_content_digest_v3(request)
    target_input = request.authority.accepted_p2a_receipt.target_input
    assert target_input is not None
    with pytest.raises(TypeError):
        target_input["scope"] = {"workspace_id": "replayed"}
    nested_scope = target_input["scope"]
    with pytest.raises(TypeError):
        nested_scope["operation_id"] = "replayed"
    assert request_content_digest_v3(request) == before
    assert request.authority.p2a_ref.receipt_digest == (
        karma_receipt_digest_v3(request.authority.accepted_p2a_receipt)
    )
    with pytest.raises(TypeError):
        dict.__setitem__(target_input, "scope", {"workspace_id": "bypass"})
    assert request_content_digest_v3(request) == before


def test_v3_rejects_p2a_projection_replay_across_operation():
    body = request_data()
    body["scope"]["operation_id"] = "op-script-v3-replayed"
    body["scope"]["idempotency_key"] = "ares-script-v3:replayed"
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV3.model_validate(body)


def test_v3_rejects_fully_rehashed_incomplete_p2a_projection():
    body = request_data()
    receipt_body = body["authority"]["accepted_p2a_receipt"]
    target_input = deepcopy(receipt_body["target_input"])
    del target_input["hook_ref"]
    target_digest = sha256_digest(target_input)
    receipt_body["target_input"] = target_input
    receipt_body["target_input_digest"] = target_digest
    body["authority"]["p2a_ref"]["artifact_digest"] = target_digest
    body["authority"]["p2a_ref"]["payload_digest"] = target_digest
    receipt = KarmaEdgeReceipt.model_validate(receipt_body)
    receipt_digest = karma_receipt_digest_v3(receipt)
    body["authority"]["p2a_ref"]["receipt_digest"] = receipt_digest
    body["authority"]["p2a_ref"]["source_output_digest"] = receipt_digest
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV3.model_validate(body)


@pytest.mark.parametrize(
    ("field", "value"),
    [("n_beats", 3), ("human_instruction", "다른 지시")],
)
def test_v3_rejects_creative_constraint_replay(field: str, value: object):
    body = request_data()
    body["creative_constraints"][field] = value
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV3.model_validate(body)


@pytest.mark.parametrize("field", ["receipt_id", "operation_id", "idempotency_key"])
def test_v3_rejects_blank_ids(field: str):
    body = request_data()
    if field == "receipt_id":
        body["authority"]["identity_ref"][field] = "  "
    else:
        body["scope"][field] = "  "
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV3.model_validate(body)


def test_v3_request_and_nested_refs_are_frozen_and_extra_forbid():
    request = AresCreateScriptRequestV3.model_validate(request_data())
    with pytest.raises(ValidationError):
        request.scope.operation_id = "other"
    body = request_data()
    body["authority"]["identity_ref"]["minted_by_star"] = True
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV3.model_validate(body)


def test_v3_result_contains_semantic_beats_only():
    result = AresCreateScriptResultV3.model_validate(ok_result_data())
    assert result.semantic_beat_plan is not None
    beat = result.semantic_beat_plan.beats[0]
    assert beat.scene_intent
    dumped = beat.model_dump()
    assert {"shot", "camera", "camera_mode", "render_mode"}.isdisjoint(dumped)


@pytest.mark.parametrize("forbidden", ["shot", "camera", "camera_mode", "render_mode"])
def test_v3_semantic_beat_rejects_athena_owned_fields(forbidden: str):
    body = semantic_plan_data(script_package_data()["package_digest"])["beats"][0]
    body[forbidden] = "handheld"
    with pytest.raises(ValidationError):
        AresSemanticBeatV3.model_validate(body)


def test_v3_result_rejects_visual_or_dispatch_state():
    body = ok_result_data()
    body["render_job_id"] = "render-1"
    with pytest.raises(ValidationError):
        AresCreateScriptResultV3.model_validate(body)


@pytest.mark.parametrize(
    "forbidden",
    [
        "shot",
        "camera_mode",
        "cameraAngle",
        "shot_plan",
        "render_mode",
        "production_plan",
        "visual_prompt",
        "persona_cast",
        "cast",
        "scene_direction",
        "visual_context",
    ],
)
def test_v3_script_package_rejects_nested_visual_plan_keys(forbidden: str):
    body = script_package_data()
    body["master_sales_script"]["beats"] = [{forbidden: "handheld"}]
    body = _with_digest(
        {key: value for key, value in body.items() if key != "package_digest"},
        "package_digest",
    )
    with pytest.raises(ValidationError):
        ScriptPackageV3.model_validate(body)


@pytest.mark.parametrize(
    "invalid",
    [
        float("nan"),
        float("inf"),
        1.5,
        9_007_199_254_740_992,
        object(),
    ],
)
def test_v3_script_package_rejects_noncanonical_json(invalid: object):
    body = script_package_data()
    body["master_sales_script"]["invalid"] = invalid
    with pytest.raises((TypeError, ValidationError, ValueError)):
        ScriptPackageV3.model_validate(body)


@pytest.mark.parametrize(
    ("field", "value"),
    [("text", "다른 대사"), ("caption", "다른 자막")],
)
def test_v3_script_package_rejects_master_segment_drift(field: str, value: str):
    body = script_package_data()
    body["master_sales_script"]["beats"][0][field] = value
    body = _with_digest(
        {key: value for key, value in body.items() if key != "package_digest"},
        "package_digest",
    )
    with pytest.raises(ValidationError):
        ScriptPackageV3.model_validate(body)


def test_v3_result_rejects_semantic_package_text_or_caption_drift():
    body = ok_result_data()
    plan = body["semantic_beat_plan"]
    plan["beats"][0]["caption"] = "다른 자막"
    plan = _with_digest(
        {key: value for key, value in plan.items() if key != "plan_digest"},
        "plan_digest",
    )
    body["semantic_beat_plan"] = plan
    body = bind_result_digest(body)
    with pytest.raises(ValidationError):
        AresCreateScriptResultV3.model_validate(body)


def test_v3_nonblank_fields_preserve_surrounding_whitespace():
    scope = AresRequestScopeV3.model_validate(
        {
            "workspace_id": " ws ",
            "run_id": " run ",
            "operation_id": " op-script-v3-1 ",
            "idempotency_key": " key ",
        }
    )
    assert scope.operation_id == " op-script-v3-1 "

    beat = AresSemanticBeatV3.model_validate(
        {
            "beat_index": 0,
            "text": " 대사 ",
            "caption": " 자막 ",
            "scene_intent": " 장면 의도 ",
            "role_intents": [" lead "],
        }
    )
    assert beat.text == " 대사 "
    assert beat.role_intents == (" lead ",)


def test_v3_produced_at_requires_valid_utc_calendar_value():
    with pytest.raises(ValidationError):
        AresGenerateProvenanceV3.model_validate(
            {
                "producer": "ares",
                "contract_version": "AresCreateScriptResult.v3",
                "request_content_digest": sha256_digest({"request": 1}),
                "produced_at": "2026-02-30T00:00:00Z",
            }
        )


def test_v3_blocked_result_content_digest_python_ts_parity_vector():
    payload = {
        "contract_version": "AresCreateScriptResult.v3",
        "status": "blocked",
        "script_package": None,
        "semantic_beat_plan": None,
        "quality_findings": [],
        "provenance": {
            "producer": "ares",
            "contract_version": "AresCreateScriptResult.v3",
            "request_content_digest": sha256_digest({"request": 1}),
            "model_id": None,
            "prompt_digest": None,
            "produced_at": None,
        },
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost_cents": 0,
            "model_id": None,
        },
        "block_reason": "upstream authority missing",
    }
    content_digest = sha256_digest(payload)
    assert content_digest == (
        "sha256:c202627e893f27d9da7931b9db969255601c2a01cf7144dc503f5ec24ecd1419"
    )
    AresCreateScriptResultV3.model_validate(
        {**payload, "content_digest": content_digest}
    )


def test_v3_schema_digests_are_stable_and_distinct():
    request_digest = ares_create_script_request_v3_schema_digest()
    result_digest = ares_create_script_result_v3_schema_digest()
    # These are also asserted by the TypeScript mirror test.
    assert request_digest == (
        "sha256:e3043b68c15ecdc9c560912067c8b7c6b7f25cdce3bce6dfb0facf20204be8b6"
    )
    assert result_digest == (
        "sha256:72a50c6d3305b158441328e024d630a9cdd0fe3f974d76bce7ab80d9d52c8de0"
    )
    assert ares_p2a_target_projection_v3_schema_digest() == (
        "sha256:21eb7a2cc977d1aedd61885f90ddbd213809c65a061c04b6fb6793b27817d687"
    )
    assert request_digest != result_digest


def test_v3_projection_schema_digest_binds_nested_structure_and_invariants():
    descriptor = ares_p2a_target_projection_v3_schema_descriptor()
    baseline = sha256_digest(descriptor)
    drifted = deepcopy(descriptor)
    drifted["properties"]["creative_constraints"]["properties"]["n_beats"][
        "maximum"
    ] = 65
    assert sha256_digest(drifted) != baseline
    drifted = deepcopy(descriptor)
    drifted["invariants"].remove(
        "source_output_digests_cover_four_authority_outputs_and_command"
    )
    assert sha256_digest(drifted) != baseline
