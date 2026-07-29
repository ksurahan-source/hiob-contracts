from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    AcceptedIdentityReceiptV1,
    derive_accepted_identity_receipt_digest_v1,
)


def _receipt() -> dict[str, object]:
    body: dict[str, object] = {
        "contract_version": "AcceptedIdentityReceipt.v1",
        "workspace_id": "00000000-0000-4000-8000-000000000001",
        "brand_slug": "viewok",
        "subject_id": "adult-mom",
        "source_receipt_ref": "parzifal:run-1:identity",
        "source_record_version": 1,
        "state": "accepted",
        "face_id": "face-adult-mom",
        "voice_id": "typecast-adult-mom",
    }
    return {
        **body,
        "receipt_digest": derive_accepted_identity_receipt_digest_v1(body),
    }


def test_receipt_digest_binds_identity_and_acceptance_state() -> None:
    receipt = _receipt()
    for field, changed in (
        ("workspace_id", "00000000-0000-4000-8000-000000000002"),
        ("brand_slug", "other"),
        ("subject_id", "other-subject"),
        ("source_receipt_ref", "parzifal:run-2:identity"),
        ("source_record_version", 2),
        ("state", "revoked"),
        ("face_id", "other-face"),
        ("voice_id", "other-voice"),
    ):
        with pytest.raises(ValidationError):
            AcceptedIdentityReceiptV1.model_validate(
                {**receipt, field: changed}
            )


def test_canonical_accepted_identity_receipt_is_valid() -> None:
    assert AcceptedIdentityReceiptV1.model_validate(_receipt()).state == (
        "accepted"
    )
