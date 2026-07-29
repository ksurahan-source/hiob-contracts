from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    StarMakeReadyReceiptV1,
    StarMakeReadyRequestV1,
    derive_star_make_ready_command_id_v1,
    derive_star_make_ready_receipt_digest_v1,
    derive_star_make_ready_request_digest_v1,
)

WORKSPACE_ID = "3c8102c6-ec84-4530-9606-1c977b090edc"
RUN_ID = "af459458-e7aa-4c03-b263-702112e61c15"


def _request() -> dict:
    payload = {
        "contract_version": "StarMakeReadyRequest.v1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "run_revision": 7,
    }
    return {
        **payload,
        "request_digest": derive_star_make_ready_request_digest_v1(payload),
    }


def _receipt() -> dict:
    request = _request()
    payload = {
        "contract_version": "StarMakeReadyReceipt.v1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "run_revision": 7,
        "request_digest": request["request_digest"],
        "character_lock_digest": "sha256:" + "1" * 64,
        "character_lock_version": 3,
        "product_lock_digest": "sha256:" + "2" * 64,
        "artemis_approval_receipt_id": "artemis-approval-1",
        "artemis_approval_receipt_digest": "sha256:" + "3" * 64,
        "artemis_approval_state_revision": 4,
        "state": "succeeded",
        "provider_call": "none",
    }
    payload["command_id"] = derive_star_make_ready_command_id_v1(payload)
    return {
        **payload,
        "receipt_digest": derive_star_make_ready_receipt_digest_v1(payload),
    }


class _Resolver:
    def __init__(self, expected: dict) -> None:
        self.expected = expected

    def is_current_make_ready(self, **authority) -> bool:
        return authority == self.expected


def _authority(value: dict) -> dict:
    return {
        field: value[field]
        for field in (
            "command_id",
            "workspace_id",
            "run_id",
            "run_revision",
            "character_lock_digest",
            "character_lock_version",
            "product_lock_digest",
            "artemis_approval_receipt_id",
            "artemis_approval_receipt_digest",
            "artemis_approval_state_revision",
        )
    }


def test_make_ready_request_and_receipt_bind_current_lock_authority() -> None:
    request = StarMakeReadyRequestV1.model_validate(_request())
    receipt = StarMakeReadyReceiptV1.model_validate(_receipt())

    assert receipt.request_digest == request.request_digest
    assert receipt.character_lock_version == 3
    assert receipt.artemis_approval_state_revision == 4
    assert receipt.provider_call == "none"
    assert request.request_digest == (
        "sha256:a1920ab5b142cbf0f2ecc88dc08f301035bd299c486a5bdaf005dc3c03b765b9"
    )
    assert receipt.command_id == (
        "sha256:c31ef5061b88f66e3692a6e97a8b6f7b878bb40fe9eefbbcf6c25644edbf6da6"
    )
    assert receipt.receipt_digest == (
        "sha256:ca36a7df54b138225b205542af832a52b74f209adc7693e99054c9e23ff497be"
    )
    assert receipt.authorizes(resolver=_Resolver(_authority(_receipt())))


@pytest.mark.parametrize(
    "field",
    [
        "workspace_id",
        "run_id",
        "run_revision",
        "character_lock_digest",
        "character_lock_version",
        "product_lock_digest",
        "artemis_approval_receipt_digest",
        "artemis_approval_state_revision",
    ],
)
def test_make_ready_receipt_rejects_scope_or_authority_drift(field: str) -> None:
    value = _receipt()
    value[field] = (
        value[field] + 1
        if isinstance(value[field], int)
        else "sha256:" + "9" * 64
        if field.endswith("digest")
        else "changed"
    )

    with pytest.raises(ValidationError):
        StarMakeReadyReceiptV1.model_validate(value)


def test_make_ready_rejects_provider_and_client_authority_fields() -> None:
    value = _receipt()
    value["provider_call"] = "seedream"
    value["parzifal_receipt"] = {"face_id": "client-face"}
    value["dispatch"] = {"provider": "seedream"}

    with pytest.raises(ValidationError) as exc_info:
        StarMakeReadyReceiptV1.model_validate(value)

    errors = exc_info.value.errors()
    assert any(error["loc"] == ("provider_call",) for error in errors)
    assert any(error["loc"] == ("parzifal_receipt",) for error in errors)
    assert any(error["loc"] == ("dispatch",) for error in errors)


def test_make_ready_rejects_non_opaque_approval_receipt_id() -> None:
    value = _receipt()
    value["artemis_approval_receipt_id"] = "\ud800"

    with pytest.raises(ValidationError):
        StarMakeReadyReceiptV1.model_validate(value)


def test_fully_rehashed_fabrication_is_not_current_authority() -> None:
    canonical = _receipt()
    fabricated = _receipt()
    fabricated["character_lock_digest"] = "sha256:" + "8" * 64
    fabricated["command_id"] = derive_star_make_ready_command_id_v1(fabricated)
    fabricated["receipt_digest"] = derive_star_make_ready_receipt_digest_v1(
        fabricated
    )

    structurally_valid = StarMakeReadyReceiptV1.model_validate(fabricated)

    assert not structurally_valid.authorizes(
        resolver=_Resolver(_authority(canonical))
    )


def test_make_ready_resolver_requires_literal_true() -> None:
    receipt = StarMakeReadyReceiptV1.model_validate(_receipt())

    class TruthyResolver:
        def is_current_make_ready(self, **_authority):
            return 1

    assert not receipt.authorizes(resolver=TruthyResolver())
