"""Star command scope binds make readiness without becoming Ares authority."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    AresV3CommandScopeV1,
    derive_ares_v3_make_context_digest_v1,
)


EXPECTED_KEYS = {
    "contract_version",
    "scope",
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
        "contract_version": "AresV3CommandScope.v1",
        "scope": {
            "workspace_id": "ws-v3-1",
            "run_id": "run-v3-1",
            "operation_id": "op-script-v3-1",
            "idempotency_key": (
                "ares-script-v3:ws-v3-1:run-v3-1:op-script-v3-1"
            ),
        },
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


def test_command_scope_is_one_exact_atomic_make_context() -> None:
    parsed = AresV3CommandScopeV1.model_validate(_payload())

    assert set(parsed.model_dump(mode="json")) == EXPECTED_KEYS
    assert parsed.make_context_digest == (
        "sha256:e99651e95596a97ce408a82e53bbe041a8e7e981bf8503d43ab4a090abd87b3e"
    )
    assert parsed.subject_id == "lead"


@pytest.mark.parametrize(
    "field",
    [
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
def test_command_scope_rejects_make_context_drift(field: str) -> None:
    value = _payload()
    value[field] = (
        value[field] + 1
        if isinstance(value[field], int)
        else "sha256:" + "9" * 64
        if field.endswith("digest")
        else "changed"
    )

    with pytest.raises(ValidationError, match="make_context_digest"):
        AresV3CommandScopeV1.model_validate(value)


def test_command_scope_rejects_scope_drift() -> None:
    value = _payload()
    value["scope"]["workspace_id"] = "other-workspace"

    with pytest.raises(ValidationError, match="make_context_digest"):
        AresV3CommandScopeV1.model_validate(value)


def test_make_context_digest_excludes_command_execution_identity() -> None:
    value = _payload()
    value["scope"]["operation_id"] = "other-operation"
    value["scope"]["idempotency_key"] = "other-idempotency-key"

    parsed = AresV3CommandScopeV1.model_validate(value)

    assert parsed.make_context_digest == _payload()["make_context_digest"]


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
    ],
)
def test_command_scope_rejects_parallel_receipt_and_provider_authority(
    legacy_or_provider_field: str,
) -> None:
    value = _payload()
    value[legacy_or_provider_field] = "client-owned"

    with pytest.raises(ValidationError):
        AresV3CommandScopeV1.model_validate(value)


def test_command_scope_is_immutable_and_digest_helper_requires_exact_source() -> None:
    parsed = AresV3CommandScopeV1.model_validate(_payload())

    with pytest.raises(ValidationError):
        parsed.scope.operation_id = "mutated"

    incomplete = deepcopy(_payload())
    del incomplete["make_context_digest"]
    del incomplete["product_lock_digest"]
    with pytest.raises((KeyError, ValidationError)):
        derive_ares_v3_make_context_digest_v1(incomplete)
