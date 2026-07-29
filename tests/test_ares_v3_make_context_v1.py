"""Star command scope binds make readiness without becoming Ares authority."""

from __future__ import annotations

from copy import deepcopy
from importlib.util import find_spec

import pytest
from pydantic import ValidationError

import hiob_contracts
from hiob_contracts import (
    AresV3MakeContextV1,
    derive_ares_v3_make_context_digest_v1,
)


EXPECTED_KEYS = {
    "contract_version",
    "workspace_id",
    "run_id",
    "brand_id",
    "subject_id",
    "product_id",
    "character_lock_digest",
    "character_lock_version",
    "product_lock_digest",
    "artemis_approval_receipt_id",
    "artemis_approval_receipt_digest",
    "artemis_approval_state_revision",
    "make_context_digest",
}


def _payload() -> dict:
    make_context = {
        "contract_version": "AresV3MakeContext.v1",
        "workspace_id": "4d2b4b89-77de-4f6a-8b3c-8abdafc1e2f1",
        "run_id": "7bdf3494-b232-4f15-93ea-b4a99625ba9c",
        "brand_id": "2a86daca-f5f2-4a3d-a868-f283a0a57d84",
        "subject_id": "lead",
        "product_id": "c4404dda-a191-4bd3-942d-21a45f202554",
        "character_lock_digest": "sha256:" + "1" * 64,
        "character_lock_version": 3,
        "product_lock_digest": "sha256:" + "4" * 64,
        "artemis_approval_receipt_id": "artemis-approval-1",
        "artemis_approval_receipt_digest": "sha256:" + "5" * 64,
        "artemis_approval_state_revision": 4,
    }
    return {
        **make_context,
        "make_context_digest": derive_ares_v3_make_context_digest_v1(
            make_context
        ),
    }


def test_make_context_is_one_exact_atomic_authority_snapshot() -> None:
    parsed = AresV3MakeContextV1.model_validate(_payload())

    assert set(parsed.model_dump(mode="json")) == EXPECTED_KEYS
    assert parsed.make_context_digest == (
        "sha256:9c04fa8a7f7152b3ab51bf3fa45d394426a432e1bb003ef171ffb4fe7038ca07"
    )
    assert parsed.subject_id == "lead"


def test_make_context_is_the_only_public_make_ready_contract() -> None:
    legacy_names = (
        "StarMakeReadyRequestV1",
        "StarMakeReadyReceiptV1",
        "StarMakeReadyResolverV1",
        "derive_star_make_ready_request_digest_v1",
        "derive_star_make_ready_command_id_v1",
        "derive_star_make_ready_receipt_digest_v1",
    )

    for name in legacy_names:
        assert not hasattr(hiob_contracts, name)
        assert name not in hiob_contracts.__all__
    assert find_spec("hiob_contracts.star_make_ready_v1") is None


def test_make_context_has_one_dedicated_debug_module() -> None:
    module_name = "hiob_contracts.ares_v3_make_context_v1"

    assert find_spec(module_name) is not None
    assert AresV3MakeContextV1.__module__ == module_name
    assert derive_ares_v3_make_context_digest_v1.__module__ == module_name


@pytest.mark.parametrize("field", ["workspace_id", "run_id", "brand_id"])
def test_make_context_rejects_non_uuid_db_scope_after_rehash(
    field: str,
) -> None:
    value = _payload()
    value[field] = "not-a-db-uuid"
    value["make_context_digest"] = derive_ares_v3_make_context_digest_v1(value)

    with pytest.raises(ValidationError, match=field):
        AresV3MakeContextV1.model_validate(value)


@pytest.mark.parametrize(
    "field",
    [
        "workspace_id",
        "run_id",
        "brand_id",
        "subject_id",
        "product_id",
        "character_lock_digest",
        "character_lock_version",
        "product_lock_digest",
        "artemis_approval_receipt_id",
        "artemis_approval_receipt_digest",
        "artemis_approval_state_revision",
    ],
)
def test_make_context_rejects_authority_drift(field: str) -> None:
    value = _payload()
    valid_uuid_drift = {
        "workspace_id": "11111111-1111-4111-8111-111111111111",
        "run_id": "22222222-2222-4222-8222-222222222222",
        "brand_id": "33333333-3333-4333-8333-333333333333",
    }
    value[field] = (
        value[field] + 1
        if isinstance(value[field], int)
        else "sha256:" + "9" * 64
        if field.endswith("digest")
        else valid_uuid_drift.get(field, "changed")
    )

    with pytest.raises(ValidationError, match="make_context_digest"):
        AresV3MakeContextV1.model_validate(value)


@pytest.mark.parametrize(
    "legacy_or_provider_field",
    [
        "run_revision",
        "command_id",
        "request_digest",
        "receipt_digest",
        "provider_call",
        "dispatch",
        "make_ready_receipt",
        "scope",
        "operation_id",
        "idempotency_key",
    ],
)
def test_make_context_rejects_command_receipt_and_provider_authority(
    legacy_or_provider_field: str,
) -> None:
    value = _payload()
    value[legacy_or_provider_field] = "client-owned"

    with pytest.raises(ValidationError):
        AresV3MakeContextV1.model_validate(value)


def test_make_context_is_immutable_and_digest_helper_requires_exact_source() -> None:
    parsed = AresV3MakeContextV1.model_validate(_payload())

    with pytest.raises(ValidationError):
        parsed.subject_id = "mutated"

    incomplete = deepcopy(_payload())
    del incomplete["make_context_digest"]
    del incomplete["product_lock_digest"]
    with pytest.raises((KeyError, ValidationError)):
        derive_ares_v3_make_context_digest_v1(incomplete)
