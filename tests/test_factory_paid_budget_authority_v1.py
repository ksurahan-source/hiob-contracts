"""Pre-script paid-budget authority is separate from the exact beat manifest."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

import hiob_contracts
from hiob_contracts import (
    FactoryPaidBudgetAuthorityV1,
    build_factory_paid_budget_authority_v1,
    derive_factory_paid_budget_approval_subject_digest_v1,
    derive_factory_paid_budget_authority_digest_v1,
    derive_factory_paid_budget_idempotency_key_v1,
    registered_contracts,
    sha256_digest,
    validate_payload,
)


WORKSPACE_ID = "00000000-0000-4000-8000-000000000001"
RUN_ID = "00000000-0000-4000-8000-000000000002"
APPROVAL_RECEIPT_DIGEST = sha256_digest({"approval": "paid-budget-v1"})


def _authority(**changes):
    body = {
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "all_beat_count": 5,
        "max_total_cost_microunits": 12_500_000,
        "currency": "USD",
        "approval_receipt_id": "approval-paid-budget-1",
        "approval_receipt_digest": APPROVAL_RECEIPT_DIGEST,
    }
    body.update(changes)
    return build_factory_paid_budget_authority_v1(**body).model_dump(mode="json")


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
    with pytest.raises(ValidationError):
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
    with pytest.raises(ValidationError):
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
    with pytest.raises(ValidationError):
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


def test_distinct_budget_or_approval_mints_distinct_idempotency() -> None:
    base = _authority()
    changed_count = _authority(all_beat_count=12)
    changed_cost = _authority(max_total_cost_microunits=13_000_000)
    changed_receipt = _authority(
        approval_receipt_id="approval-paid-budget-2",
        approval_receipt_digest=sha256_digest({"approval": "paid-budget-v2"}),
    )

    assert len(
        {
            base["idempotency_key"],
            changed_count["idempotency_key"],
            changed_cost["idempotency_key"],
            changed_receipt["idempotency_key"],
        }
    ) == 4


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
    result = validate_payload("FactoryPaidBudgetAuthority", _authority())
    assert result.ok is True
    assert isinstance(result.obj, FactoryPaidBudgetAuthorityV1)


def test_python_typescript_digest_vectors_are_stable() -> None:
    value = _authority()
    assert value["approval_subject_digest"] == (
        "sha256:f656277f35a207f2f6b192355955a5e437daf10cb2e2633031e7447cc66b78af"
    )
    assert value["idempotency_key"] == (
        "sha256:a512001302620cf0466024129162477404ec1fb1ed8d46b526ac9fd2d8bfd267"
    )
    assert value["authority_digest"] == (
        "sha256:9dc540535515e92e11c7596e563e22a6d0e7d08f24410e9de33c9e560de84ee9"
    )
