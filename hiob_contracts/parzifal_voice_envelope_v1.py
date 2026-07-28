"""Minimal Parzifal identity + voice handoff for Orpheus."""

from __future__ import annotations

from typing import Any, Literal, Mapping

from pydantic import BaseModel, model_validator

from .ares_script_revision_v1 import (
    DigestStr,
    NonBlankStr,
    _FROZEN_STRICT,
    canonical_contract_digest_v1,
)
from .character_identity_v1 import character_identity_binding_errors_v1

_DIGEST_FIELDS = (
    "contract_version",
    "workspace_id",
    "run_id",
    "subject_id",
    "face_id",
    "voice_id",
    "identity_binding_digest",
    "voice_spec_digest",
)


def derive_parzifal_voice_envelope_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    data = (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else dict(value)
    )
    return canonical_contract_digest_v1(
        {field: data[field] for field in _DIGEST_FIELDS if field in data}
    )


class ParzifalVoiceEnvelopeV1(BaseModel):
    """One sealed character voice. No prompt, DB state, or provider authority."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["ParzifalVoiceEnvelope.v1"]
    workspace_id: NonBlankStr
    run_id: NonBlankStr
    subject_id: NonBlankStr
    face_id: NonBlankStr
    voice_id: NonBlankStr
    identity_binding_digest: DigestStr
    voice_spec_digest: DigestStr
    envelope_digest: DigestStr

    @model_validator(mode="after")
    def _digest_matches_content(self) -> "ParzifalVoiceEnvelopeV1":
        binding_errors = character_identity_binding_errors_v1(
            subject_id=self.subject_id,
            face_id=self.face_id,
            voice_id=self.voice_id,
            identity_binding_digest=self.identity_binding_digest,
        )
        if binding_errors:
            raise ValueError(binding_errors[0])
        expected = derive_parzifal_voice_envelope_digest_v1(self)
        if self.envelope_digest != expected:
            raise ValueError(
                "envelope_digest does not match Parzifal voice envelope content"
            )
        return self


__all__ = [
    "ParzifalVoiceEnvelopeV1",
    "derive_parzifal_voice_envelope_digest_v1",
]
