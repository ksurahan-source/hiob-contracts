"""Exact provider input emitted by ``ares.script.prepare_generation``."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Mapping

from pydantic import BaseModel, Field, field_validator, model_validator

from ...ares_script_revision_v1 import (
    DigestStr,
    NonBlankStr,
    _FROZEN_STRICT,
)
from ...character_identity_v1 import (
    character_identity_binding_errors_v1,
)
from ...factory import sha256_digest
from ...voice_spec_v1 import VoiceSpecV1


_DIGEST_FIELDS = (
    "contract_version",
    "workspace_id",
    "run_id",
    "script_revision_id",
    "plan_revision_id",
    "factory_revision",
    "character_lock",
    "voice_spec",
    "current_character",
    "conflict",
    "adjacent_beat_summaries",
    "memories",
)


def derive_ares_script_generation_input_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    """Bind the complete bounded context and exclude only its own digest."""

    data = (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else dict(value)
    )
    return sha256_digest({field: data[field] for field in _DIGEST_FIELDS})


class AresCharacterIdentityProjectionV1(BaseModel):
    """The face and voice identity projection Ares is allowed to consume."""

    model_config = _FROZEN_STRICT

    persona_id: Annotated[NonBlankStr, Field(max_length=128)]
    face_id: Annotated[NonBlankStr, Field(max_length=256)]
    voice_id: Annotated[NonBlankStr, Field(max_length=256)]
    identity_binding_digest: DigestStr

    @model_validator(mode="after")
    def _bind_face_and_voice(self) -> "AresCharacterIdentityProjectionV1":
        errors = character_identity_binding_errors_v1(
            subject_id=self.persona_id,
            face_id=self.face_id,
            voice_id=self.voice_id,
            identity_binding_digest=self.identity_binding_digest,
        )
        if errors:
            raise ValueError(errors[0])
        return self


class AresProvenanceMemoryV1(BaseModel):
    """One bounded memory whose source remains visible."""

    model_config = _FROZEN_STRICT

    text: Annotated[NonBlankStr, Field(max_length=500)]
    provenance: Annotated[NonBlankStr, Field(max_length=200)]


class AresScriptGenerationInputV1(BaseModel):
    """The only payload Ares permits the script provider to receive."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresScriptGenerationInput.v1"]
    workspace_id: NonBlankStr
    run_id: NonBlankStr
    script_revision_id: NonBlankStr
    plan_revision_id: NonBlankStr
    factory_revision: int = Field(
        ge=0,
        le=2_147_483_647,
        strict=True,
    )
    character_lock: AresCharacterIdentityProjectionV1
    voice_spec: VoiceSpecV1
    current_character: Annotated[NonBlankStr, Field(max_length=500)]
    conflict: Annotated[NonBlankStr, Field(max_length=500)]
    adjacent_beat_summaries: tuple[
        Annotated[NonBlankStr, Field(max_length=300)],
        ...,
    ] = Field(default_factory=tuple, max_length=2)
    memories: tuple[AresProvenanceMemoryV1, ...] = Field(
        default_factory=tuple,
        max_length=3,
    )
    generation_input_digest: DigestStr

    @field_validator(
        "adjacent_beat_summaries",
        "memories",
        mode="before",
    )
    @classmethod
    def _tuples(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _bind_scope_and_digest(self) -> "AresScriptGenerationInputV1":
        if self.voice_spec.subject_id != self.character_lock.persona_id:
            raise ValueError(
                "voice_spec.subject_id must match character_lock.persona_id"
            )
        if (
            self.generation_input_digest
            != derive_ares_script_generation_input_digest_v1(self)
        ):
            raise ValueError(
                "generation_input_digest does not match generation input"
            )
        return self


__all__ = [
    "AresCharacterIdentityProjectionV1",
    "AresProvenanceMemoryV1",
    "AresScriptGenerationInputV1",
    "derive_ares_script_generation_input_digest_v1",
]

