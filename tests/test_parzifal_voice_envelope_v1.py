from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    ParzifalVoiceEnvelopeV1,
    derive_parzifal_voice_envelope_digest_v1,
    sha256_digest,
)


def _payload() -> dict:
    return {
        "contract_version": "ParzifalVoiceEnvelope.v1",
        "workspace_id": "ws-1",
        "run_id": "run-1",
        "subject_id": "mom",
        "voice_id": "tc_voice_mom_1",
        "identity_binding_digest": sha256_digest({"identity": "mom"}),
        "voice_spec_digest": sha256_digest({"voice_spec": "mom"}),
    }


def test_voice_envelope_is_frozen_and_digest_sealed() -> None:
    payload = _payload()
    envelope = ParzifalVoiceEnvelopeV1.model_validate(
        {
            **payload,
            "envelope_digest": derive_parzifal_voice_envelope_digest_v1(payload),
        }
    )

    assert envelope.envelope_digest == derive_parzifal_voice_envelope_digest_v1(
        payload
    )
    with pytest.raises(ValidationError):
        envelope.voice_id = "tc_other"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("workspace_id", ""),
        ("run_id", "  "),
        ("subject_id", ""),
        ("voice_id", ""),
        ("identity_binding_digest", "bad"),
        ("voice_spec_digest", "bad"),
    ],
)
def test_voice_envelope_rejects_blank_ids_and_invalid_digests(
    field: str,
    value: str,
) -> None:
    payload = _payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        ParzifalVoiceEnvelopeV1.model_validate(
            {
                **payload,
                "envelope_digest": derive_parzifal_voice_envelope_digest_v1(
                    payload
                ),
            }
        )


def test_voice_envelope_rejects_tampering_under_old_digest() -> None:
    payload = _payload()
    digest = derive_parzifal_voice_envelope_digest_v1(payload)
    payload["voice_id"] = "tc_changed"

    with pytest.raises(ValidationError, match="envelope_digest"):
        ParzifalVoiceEnvelopeV1.model_validate(
            {**payload, "envelope_digest": digest}
        )
