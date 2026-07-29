"""Star command scope binds make readiness without becoming Ares authority."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

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
        "workspace_id": "ws-v3-1",
        "run_id": "run-v3-1",
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
        "sha256:e99651e95596a97ce408a82e53bbe041a8e7e981bf8503d43ab4a090abd87b3e"
    )
    assert parsed.subject_id == "lead"


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
    value[field] = (
        value[field] + 1
        if isinstance(value[field], int)
        else "sha256:" + "9" * 64
        if field.endswith("digest")
        else "changed"
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
