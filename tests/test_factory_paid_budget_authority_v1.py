"""Pre-script paid-budget authority is separate from the exact beat manifest."""

from __future__ import annotations

import json
import pickle
import copy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import hiob_contracts
from hiob_contracts import (
    FactoryPaidBudgetApprovalReceiptV1,
    FactoryPaidBudgetAuthorityV1,
    VerifiedFactoryPaidBudgetAuthorityV1,
    build_factory_paid_budget_authority_v1,
    derive_factory_paid_budget_approval_subject_digest_v1,
    derive_factory_paid_budget_approval_receipt_digest_v1,
    derive_factory_paid_budget_authority_digest_v1,
    derive_factory_paid_budget_idempotency_key_v1,
    registered_contracts,
    sha256_digest,
    validate_payload,
    factory_beat_manifest_binds_paid_authority_v1,
    factory_beat_manifest_structurally_binds_paid_authority_v1,
    require_factory_beat_manifest_paid_authority_v1,
)


WORKSPACE_ID = "00000000-0000-4000-8000-000000000001"
RUN_ID = "00000000-0000-4000-8000-000000000002"
APPROVAL_RECEIPT_DIGEST = sha256_digest({"approval": "paid-budget-v1"})
COST_PROFILE_DIGEST = sha256_digest({"pricing": "fal-kling-2026-08-01"})


class _Resolver:
    def __init__(self, current: bool = True) -> None:
        self.current = current
        self.last_identity = None

    def is_current_approval(self, **identity) -> bool:
        self.last_identity = identity
        return self.current


def _approval_receipt(**changes):
    body = {
        "contract_version": "FactoryPaidBudgetApprovalReceipt.v1",
        "receipt_id": "approval-paid-budget-1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "all_beat_count": 5,
        "paid_calls": {
            "script": 1, "image": 5, "video": 5, "voice": 5,
            "render": 1, "retries": 0, "fallbacks": 0,
            "character_lock": 0,
        },
        "max_total_cost_microunits": 12_500_000,
        "currency": "USD",
        "cost_profile_digest": COST_PROFILE_DIGEST,
        "pricing_policy_revision": 3,
        "approver_account_id": "account-owner",
        "decision": "approved",
        "policy_version": "paid-budget-policy-v1",
        "state_revision": 1,
        "approved_at_utc": "2026-08-01T07:00:00Z",
        "expires_at_utc": "2026-08-01T09:00:00Z",
        "revoked_at_utc": None,
        "transaction_audit_id": "approval-paid-budget-1",
    }
    body.update(changes)
    if "all_beat_count" in changes and "paid_calls" not in changes:
        count = changes["all_beat_count"]
        body["paid_calls"] = {
            "script": 1, "image": count, "video": count, "voice": count,
            "render": 1, "retries": 0, "fallbacks": 0,
            "character_lock": 0,
        }
    body["approval_subject_digest"] = (
        derive_factory_paid_budget_approval_subject_digest_v1(body)
    )
    body["receipt_digest"] = (
        derive_factory_paid_budget_approval_receipt_digest_v1(body)
    )
    return FactoryPaidBudgetApprovalReceiptV1.model_validate(body)


def _authority(**changes):
    receipt = changes.pop("approval_receipt", None)
    scope = {
        key: changes.pop(key)
        for key in list(changes)
        if key in {
            "workspace_id", "run_id", "factory_revision", "all_beat_count",
            "max_total_cost_microunits", "currency",
            "cost_profile_digest", "pricing_policy_revision",
        }
    }
    if receipt is None:
        receipt_id = changes.pop("approval_receipt_id", "approval-paid-budget-1")
        changes.pop("approval_receipt_digest", None)
        receipt = _approval_receipt(
            **scope,
            receipt_id=receipt_id,
            transaction_audit_id=receipt_id,
        )
    body = {
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "all_beat_count": 5,
        "max_total_cost_microunits": 12_500_000,
        "currency": "USD",
        "cost_profile_digest": COST_PROFILE_DIGEST,
        "pricing_policy_revision": 3,
        "approval_receipt": receipt,
        "at_utc": "2026-08-01T08:00:00Z",
        "resolver": _Resolver(),
        **scope,
    }
    body.update(changes)
    return build_factory_paid_budget_authority_v1(
        **body
    ).authority.model_dump(mode="json")


def test_receipt_is_structural_evidence_not_bearer_authority() -> None:
    receipt = _approval_receipt()
    authority = FactoryPaidBudgetAuthorityV1.model_validate(_authority())
    assert receipt.authorizes(
        authority, at_utc="2026-08-01T08:00:00Z", resolver=_Resolver()
    )
    assert not receipt.authorizes(
        authority, at_utc="2026-08-01T08:00:00Z", resolver=_Resolver(False)
    )
    with pytest.raises(ValueError, match="current durable approval"):
        FactoryPaidBudgetAuthorityV1.from_verified(
            authority.model_dump(mode="json"),
            approval_receipt=receipt,
            at_utc="2026-08-01T08:00:00Z",
            resolver=_Resolver(False),
        )


def test_verified_authority_is_nonserializable_capability_and_manifest_guard() -> None:
    receipt = _approval_receipt()
    parsed = FactoryPaidBudgetAuthorityV1.model_validate(_authority())
    verified = FactoryPaidBudgetAuthorityV1.from_verified(
        parsed.model_dump(mode="json"),
        approval_receipt=receipt,
        at_utc="2026-08-01T08:00:00Z",
        resolver=_Resolver(),
    )
    assert isinstance(verified, VerifiedFactoryPaidBudgetAuthorityV1)
    assert verified.authority is parsed or verified.authority == parsed
    with pytest.raises(TypeError):
        json.dumps(verified)
    with pytest.raises((TypeError, pickle.PicklingError)):
        pickle.dumps(verified)
    with pytest.raises(TypeError):
        copy.copy(verified)
    with pytest.raises(TypeError):
        copy.deepcopy(verified)
    with pytest.raises(TypeError, match="immutable"):
        verified.any_field = "value"
    with pytest.raises(TypeError, match="immutable"):
        del verified.any_field
    assert repr(verified) == "VerifiedFactoryPaidBudgetAuthorityV1(<sealed>)"
    with pytest.raises(TypeError, match="only be minted"):
        VerifiedFactoryPaidBudgetAuthorityV1(parsed, _token=object())

    manifest = SimpleNamespace(
        workspace_id=parsed.workspace_id,
        run_id=parsed.run_id,
        factory_revision=parsed.factory_revision,
        beats=[object()] * parsed.all_beat_count,
        paid_budget_authority_digest=parsed.authority_digest,
    )
    assert factory_beat_manifest_binds_paid_authority_v1(manifest, verified)
    assert not factory_beat_manifest_binds_paid_authority_v1(manifest, parsed)
    assert factory_beat_manifest_structurally_binds_paid_authority_v1(
        manifest, parsed
    )
    assert require_factory_beat_manifest_paid_authority_v1(
        manifest, verified
    ) is verified
    mismatched_manifest = SimpleNamespace(
        workspace_id=parsed.workspace_id,
        run_id=parsed.run_id,
        factory_revision=parsed.factory_revision,
        beats=[object()] * (parsed.all_beat_count - 1),
        paid_budget_authority_digest=parsed.authority_digest,
    )
    with pytest.raises(ValueError, match="does not bind"):
        require_factory_beat_manifest_paid_authority_v1(
            mismatched_manifest, verified
        )
    with pytest.raises(TypeError, match="VerifiedFactoryPaidBudgetAuthority"):
        require_factory_beat_manifest_paid_authority_v1(manifest, parsed)


def test_verified_authority_registry_defeats_slot_and_getter_retarget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _approval_receipt()
    original = FactoryPaidBudgetAuthorityV1.model_validate(_authority())
    verified = FactoryPaidBudgetAuthorityV1.from_verified(
        original,
        approval_receipt=receipt,
        at_utc="2026-08-01T08:00:00Z",
        resolver=_Resolver(),
    )
    alien = FactoryPaidBudgetAuthorityV1.model_validate(
        _authority(cost_profile_digest=sha256_digest({"pricing": "alien"}))
    )
    manifest = SimpleNamespace(
        workspace_id=original.workspace_id,
        run_id=original.run_id,
        factory_revision=original.factory_revision,
        beats=[object()] * original.all_beat_count,
        paid_budget_authority_digest=original.authority_digest,
    )

    with pytest.raises((AttributeError, TypeError)):
        object.__setattr__(
            verified,
            "_VerifiedFactoryPaidBudgetAuthorityV1__authority",
            alien,
        )
    monkeypatch.setattr(
        VerifiedFactoryPaidBudgetAuthorityV1,
        "authority",
        property(lambda _self: alien),
    )
    assert factory_beat_manifest_binds_paid_authority_v1(manifest, verified)


def test_cost_profile_and_current_pricing_revision_are_sealed_everywhere() -> None:
    receipt = _approval_receipt()
    authority = FactoryPaidBudgetAuthorityV1.model_validate(_authority())
    assert authority.cost_profile_digest == COST_PROFILE_DIGEST
    assert authority.pricing_policy_revision == 3
    assert receipt.cost_profile_digest == authority.cost_profile_digest
    assert receipt.pricing_policy_revision == authority.pricing_policy_revision
    resolver = _Resolver()
    assert receipt.authorizes(
        authority, at_utc="2026-08-01T08:00:00Z", resolver=resolver
    )
    assert resolver.last_identity["cost_profile_digest"] == COST_PROFILE_DIGEST
    assert resolver.last_identity["pricing_policy_revision"] == 3


@pytest.mark.parametrize(
    ("receipt_change", "at_utc"),
    [
        ({"revoked_at_utc": "2026-08-01T07:30:00Z"}, "2026-08-01T08:00:00Z"),
        ({}, "2026-08-01T09:00:00Z"),
    ],
)
def test_builder_rejects_revoked_or_expired_approval(
    receipt_change: dict, at_utc: str
) -> None:
    with pytest.raises(ValueError, match="current durable approval"):
        _authority(
            approval_receipt=_approval_receipt(**receipt_change),
            at_utc=at_utc,
        )


def test_builds_one_frozen_pre_script_authority_with_all_bindings() -> None:
    value = FactoryPaidBudgetAuthorityV1.model_validate(_authority())

    assert value.contract_version == "FactoryPaidBudgetAuthority.v1"
    assert value.all_beat_count == 5
    assert value.max_total_cost_microunits == 12_500_000
    assert value.paid_calls.model_dump() == {
        "script": 1,
        "image": 5,
        "video": 5,
        "voice": 5,
        "render": 1,
        "retries": 0,
        "fallbacks": 0,
        "character_lock": 0,
    }
    assert value.approval_subject_digest == (
        derive_factory_paid_budget_approval_subject_digest_v1(value)
    )
    assert value.idempotency_key == (
        derive_factory_paid_budget_idempotency_key_v1(value)
    )
    assert value.authority_digest == (
        derive_factory_paid_budget_authority_digest_v1(value)
    )
    assert hiob_contracts.FactoryPaidBudgetAuthorityV1 is (
        FactoryPaidBudgetAuthorityV1
    )
    with pytest.raises((ValidationError, ValueError)):
        value.all_beat_count = 2


@pytest.mark.parametrize("all_beat_count", [1, 2, 3, 5, 12, 16])
def test_authority_supports_legacy_one_beat_and_all_product_counts(
    all_beat_count: int,
) -> None:
    value = FactoryPaidBudgetAuthorityV1.model_validate(
        _authority(all_beat_count=all_beat_count)
    )

    assert value.all_beat_count == all_beat_count


@pytest.mark.parametrize("all_beat_count", [0, 17, True, 1.0])
def test_authority_rejects_noncanonical_or_unsupported_count(
    all_beat_count,
) -> None:
    with pytest.raises((ValidationError, ValueError)):
        FactoryPaidBudgetAuthorityV1.model_validate(
            _authority(all_beat_count=all_beat_count)
        )


@pytest.mark.parametrize(
    "max_total_cost_microunits",
    [0, -1, True, 1.0, "12500000"],
)
def test_authority_requires_positive_integer_microunits(
    max_total_cost_microunits,
) -> None:
    with pytest.raises((ValidationError, ValueError)):
        FactoryPaidBudgetAuthorityV1.model_validate(
            _authority(max_total_cost_microunits=max_total_cost_microunits)
        )


@pytest.mark.parametrize("currency", ["usd", "USDT", "U1D", ""])
def test_authority_requires_uppercase_iso_currency(currency: str) -> None:
    with pytest.raises(ValidationError):
        FactoryPaidBudgetAuthorityV1.model_validate(
            _authority(currency=currency)
        )


@pytest.mark.parametrize(
    "field",
    [
        "all_beat_count",
        "max_total_cost_microunits",
        "currency",
        "cost_profile_digest",
        "pricing_policy_revision",
        "approval_receipt_id",
        "approval_receipt_digest",
    ],
)
def test_approval_subject_and_authority_fail_closed_on_tamper(field: str) -> None:
    payload = _authority()
    payload[field] = {
        "all_beat_count": 12,
        "max_total_cost_microunits": 13_000_000,
        "currency": "KRW",
        "cost_profile_digest": sha256_digest({"pricing": "other"}),
        "pricing_policy_revision": 4,
        "approval_receipt_id": "approval-other",
        "approval_receipt_digest": sha256_digest({"approval": "other"}),
    }[field]

    with pytest.raises(ValidationError):
        FactoryPaidBudgetAuthorityV1.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("script", 0),
        ("image", 4),
        ("video", 6),
        ("voice", 1),
        ("render", 2),
        ("retries", 1),
        ("fallbacks", 1),
        ("character_lock", 1),
    ],
)
def test_paid_calls_must_equal_exact_all_beat_cardinality(
    field: str,
    value: int,
) -> None:
    payload = _authority()
    payload["paid_calls"][field] = value
    payload["approval_subject_digest"] = (
        derive_factory_paid_budget_approval_subject_digest_v1(payload)
    )
    payload["idempotency_key"] = derive_factory_paid_budget_idempotency_key_v1(
        payload
    )
    payload["authority_digest"] = derive_factory_paid_budget_authority_digest_v1(
        payload
    )

    with pytest.raises(ValidationError, match="paid_calls"):
        FactoryPaidBudgetAuthorityV1.model_validate(payload)


def test_rehashed_approval_or_idempotency_substitution_is_rejected() -> None:
    payload = _authority()
    payload["approval_subject_digest"] = (
        derive_factory_paid_budget_approval_subject_digest_v1(
            {**payload, "all_beat_count": 12}
        )
    )
    payload["idempotency_key"] = derive_factory_paid_budget_idempotency_key_v1(
        payload
    )
    payload["authority_digest"] = derive_factory_paid_budget_authority_digest_v1(
        payload
    )
    with pytest.raises(ValidationError, match="approval_subject_digest"):
        FactoryPaidBudgetAuthorityV1.model_validate(payload)

    payload = _authority()
    payload["idempotency_key"] = sha256_digest({"idempotency": "other"})
    payload["authority_digest"] = derive_factory_paid_budget_authority_digest_v1(
        payload
    )
    with pytest.raises(ValidationError, match="idempotency_key"):
        FactoryPaidBudgetAuthorityV1.model_validate(payload)

    payload = _authority()
    payload["authority_digest"] = sha256_digest({"authority": "other"})
    with pytest.raises(ValidationError, match="authority_digest"):
        FactoryPaidBudgetAuthorityV1.model_validate(payload)


def test_unminted_verified_capability_is_rejected() -> None:
    ghost = object.__new__(VerifiedFactoryPaidBudgetAuthorityV1)
    with pytest.raises(TypeError, match="unminted"):
        _ = ghost.authority


def test_approval_receipt_late_guards_are_independently_fail_closed() -> None:
    receipt = _approval_receipt()
    invalid_cases = [
        (
            {"transaction_audit_id": "other"},
            "transaction_audit_id",
        ),
        (
            {
                "paid_calls": receipt.paid_calls.model_copy(
                    update={"image": receipt.all_beat_count - 1}
                )
            },
            "paid_calls",
        ),
        (
            {"approval_subject_digest": sha256_digest({"subject": "other"})},
            "approval_subject_digest",
        ),
        (
            {"expires_at_utc": receipt.approved_at_utc},
            "must follow",
        ),
        (
            {"revoked_at_utc": "2026-08-01T06:59:59Z"},
            "approval lifetime",
        ),
        (
            {"receipt_digest": sha256_digest({"receipt": "other"})},
            "receipt_digest",
        ),
    ]
    for update, message in invalid_cases:
        with pytest.raises(ValueError, match=message):
            receipt.model_copy(update=update)._bind_receipt()


def test_approval_authorizer_rejects_structurally_unbound_authority() -> None:
    receipt = _approval_receipt()
    authority = FactoryPaidBudgetAuthorityV1.model_validate(_authority())
    alien = authority.model_copy(
        update={"run_id": "00000000-0000-4000-8000-000000000099"}
    )
    assert not receipt.authorizes(
        alien,
        at_utc="2026-08-01T08:00:00Z",
        resolver=_Resolver(),
    )


def test_distinct_budget_or_approval_mints_distinct_idempotency() -> None:
    base = _authority()
    changed_count = _authority(all_beat_count=12)
    changed_cost = _authority(max_total_cost_microunits=13_000_000)
    changed_profile = _authority(
        cost_profile_digest=sha256_digest({"pricing": "next"})
    )
    changed_pricing_revision = _authority(pricing_policy_revision=4)
    changed_receipt = _authority(
        approval_receipt_id="approval-paid-budget-2",
        approval_receipt_digest=sha256_digest({"approval": "paid-budget-v2"}),
    )

    assert len(
        {
            base["idempotency_key"],
            changed_count["idempotency_key"],
            changed_cost["idempotency_key"],
            changed_profile["idempotency_key"],
            changed_pricing_revision["idempotency_key"],
            changed_receipt["idempotency_key"],
        }
    ) == 6


@pytest.mark.parametrize(
    "legacy_field",
    ["exact", "operations", "plan_digest", "sealed_voice_id", "paid_budget"],
)
def test_authority_does_not_collide_with_legacy_or_plan_budget_shape(
    legacy_field: str,
) -> None:
    payload = _authority()
    payload[legacy_field] = [] if legacy_field in {"operations", "paid_budget"} else True
    with pytest.raises(ValidationError, match="extra"):
        FactoryPaidBudgetAuthorityV1.model_validate(payload)


def test_registry_exposes_fail_loud_consumer_surface() -> None:
    assert "FactoryPaidBudgetAuthority" in registered_contracts()
    assert "FactoryPaidBudgetApprovalReceipt" in registered_contracts()
    result = validate_payload("FactoryPaidBudgetAuthority", _authority())
    assert result.ok is True
    assert isinstance(result.obj, FactoryPaidBudgetAuthorityV1)
    receipt_result = validate_payload(
        "FactoryPaidBudgetApprovalReceipt",
        _approval_receipt().model_dump(mode="json"),
    )
    assert receipt_result.ok is True
    assert isinstance(receipt_result.obj, FactoryPaidBudgetApprovalReceiptV1)


def test_python_typescript_digest_vectors_are_stable() -> None:
    value = _authority()
    assert value["approval_subject_digest"] == (
        "sha256:860647e42e99dec7d580e5a323207e617f1351bfe5d20b20b99e77edc4cc55a4"
    )
    assert value["idempotency_key"] == (
        "sha256:692f716bcad148945500ca48292ab1aee705bf128de1f2515a2d9449e1308ba1"
    )
    assert value["authority_digest"] == (
        "sha256:c2cdbc6b4111fbba80ff3bea160d8391f4461eb1ae364f29c5bed3e8a2721e8b"
    )
    derive_factory_paid_budget_approval_receipt_digest_v1,
