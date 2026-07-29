from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    ParzifalIdentityReceiptV1,
    StarMakeReadyReceiptV1,
    derive_character_identity_binding_digest_v1,
    derive_parzifal_identity_receipt_payload_digest_v1,
    derive_star_make_ready_receipt_digest_v1,
)


def _payload() -> dict:
    identity_binding_digest = derive_character_identity_binding_digest_v1(
        subject_id="subject-1",
        face_id="face-1",
        voice_id="voice-1",
    )
    parzifal_payload = {
        "contract_version": "ParzifalIdentityReceipt.v1",
        "receipt_id": "parzifal-receipt-1",
        "workspace_id": "workspace-1",
        "run_id": "run-1",
        "subject_id": "subject-1",
        "face_id": "face-1",
        "voice_id": "voice-1",
        "identity_binding_digest": identity_binding_digest,
        "element_lock_digest": "sha256:" + "1" * 64,
    }
    parzifal_receipt = {
        **parzifal_payload,
        "payload_digest": derive_parzifal_identity_receipt_payload_digest_v1(
            parzifal_payload
        ),
    }
    make_ready_payload = {
        "contract_version": "StarMakeReadyReceipt.v1",
        "workspace_id": "workspace-1",
        "run_id": "run-1",
        "parzifal_record_ref": {
            "id": parzifal_receipt["receipt_id"],
            "version": 1,
            "digest": parzifal_receipt["payload_digest"],
        },
        "parzifal_receipt": parzifal_receipt,
        "current_element_lock_digest": parzifal_receipt[
            "element_lock_digest"
        ],
        "provider_call": "none",
    }
    return {
        **make_ready_payload,
        "receipt_digest": derive_star_make_ready_receipt_digest_v1(
            make_ready_payload
        ),
    }


def test_star_make_ready_receipt_accepts_exact_bound_authority() -> None:
    receipt = StarMakeReadyReceiptV1.model_validate(_payload())

    assert isinstance(receipt.parzifal_receipt, ParzifalIdentityReceiptV1)
    assert receipt.parzifal_record_ref.id == receipt.parzifal_receipt.receipt_id
    assert (
        receipt.parzifal_record_ref.digest
        == receipt.parzifal_receipt.payload_digest
    )
    assert receipt.provider_call == "none"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda value: value["parzifal_record_ref"].update(
                {"id": "other-receipt"}
            ),
            "parzifal_record_ref.id must match parzifal_receipt.receipt_id",
        ),
        (
            lambda value: value["parzifal_record_ref"].update(
                {"digest": "sha256:" + "2" * 64}
            ),
            (
                "parzifal_record_ref.digest must match "
                "parzifal_receipt.payload_digest"
            ),
        ),
        (
            lambda value: value.update(
                {"current_element_lock_digest": "sha256:" + "3" * 64}
            ),
            (
                "current_element_lock_digest must match "
                "parzifal_receipt.element_lock_digest"
            ),
        ),
        (
            lambda value: value["parzifal_receipt"].update(
                {"identity_binding_digest": "sha256:" + "4" * 64}
            ),
            (
                "identity_binding_digest does not match "
                "subject_id + face_id + voice_id"
            ),
        ),
        (
            lambda value: value.update({"provider_call": "seedream"}),
            "Input should be 'none'",
        ),
    ],
)
def test_star_make_ready_receipt_fails_closed_on_binding_drift(
    mutate,
    message: str,
) -> None:
    value = _payload()
    mutate(value)

    with pytest.raises(ValidationError, match=message.replace("+", r"\+")):
        StarMakeReadyReceiptV1.model_validate(value)


def test_star_make_ready_receipt_rejects_non_positive_version_and_extras() -> None:
    value = _payload()
    value["parzifal_record_ref"]["version"] = 0
    value["dispatch"] = {"provider": "seedream"}

    with pytest.raises(ValidationError) as exc_info:
        StarMakeReadyReceiptV1.model_validate(value)

    errors = exc_info.value.errors()
    assert any(error["loc"] == ("parzifal_record_ref", "version") for error in errors)
    assert any(error["loc"] == ("dispatch",) for error in errors)
