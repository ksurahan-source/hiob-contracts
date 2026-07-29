from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    ReelsFactoryProgressReceiptV1,
    derive_reels_factory_progress_receipt_digest_v1,
)


RUN_ID = "00000000-0000-4000-8000-000000000001"


def _receipt(**changes):
    body = {
        "contract_version": "ReelsFactoryProgressReceipt.v1",
        "run_id": RUN_ID,
        "idempotency_key": "studio:run:one-reel",
        "revision": 4,
        "stage": "render",
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
        "receipt_digest": derive_reels_factory_progress_receipt_digest_v1(
            body
        ),
    }


def test_progress_receipt_has_exact_sealed_shape() -> None:
    value = ReelsFactoryProgressReceiptV1.model_validate(_receipt())

    assert set(value.model_dump(mode="json")) == {
        "contract_version",
        "run_id",
        "idempotency_key",
        "revision",
        "stage",
        "provider_attempts",
        "receipt_digest",
    }


def test_progress_receipt_rejects_digest_drift_and_extra_authority() -> None:
    with pytest.raises(ValidationError, match="receipt_digest"):
        ReelsFactoryProgressReceiptV1.model_validate(
            {**_receipt(), "revision": 5}
        )
    with pytest.raises(ValidationError):
        ReelsFactoryProgressReceiptV1.model_validate(
            {**_receipt(), "provider_mode": "real"}
        )


@pytest.mark.parametrize(
    "attempts",
    [
        {"script": 1, "image": 1, "voice": 1},
        {"script": 1, "image": 1, "voice": 1, "render": 0, "retry": 0},
        {"script": 1, "image": 1, "voice": 1, "render": -1},
        {"script": True, "image": 1, "voice": 1, "render": 0},
    ],
)
def test_progress_attempts_are_exact_nonnegative_integers(attempts) -> None:
    with pytest.raises(ValidationError):
        ReelsFactoryProgressReceiptV1.model_validate(
            _receipt(provider_attempts=attempts)
        )
