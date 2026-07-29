"""Exact provider input emitted by ``ares.script.prepare_generation``."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Mapping

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from ...ares_script_revision_v1 import (
    _FROZEN_STRICT,
)
from ...character_identity_v1 import (
    character_identity_binding_errors_v1,
)
from ...factory import sha256_digest
from ...voice_spec_v1 import derive_voice_spec_digest_v1


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


def _valid_unicode_scalars(value: str) -> str:
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValueError("text must contain valid Unicode scalar values")
    return value


def _assert_json_unicode_scalars(value: Any) -> None:
    if isinstance(value, str):
        _valid_unicode_scalars(value)
    elif isinstance(value, Mapping):
        for key, item in value.items():
            _valid_unicode_scalars(str(key))
            _assert_json_unicode_scalars(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_json_unicode_scalars(item)


Text80 = Annotated[
    str,
    StringConstraints(min_length=1, max_length=80, pattern=r"\S"),
    AfterValidator(_valid_unicode_scalars),
]
Text120 = Annotated[
    str,
    StringConstraints(min_length=1, max_length=120, pattern=r"\S"),
    AfterValidator(_valid_unicode_scalars),
]
Text128 = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128, pattern=r"\S"),
    AfterValidator(_valid_unicode_scalars),
]
Text200 = Annotated[
    str,
    StringConstraints(min_length=1, max_length=200, pattern=r"\S"),
    AfterValidator(_valid_unicode_scalars),
]
Text256 = Annotated[
    str,
    StringConstraints(min_length=1, max_length=256, pattern=r"\S"),
    AfterValidator(_valid_unicode_scalars),
]
Text300 = Annotated[
    str,
    StringConstraints(min_length=1, max_length=300, pattern=r"\S"),
    AfterValidator(_valid_unicode_scalars),
]
Text500 = Annotated[
    str,
    StringConstraints(min_length=1, max_length=500, pattern=r"\S"),
    AfterValidator(_valid_unicode_scalars),
]
Text512 = Annotated[
    str,
    StringConstraints(min_length=1, max_length=512, pattern=r"\S"),
    AfterValidator(_valid_unicode_scalars),
]
DigestText = Annotated[
    str,
    StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$"),
]


def derive_ares_script_generation_input_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    """Bind the complete bounded context and exclude only its own digest."""

    data = (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else dict(value)
    )
    body = {field: data[field] for field in _DIGEST_FIELDS}
    _assert_json_unicode_scalars(body)
    return sha256_digest(body)


class AresCharacterIdentityProjectionV1(BaseModel):
    """The face and voice identity projection Ares is allowed to consume."""

    model_config = _FROZEN_STRICT

    persona_id: Text128
    face_id: Text256
    voice_id: Text256
    identity_binding_digest: DigestText

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

    text: Text500
    provenance: Text200


class AresVoiceSpecProjectionV1(BaseModel):
    """The exact VoiceSpec fields Ares passes to its provider."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["VoiceSpec.v1"]
    subject_id: Text128
    rhythm: Text300
    vocabulary: tuple[Text80, ...] = Field(max_length=12)
    forbidden_phrases: tuple[Text120, ...] = Field(max_length=12)
    approved_examples: tuple[Text500, ...] = Field(
        min_length=3,
        max_length=5,
    )
    voice_spec_digest: DigestText

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
    def _bind_voice_spec(self) -> "AresVoiceSpecProjectionV1":
        if self.voice_spec_digest != derive_voice_spec_digest_v1(self):
            raise ValueError(
                "voice_spec_digest does not match VoiceSpec content"
            )
        return self


class AresScriptGenerationInputV1(BaseModel):
    """The only payload Ares permits the script provider to receive."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresScriptGenerationInput.v1"]
    workspace_id: Text512
    run_id: Text512
    script_revision_id: Text512
    plan_revision_id: Text512
    factory_revision: int = Field(
        ge=0,
        le=2_147_483_647,
        strict=True,
    )
    character_lock: AresCharacterIdentityProjectionV1
    voice_spec: AresVoiceSpecProjectionV1
    current_character: Text500
    conflict: Text500
    adjacent_beat_summaries: tuple[Text300, ...] = Field(max_length=2)
    memories: tuple[AresProvenanceMemoryV1, ...] = Field(
        max_length=3,
    )
    generation_input_digest: DigestText

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
    "AresVoiceSpecProjectionV1",
    "AresScriptGenerationInputV1",
    "derive_ares_script_generation_input_digest_v1",
]
