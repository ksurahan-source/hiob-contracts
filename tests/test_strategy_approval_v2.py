from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    ParzifalIdentityBindingV1,
    StrategyApprovalBundleV1,
    StrategyApprovalReceiptV2,
    canonical_contract_digest_v1,
    derive_parzifal_identity_binding_id_v1,
    validate_parzifal_identity_binding_v1,
    validate_strategy_approval_evidence_v2,
)


RUN_ID = "11111111-1111-4111-8111-111111111111"
WORKSPACE_ID = "22222222-2222-4222-8222-222222222222"
APPROVAL_ID = "33333333-3333-4333-8333-333333333333"
CLAIM_ID = "44444444-4444-4444-8444-444444444444"
SOURCE_DIGEST = "sha256:" + "a" * 64
TARGET_PROFILE = {"persona": {"pain": "반복 실패", "role": "창업자"}}
MASTER_SHEET = {"status": "identity_sealed", "identity": {"name": "대표"}}
CAST_SHEETS = {"status": "sealed", "lead": {"persona_id": "target"}}


def bundle_data() -> dict:
    return {
        "contract_version": "StrategyApprovalBundle.v1",
        "run_id": RUN_ID,
        "workspace_id": WORKSPACE_ID,
        "strategy": {
            "audience": "창업자",
            "beats": [{"index": 0, "claim": "빠른 검증"}],
        },
        "brief_patch": {"strategy_full": {"audience": "창업자"}},
        "attributes_patch": {
            "strategy_status": "approved",
            "identity_source": "parzifal",
            "target_profile": TARGET_PROFILE,
            "parzifal_master_sheet": MASTER_SHEET,
            "parzifal_cast_sheets": CAST_SHEETS,
        },
    }


def receipt_data(bundle: dict | None = None) -> dict:
    bundle = bundle or bundle_data()
    payload = {
        "contract_version": "StrategyApprovalReceipt.v2",
        "approval_id": APPROVAL_ID,
        "claim_id": CLAIM_ID,
        "run_id": RUN_ID,
        "workspace_id": WORKSPACE_ID,
        "strategy_input_revision": 0,
        "approval_revision": 1,
        "source_digest": SOURCE_DIGEST,
        "strategy_digest": canonical_contract_digest_v1(bundle["strategy"]),
        "bundle_digest": canonical_contract_digest_v1(bundle),
        "approved_by_account_id": "66666666-6666-4666-8666-666666666666",
        "approved_at": "2026-07-24T01:02:03.123456Z",
    }
    payload["receipt_digest"] = canonical_contract_digest_v1(payload)
    return payload


def binding_data(bundle: dict | None = None, receipt: dict | None = None) -> dict:
    bundle = bundle or bundle_data()
    receipt = receipt or receipt_data(bundle)
    target_profile = bundle["attributes_patch"]["target_profile"]
    master_sheet = bundle["attributes_patch"]["parzifal_master_sheet"]
    cast_sheets = bundle["attributes_patch"]["parzifal_cast_sheets"]
    payload = {
        "contract_version": "ParzifalIdentityBinding.v1",
        "binding_id": derive_parzifal_identity_binding_id_v1(
            receipt["receipt_digest"]
        ),
        "binding_revision": 1,
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "strategy_approval_id": APPROVAL_ID,
        "strategy_digest": receipt["strategy_digest"],
        "strategy_bundle_digest": receipt["bundle_digest"],
        "strategy_receipt_digest": receipt["receipt_digest"],
        "target_profile": target_profile,
        "target_profile_digest": canonical_contract_digest_v1(target_profile),
        "master_sheet": master_sheet,
        "master_sheet_digest": canonical_contract_digest_v1(master_sheet),
        "cast_sheets": cast_sheets,
        "cast_sheets_digest": canonical_contract_digest_v1(cast_sheets),
        "identity_source": "parzifal",
        "source_node": "parzifal.identity.bind",
        "source_revision": "parzifal.identity.bind.v1",
        "created_at": receipt["approved_at"],
        "created_by_account_id": receipt["approved_by_account_id"],
    }
    payload["binding_digest"] = canonical_contract_digest_v1(payload)
    return payload


def test_python_golden_digests_and_exports_are_stable():
    bundle = StrategyApprovalBundleV1.model_validate(bundle_data())
    receipt = StrategyApprovalReceiptV2.model_validate(receipt_data())
    binding = ParzifalIdentityBindingV1.model_validate(binding_data())

    assert bundle.strategy_digest == (
        "sha256:663d4eabb6338116bfb922a00a517b83bc2dadb6e99ef58b967d061d3d3fc9ca"
    )
    assert bundle.bundle_digest == (
            "sha256:8d9e3a6766f5bd9e3244891aaf3f0b626121b8f76242718b875d9c0f45fc6355"
    )
    assert receipt.receipt_digest == (
            "sha256:4cdeb2ee6af0f7ddc2cdf7f1ddf28c77bad29392252031793086e30e69dc82e7"
    )
    assert binding.binding_digest == (
            "sha256:885903ee232604a8eb69afbd6f90e5a03ae8c6557a1464941884ccfab686a1d9"
    )


def test_evidence_and_identity_binding_validate_exact_scope_and_digests():
    bundle = bundle_data()
    receipt = receipt_data(bundle)
    parsed_bundle, parsed_receipt = validate_strategy_approval_evidence_v2(
        bundle, receipt
    )
    parsed_binding = validate_parzifal_identity_binding_v1(
        binding_data(bundle, receipt),
        bundle=parsed_bundle,
        receipt=parsed_receipt,
    )
    assert parsed_binding.strategy_approval_id == parsed_receipt.approval_id
    assert parsed_binding.strategy_receipt_digest == parsed_receipt.receipt_digest


def test_contracts_are_deeply_immutable_and_forbid_extras():
    bundle = StrategyApprovalBundleV1.model_validate(bundle_data())
    with pytest.raises(TypeError):
        bundle.strategy["audience"] = "tamper"  # type: ignore[index]
    with pytest.raises(ValidationError):
        StrategyApprovalBundleV1.model_validate({**bundle_data(), "extra": True})

    binding = binding_data()
    binding["extra"] = True
    with pytest.raises(ValidationError):
        ParzifalIdentityBindingV1.model_validate(binding)


@pytest.mark.parametrize(
    ("mutator", "model"),
    [
        (
            lambda value: value["strategy"].update({"audience": "다른 사람"}),
            "bundle",
        ),
        (
            lambda value: value.update({"receipt_digest": "sha256:" + "0" * 64}),
            "receipt",
        ),
        (
            lambda value: value["target_profile"].update({"persona": {"pain": "변조"}}),
            "binding",
        ),
        (
            lambda value: value.update({"binding_digest": "sha256:" + "0" * 64}),
            "binding",
        ),
    ],
)
def test_tampering_is_rejected(mutator, model):
    value = {
        "bundle": bundle_data,
        "receipt": receipt_data,
        "binding": binding_data,
    }[model]()
    mutator(value)
    target = {
        "bundle": StrategyApprovalBundleV1,
        "receipt": StrategyApprovalReceiptV2,
        "binding": ParzifalIdentityBindingV1,
    }[model]
    if model == "bundle":
        with pytest.raises(ValueError):
            validate_strategy_approval_evidence_v2(value, receipt_data())
    else:
        with pytest.raises(ValidationError):
            target.model_validate(value)


def test_cross_scope_and_forged_evidence_are_rejected():
    bundle = bundle_data()
    receipt = receipt_data(bundle)
    foreign = deepcopy(receipt)
    foreign["run_id"] = "77777777-7777-4777-8777-777777777777"
    foreign["receipt_digest"] = canonical_contract_digest_v1(
        {key: value for key, value in foreign.items() if key != "receipt_digest"}
    )
    with pytest.raises(ValueError, match="run_id scope mismatch"):
        validate_strategy_approval_evidence_v2(bundle, foreign)

    forged_binding = binding_data(bundle, receipt)
    forged_binding["strategy_approval_id"] = (
        "88888888-8888-4888-8888-888888888888"
    )
    forged_binding["binding_digest"] = canonical_contract_digest_v1(
        {
            key: value
            for key, value in forged_binding.items()
            if key != "binding_digest"
        }
    )
    with pytest.raises(ValueError, match="strategy_approval_id"):
        validate_parzifal_identity_binding_v1(
            forged_binding, bundle=bundle, receipt=receipt
        )

    forged_snapshot = binding_data(bundle, receipt)
    forged_snapshot["target_profile"] = {"persona": {"pain": "공격자"}}
    forged_snapshot["target_profile_digest"] = canonical_contract_digest_v1(
        forged_snapshot["target_profile"]
    )
    forged_snapshot["binding_digest"] = canonical_contract_digest_v1(
        {
            key: value
            for key, value in forged_snapshot.items()
            if key != "binding_digest"
        }
    )
    with pytest.raises(ValueError, match="does not match approved bundle"):
        validate_parzifal_identity_binding_v1(
            forged_snapshot, bundle=bundle, receipt=receipt
        )

    forged_metadata = binding_data(bundle, receipt)
    forged_metadata["created_by_account_id"] = (
        "99999999-9999-4999-8999-999999999999"
    )
    forged_metadata["binding_digest"] = canonical_contract_digest_v1(
        {
            key: value
            for key, value in forged_metadata.items()
            if key != "binding_digest"
        }
    )
    with pytest.raises(ValueError, match="created_by_account_id"):
        validate_parzifal_identity_binding_v1(
            forged_metadata, bundle=bundle, receipt=receipt
        )

    with pytest.raises(ValueError, match="lowercase sha256"):
        derive_parzifal_identity_binding_id_v1("SHA256:" + "0" * 64)


def test_existing_model_instances_are_revalidated_at_public_boundaries():
    bundle = StrategyApprovalBundleV1.model_construct(**bundle_data())
    forged_receipt = StrategyApprovalReceiptV2.model_construct(
        **{
            **receipt_data(),
            "approval_id": "bad",
            "strategy_input_revision": -1,
            "receipt_digest": "sha256:" + "0" * 64,
        }
    )
    with pytest.raises(ValidationError):
        validate_strategy_approval_evidence_v2(bundle, forged_receipt)

    valid_bundle = StrategyApprovalBundleV1.model_validate(bundle_data())
    valid_receipt = StrategyApprovalReceiptV2.model_validate(receipt_data())
    forged_binding = ParzifalIdentityBindingV1.model_construct(
        **{
            **binding_data(),
            "contract_version": "Wrong.v1",
            "identity_source": "studio_fallback",
            "binding_digest": "sha256:" + "0" * 64,
        }
    )
    with pytest.raises(ValidationError):
        validate_parzifal_identity_binding_v1(
            forged_binding,
            bundle=valid_bundle,
            receipt=valid_receipt,
        )


def test_unpaired_unicode_in_json_keys_fails_during_parse():
    payload = bundle_data()
    payload["strategy"] = {"\ud800": 1}
    with pytest.raises(ValidationError, match="Unicode surrogate key"):
        StrategyApprovalBundleV1.model_validate(payload)


def test_cyclic_json_and_non_uuid_approver_fail_closed():
    payload = bundle_data()
    cyclic: dict = {}
    cyclic["self"] = cyclic
    payload["strategy"] = cyclic
    with pytest.raises(ValidationError, match="cyclic non-JSON"):
        StrategyApprovalBundleV1.model_validate(payload)

    receipt = receipt_data()
    receipt["approved_by_account_id"] = "not-a-uuid"
    receipt["receipt_digest"] = canonical_contract_digest_v1(
        {key: value for key, value in receipt.items() if key != "receipt_digest"}
    )
    with pytest.raises(ValidationError, match="UUID"):
        StrategyApprovalReceiptV2.model_validate(receipt)


@pytest.mark.parametrize(
    ("factory", "field", "value"),
    [
        (
            bundle_data,
            "run_id",
            "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA",
        ),
        (receipt_data, "source_digest", "sha256:" + "A" * 64),
        (receipt_data, "approved_at", "2026-07-24T01:02:03+00:00"),
        (receipt_data, "approved_by_account_id", " account "),
        (binding_data, "identity_source", "studio_fallback"),
        (binding_data, "source_revision", " 5cbcbcf "),
    ],
)
def test_noncanonical_values_are_rejected(factory, field, value):
    payload = factory()
    payload[field] = value
    model = (
        StrategyApprovalBundleV1
        if payload["contract_version"] == "StrategyApprovalBundle.v1"
        else StrategyApprovalReceiptV2
        if payload["contract_version"] == "StrategyApprovalReceipt.v2"
        else ParzifalIdentityBindingV1
    )
    with pytest.raises(ValidationError):
        model.model_validate(payload)
