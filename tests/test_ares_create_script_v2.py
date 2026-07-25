"""Ares pure generate contract V2 — authority required, extra forbid, digests bind."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    AresCreateScriptRequestV2,
    AresCreateScriptResultV2,
    BeatPlanV2,
    ScriptPackageV2,
    ares_create_script_request_schema_digest,
    ares_create_script_result_schema_digest,
    canonical_contract_digest_v1,
    request_content_digest,
    sha256_digest,
)
from hiob_contracts.ares_create_script_v2 import (
    AresAuthorityV2,
    AresCreativeConstraintsV2,
    AresEvidenceAndClaimsSealedV2,
    AresGenerateProvenanceV2,
    AresGenerateUsageV2,
    AresHookDirectiveV2,
    AresIdentitySealedV2,
    AresProductFactsSealedV2,
    AresQualityFindingV2,
)
from hiob_contracts.factory import ContractRef, KarmaEdgeReceipt, MapperRef


IDENTITY_DIGEST = sha256_digest({"identity": "lead-v3"})
PRODUCT_DIGEST = sha256_digest({"product": "xl-serum"})
EVIDENCE_DIGEST = sha256_digest({"evidence": "bundle-1"})
HOOK_DIGEST = sha256_digest({"hook": "gossip-v1"})


def _receipt(*, decision: str = "accepted", edge_id: str = "p2a") -> dict:
    target_input = {
        "brand_slug": "viewok",
        "protagonist_name": "정원이",
        "target_pain": "수영 공포",
    }
    body: dict = {
        "receipt_id": "rcpt-p2a-v2-1",
        "edge_id": edge_id,
        "run_id": "run-v2-1",
        "factory_revision": 1,
        "workspace_id": "ws-v2-1",
        "source_output_digests": (IDENTITY_DIGEST,),
        "target_contract": {
            "name": "AresScriptInput",
            "version": "v1",
            "schema_digest": sha256_digest({"schema": "ares_script_input.v1"}),
        },
        "decision": decision,
        "mapper": {
            "planet": "karma",
            "node_id": "karma.edge.refine",
            "revision": "r1",
            "policy_digest": sha256_digest({"policy": "p2a.v1"}),
        },
        "created_at": "2026-07-25T00:00:00Z",
    }
    if decision == "accepted":
        body["target_input"] = target_input
        body["target_input_digest"] = sha256_digest(target_input)
    return body


def _identity() -> dict:
    return {
        "identity_lock_digest": IDENTITY_DIGEST,
        "cast_sheet_digest": sha256_digest({"cast": "sheet-1"}),
        "speakers": [
            {
                "role": "lead",
                "subject_id": "mom",
                "display_name": "정원이",
                "voice_id": "tc_voice_1",
            }
        ],
        "locale": "ko",
        "audience_lock": "30대 엄마",
    }


def _product() -> dict:
    return {
        "product_truth_digest": PRODUCT_DIGEST,
        "brand_slug": "viewok",
        "brand_display_name": "뷰옥",
        "product_name": "XL 세럼",
        "listing_slug": "xl-serum",
        "listing_pitch": "한 번에 이해되는 세럼",
        "price_text": "39,000원",
        "usp_lines": ["빠른 흡수", "비건 포뮬러"],
        "facts_block": {"sku": "XL-01"},
    }


def _evidence() -> dict:
    return {
        "evidence_bundle_digest": EVIDENCE_DIGEST,
        "claims": [
            {
                "claim_id": "c1",
                "text": "빠른 흡수",
                "claim_kind": "product_fact",
                "provenance": {
                    "source_url": "https://example.com/pdp",
                    "quote_span": "빠르게 흡수됩니다",
                    "observed_at": "2026-07-25T00:00:00Z",
                },
            }
        ],
        "voc_quotes": ["물에 들어가면 무서워요"],
        "allowed_claim_ids": ["c1"],
    }


def _hook() -> dict:
    return {
        "directive_digest": HOOK_DIGEST,
        "archetype_id": "gossip_reveal",
        "hook_line": "엄마, 이건 꼭 보세요.",
        "hook_register": "가십",
    }


def _constraints() -> dict:
    return {
        "n_beats": 2,
        "format_mode": "ugc",
        "style_mode": "photoreal",
        "goal": "conversion",
        "human_instruction": "",
        "banned_phrases": ["100% 완치"],
    }


def request_data() -> dict:
    return {
        "contract_version": "AresCreateScriptRequest.v2",
        "authority": {
            "accepted_p2a_receipt": _receipt(),
            "identity_lock_digest": IDENTITY_DIGEST,
            "product_truth_digest": PRODUCT_DIGEST,
        },
        "identity": _identity(),
        "product_facts": _product(),
        "evidence_and_claims": _evidence(),
        "hook_directive": _hook(),
        "creative_constraints": _constraints(),
    }


def master_script() -> dict:
    return {
        "title": "엄마를 위한 XL",
        "hook": {"line": "엄마, 이건 꼭 보세요."},
        "cta": {"line": "지금 확인해 보세요."},
        "beats": [
            {"beat_index": 0, "text": "엄마, 이건 꼭 보세요."},
            {"beat_index": 1, "text": "지금 확인해 보세요."},
        ],
    }


def _with_digest(body: dict, field: str) -> dict:
    value = deepcopy(body)
    value[field] = sha256_digest(value)
    return value


def script_package_data() -> dict:
    return _with_digest(
        {
            "contract_version": "AresScriptPackage.v2",
            "master_sales_script": master_script(),
            "voice_script": [
                {"beat_index": 0, "text": "엄마, 이건 꼭 보세요."},
                {"beat_index": 1, "text": "지금 확인해 보세요."},
            ],
            "caption_script": [
                {"beat_index": 0, "text": "엄마, 이건 꼭 보세요."},
                {"beat_index": 1, "text": "지금 확인"},
            ],
            "pronunciation_overrides": {"XL": "엑스엘"},
        },
        "package_digest",
    )


def beat_plan_data(package_digest: str) -> dict:
    return _with_digest(
        {
            "contract_version": "AresBeatPlan.v2",
            "script_package_digest": package_digest,
            "beats": [
                {
                    "beat_index": 0,
                    "text": "엄마, 이건 꼭 보세요.",
                    "caption": "엄마, 이건 꼭 보세요.",
                    "scene_direction": {
                        "shot": "MCU",
                        "subject": "엄마",
                        "setting": "주방",
                        "overlay": "꼭 보세요",
                    },
                },
                {
                    "beat_index": 1,
                    "text": "지금 확인해 보세요.",
                    "caption": "지금 확인",
                    "scene_direction": {
                        "shot": "CU",
                        "subject": "제품",
                        "setting": "테이블",
                        "overlay": "지금 확인",
                    },
                },
            ],
            "beat_role_intents": [
                {
                    "beat_index": 0,
                    "roles": ["lead"],
                    "on_camera": True,
                    "notes": "",
                },
                {
                    "beat_index": 1,
                    "roles": ["product"],
                    "on_camera": True,
                    "notes": "",
                },
            ],
        },
        "plan_digest",
    )


def _bind_result_digest(partial: dict) -> dict:
    """Bind content_digest using the same serializer path as model validation."""
    body = deepcopy(partial)
    body.pop("content_digest", None)
    placeholder = "sha256:" + ("0" * 64)
    constructed = AresCreateScriptResultV2.model_construct(
        **{
            **body,
            "script_package": (
                ScriptPackageV2.model_validate(body["script_package"])
                if body.get("script_package") is not None
                else None
            ),
            "beat_plan": (
                BeatPlanV2.model_validate(body["beat_plan"])
                if body.get("beat_plan") is not None
                else None
            ),
            "quality_findings": tuple(
                AresQualityFindingV2.model_validate(item)
                for item in body.get("quality_findings") or ()
            ),
            "provenance": AresGenerateProvenanceV2.model_validate(body["provenance"]),
            "usage": AresGenerateUsageV2.model_validate(body.get("usage") or {}),
            "content_digest": placeholder,
        }
    )
    digest = canonical_contract_digest_v1(
        constructed, exclude={"content_digest"}
    )
    payload = constructed.model_dump(mode="json")
    payload["content_digest"] = digest
    return payload


def ok_result_data() -> dict:
    package = script_package_data()
    plan = beat_plan_data(package["package_digest"])
    req = AresCreateScriptRequestV2.model_validate(request_data())
    req_digest = request_content_digest(req)
    body = {
        "contract_version": "AresCreateScriptResult.v2",
        "status": "ok",
        "script_package": package,
        "beat_plan": plan,
        "quality_findings": [
            {
                "code": "audience_lock_ok",
                "severity": "info",
                "message": "audience lock present",
                "gate": "audience_lock",
            }
        ],
        "provenance": {
            "producer": "ares",
            "contract_version": "AresCreateScriptResult.v2",
            "request_content_digest": req_digest,
            "model_id": "qwen3.6-flash",
            "produced_at": "2026-07-25T12:00:00Z",
        },
        "usage": {
            "input_tokens": 100,
            "output_tokens": 200,
            "total_tokens": 300,
            "cost_cents": 1,
            "model_id": "qwen3.6-flash",
        },
    }
    return _bind_result_digest(body)


# ── Request ────────────────────────────────────────────────────────────────


def test_request_accepts_sealed_authority_bundle():
    req = AresCreateScriptRequestV2.model_validate(request_data())
    assert req.contract_version == "AresCreateScriptRequest.v2"
    assert req.authority.identity_lock_digest == IDENTITY_DIGEST
    assert req.creative_constraints.n_beats == 2
    assert request_content_digest(req).startswith("sha256:")


def test_request_rejects_extra_fields():
    data = request_data()
    data["job_status"] = "running"
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV2.model_validate(data)


def test_request_rejects_missing_authority():
    data = request_data()
    del data["authority"]
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV2.model_validate(data)


def test_request_rejects_blocked_receipt():
    data = request_data()
    data["authority"]["accepted_p2a_receipt"] = _receipt(decision="blocked")
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV2.model_validate(data)


def test_request_rejects_wrong_edge_id():
    data = request_data()
    data["authority"]["accepted_p2a_receipt"] = _receipt(edge_id="j2a")
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV2.model_validate(data)


def test_request_rejects_identity_digest_mismatch():
    data = request_data()
    data["identity"]["identity_lock_digest"] = sha256_digest({"other": True})
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV2.model_validate(data)


def test_request_rejects_product_digest_mismatch():
    data = request_data()
    data["product_facts"]["product_truth_digest"] = sha256_digest({"other": True})
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV2.model_validate(data)


def test_request_rejects_identity_not_in_receipt_sources():
    data = request_data()
    # receipt still has IDENTITY_DIGEST source; swap authority digest to other
    other = sha256_digest({"identity": "other"})
    data["authority"]["identity_lock_digest"] = other
    data["identity"]["identity_lock_digest"] = other
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV2.model_validate(data)


def test_request_rejects_empty_speakers():
    data = request_data()
    data["identity"]["speakers"] = []
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV2.model_validate(data)


def test_request_rejects_claim_not_in_allowlist():
    data = request_data()
    data["evidence_and_claims"]["allowed_claim_ids"] = ["other"]
    with pytest.raises(ValidationError):
        AresCreateScriptRequestV2.model_validate(data)


# ── Package / plan ─────────────────────────────────────────────────────────


def test_script_package_v2_has_no_db_ids():
    package = ScriptPackageV2.model_validate(script_package_data())
    dumped = package.model_dump()
    assert "candidate_id" not in dumped
    assert "revision_id" not in dumped
    assert "workspace_id" not in dumped
    assert package.package_digest.startswith("sha256:")


def test_script_package_v2_rejects_digest_tamper():
    data = script_package_data()
    data["package_digest"] = sha256_digest({"tampered": True})
    with pytest.raises(ValidationError):
        ScriptPackageV2.model_validate(data)


def test_beat_plan_v2_binds_to_package_digest():
    package = ScriptPackageV2.model_validate(script_package_data())
    plan = BeatPlanV2.model_validate(beat_plan_data(package.package_digest))
    assert plan.script_package_digest == package.package_digest
    assert "production_plan" not in plan.model_dump()


def test_beat_plan_v2_rejects_shot_camera_extra():
    package = ScriptPackageV2.model_validate(script_package_data())
    data = beat_plan_data(package.package_digest)
    data["camera_mode"] = "handheld"
    with pytest.raises(ValidationError):
        BeatPlanV2.model_validate(data)


# ── Result ─────────────────────────────────────────────────────────────────


def test_ok_result_requires_package_and_plan():
    result = AresCreateScriptResultV2.model_validate(ok_result_data())
    assert result.status == "ok"
    assert result.script_package is not None
    assert result.beat_plan is not None
    assert result.content_digest.startswith("sha256:")


def test_ok_result_rejects_package_plan_digest_mismatch():
    data = ok_result_data()
    other = script_package_data()
    other["voice_script"][0]["text"] = "다른 대사입니다."
    other.pop("package_digest", None)
    other = _with_digest(other, "package_digest")
    data["script_package"] = other
    # rebind content_digest so only package↔plan cross-bind fails
    data = _bind_result_digest(data)
    with pytest.raises(ValidationError):
        AresCreateScriptResultV2.model_validate(data)


def test_blocked_result_requires_reason_and_forbids_package():
    req = AresCreateScriptRequestV2.model_validate(request_data())
    body = {
        "contract_version": "AresCreateScriptResult.v2",
        "status": "blocked",
        "script_package": None,
        "beat_plan": None,
        "quality_findings": [
            {
                "code": "authority_missing_claim",
                "severity": "error",
                "message": "required claim missing",
            }
        ],
        "provenance": {
            "producer": "ares",
            "request_content_digest": request_content_digest(req),
        },
        "usage": {},
        "block_reason": "evidence_and_claims incomplete",
    }
    result = AresCreateScriptResultV2.model_validate(_bind_result_digest(body))
    assert result.status == "blocked"
    assert result.script_package is None


def test_blocked_result_rejects_package_payload():
    req = AresCreateScriptRequestV2.model_validate(request_data())
    package = script_package_data()
    body = {
        "contract_version": "AresCreateScriptResult.v2",
        "status": "blocked",
        "script_package": package,
        "beat_plan": beat_plan_data(package["package_digest"]),
        "quality_findings": [],
        "provenance": {
            "producer": "ares",
            "request_content_digest": request_content_digest(req),
        },
        "usage": {},
        "block_reason": "should not include package",
    }
    # Even with a correctly shaped digest, status rules must reject package.
    with pytest.raises(ValidationError):
        AresCreateScriptResultV2.model_validate(_bind_result_digest(body))


def test_result_rejects_job_status_field():
    data = ok_result_data()
    data["job_status"] = "succeeded"
    with pytest.raises(ValidationError):
        AresCreateScriptResultV2.model_validate(data)


def test_schema_digests_stable_and_exported():
    d1 = ares_create_script_request_schema_digest()
    d2 = ares_create_script_result_schema_digest()
    assert d1.startswith("sha256:")
    assert d2.startswith("sha256:")
    assert d1 == ares_create_script_request_schema_digest()
    assert d2 == ares_create_script_result_schema_digest()
    assert d1 != d2


def test_nested_sections_parse_standalone():
    AresAuthorityV2.model_validate(request_data()["authority"])
    AresIdentitySealedV2.model_validate(_identity())
    AresProductFactsSealedV2.model_validate(_product())
    AresEvidenceAndClaimsSealedV2.model_validate(_evidence())
    AresHookDirectiveV2.model_validate(_hook())
    AresCreativeConstraintsV2.model_validate(_constraints())
    AresGenerateProvenanceV2.model_validate(
        {
            "request_content_digest": IDENTITY_DIGEST,
        }
    )


def test_receipt_object_roundtrip_via_model():
    """KarmaEdgeReceipt model accepts dict and remains frozen in authority."""
    receipt = KarmaEdgeReceipt.model_validate(_receipt())
    assert receipt.decision == "accepted"
    assert ContractRef.model_validate(
        receipt.target_contract.model_dump()
    ).name == "AresScriptInput"
    assert MapperRef.model_validate(receipt.mapper.model_dump()).planet == "karma"
