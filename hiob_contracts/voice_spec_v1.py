"""Small, immutable Parzifal-owned voice specification."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Mapping

from pydantic import BaseModel, Field, field_validator, model_validator

from .ares_script_revision_v1 import (
    DigestStr,
    NonBlankStr,
    _FROZEN_STRICT,
    canonical_contract_digest_v1,
)


def _voice_spec_payload_v1(value: Mapping[str, Any] | BaseModel) -> dict[str, Any]:
    data = (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else dict(value)
    )
    return {
        key: data[key]
        for key in (
            "contract_version",
            "subject_id",
            "rhythm",
            "vocabulary",
            "forbidden_phrases",
            "approved_examples",
        )
        if key in data
    }


def derive_voice_spec_digest_v1(value: Mapping[str, Any] | BaseModel) -> str:
    return canonical_contract_digest_v1(_voice_spec_payload_v1(value))


class VoiceSpecV1(BaseModel):
    """Bounded style evidence. Parzifal produces it; Ares only consumes it."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["VoiceSpec.v1"] = "VoiceSpec.v1"
    subject_id: Annotated[NonBlankStr, Field(max_length=128)]
    rhythm: Annotated[NonBlankStr, Field(max_length=300)]
    vocabulary: tuple[
        Annotated[NonBlankStr, Field(max_length=80)], ...
    ] = Field(max_length=12)
    forbidden_phrases: tuple[
        Annotated[NonBlankStr, Field(max_length=120)], ...
    ] = Field(max_length=12)
    approved_examples: tuple[
        Annotated[NonBlankStr, Field(max_length=500)], ...
    ] = Field(min_length=3, max_length=5)
    voice_spec_digest: DigestStr

    @field_validator(
        "vocabulary",
        "forbidden_phrases",
        "approved_examples",
        mode="before",
    )
    @classmethod
    def _tuples(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _digest_matches_content(self) -> "VoiceSpecV1":
        expected = derive_voice_spec_digest_v1(self)
        if self.voice_spec_digest != expected:
            raise ValueError("voice_spec_digest does not match VoiceSpec content")
        return self


__all__ = ["VoiceSpecV1", "derive_voice_spec_digest_v1"]
