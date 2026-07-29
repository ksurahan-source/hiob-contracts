from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    ReelsFactoryFailureReceiptV1,
    derive_reels_factory_failure_receipt_digest_v1,
)


def _receipt(**changes):
    body = {
        "contract_version": "ReelsFactoryFailureReceipt.v1",
        "run_id": "00000000-0000-4000-8000-000000000001",
        "idempotency_key": "studio:one",
        "revision": 5,
        "stage": "voice",
        "code": "VOICE_PROVIDER_TERMINAL",
        "provider_call": "confirmed",
        "provider_attempts": {
            "script": 1,
            "image": 1,
            "voice": 1,
            "render": 0,
        },
    }
    body.update(changes)
    return {
        **body,
        "receipt_digest": derive_reels_factory_failure_receipt_digest_v1(body),
    }


def test_failure_receipt_has_exact_terminal_shape() -> None:
    value = ReelsFactoryFailureReceiptV1.model_validate(_receipt())
    assert set(value.model_dump(mode="json")) == {
        "contract_version",
        "run_id",
        "idempotency_key",
        "revision",
        "stage",
        "code",
        "provider_call",
        "provider_attempts",
        "receipt_digest",
    }


@pytest.mark.parametrize("provider_call", ["none", "confirmed", "unknown"])
def test_failure_receipt_accepts_only_explicit_call_state(
    provider_call: str,
) -> None:
    assert (
        ReelsFactoryFailureReceiptV1.model_validate(
            _receipt(provider_call=provider_call)
        ).provider_call
        == provider_call
    )
    with pytest.raises(ValidationError):
        ReelsFactoryFailureReceiptV1.model_validate(
            _receipt(provider_call="maybe")
        )


def test_failure_receipt_rejects_digest_drift_and_extra_fields() -> None:
    with pytest.raises(ValidationError, match="receipt_digest"):
        ReelsFactoryFailureReceiptV1.model_validate(
            {**_receipt(), "code": "OTHER"}
        )
    with pytest.raises(ValidationError):
        ReelsFactoryFailureReceiptV1.model_validate(
            {**_receipt(), "retryable": False}
        )
