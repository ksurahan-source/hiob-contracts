"""Exact provider input emitted by ``ares.script.prepare_generation``."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Mapping

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
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
from ...brand_scope import is_contract_blank
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


def _contract_nonblank(value: str) -> str:
    if is_contract_blank(value):
        raise ValueError("string must not be blank")
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


_CONTRACT_NONBLANK_PATTERN = (
    "[^\u0009-\u000D\u0020\u00A0\u1680"
    "\u2000-\u200A\u2028\u2029\u202F\u205F\u3000\uFEFF]"
)

Text80 = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=80,
        pattern=_CONTRACT_NONBLANK_PATTERN,
    ),
    AfterValidator(_contract_nonblank),
    AfterValidator(_valid_unicode_scalars),
]
Text120 = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=120,
        pattern=_CONTRACT_NONBLANK_PATTERN,
    ),
    AfterValidator(_contract_nonblank),
    AfterValidator(_valid_unicode_scalars),
]
Text128 = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=_CONTRACT_NONBLANK_PATTERN,
    ),
    AfterValidator(_contract_nonblank),
    AfterValidator(_valid_unicode_scalars),
]
Text200 = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=200,
        pattern=_CONTRACT_NONBLANK_PATTERN,
    ),
    AfterValidator(_contract_nonblank),
    AfterValidator(_valid_unicode_scalars),
]
Text256 = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=256,
        pattern=_CONTRACT_NONBLANK_PATTERN,
    ),
    AfterValidator(_contract_nonblank),
    AfterValidator(_valid_unicode_scalars),
]
Text300 = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=300,
        pattern=_CONTRACT_NONBLANK_PATTERN,
    ),
    AfterValidator(_contract_nonblank),
    AfterValidator(_valid_unicode_scalars),
]
Text500 = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=500,
        pattern=_CONTRACT_NONBLANK_PATTERN,
    ),
    AfterValidator(_contract_nonblank),
    AfterValidator(_valid_unicode_scalars),
]
Text512 = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=512,
        pattern=_CONTRACT_NONBLANK_PATTERN,
    ),
    AfterValidator(_contract_nonblank),
    AfterValidator(_valid_unicode_scalars),
]
DigestText = Annotated[
    str,
    StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$"),
]
_FACTORY_REVISION_INTEGER_ERROR = "factory_revision must be an integer"


def _normalize_factory_revision(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError(_FACTORY_REVISION_INTEGER_ERROR)
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError(_FACTORY_REVISION_INTEGER_ERROR)
        value = int(value)
    if not isinstance(value, int):
        raise ValueError(_FACTORY_REVISION_INTEGER_ERROR)
    if not 0 <= value <= 2_147_483_647:
        raise ValueError("factory_revision must be an int4 value")
    return value


def derive_ares_script_generation_input_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    """Bind the complete bounded context and exclude only its own digest."""

    data = (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else dict(value)
    )
    for field in _DIGEST_FIELDS:
        if field not in data:
            raise ValueError(
                f"{field} is required for generation input digest"
            )
    data["factory_revision"] = _normalize_factory_revision(
        data["factory_revision"]
    )
    body = {field: data[field] for field in _DIGEST_FIELDS}
    _assert_json_unicode_scalars(body)
    return sha256_digest(body)


def _semantic_model_config(*invariants: str) -> ConfigDict:
    return ConfigDict(
        **_FROZEN_STRICT,
        json_schema_extra={
            "x-hiob-validation": "pydantic-runtime-required",
            "x-hiob-semantic-invariants": list(invariants),
        },
    )


class AresCharacterIdentityProjectionV1(BaseModel):
    """The face and voice identity projection Ares is allowed to consume."""

    model_config = _semantic_model_config(
        "character_identity_binding_digest",
        "valid_unicode_scalars",
    )

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

    model_config = _semantic_model_config("valid_unicode_scalars")

    text: Text500
    provenance: Text200


class AresVoiceSpecProjectionV1(BaseModel):
    """The exact VoiceSpec fields Ares passes to its provider."""

    model_config = _semantic_model_config(
        "voice_spec_digest",
        "valid_unicode_scalars",
    )

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

    model_config = _semantic_model_config(
        "character_identity_binding_digest",
        "voice_spec_subject_matches_character",
        "voice_spec_digest",
        "generation_input_digest",
        "valid_unicode_scalars",
    )

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

    @field_validator("factory_revision", mode="before")
    @classmethod
    def _json_integer_parity(cls, value: Any) -> Any:
        return _normalize_factory_revision(value)

    @field_validator(
        "adjacent_beat_summaries",
        "memories",
        mode="before",
    )
    @classmethod
    def _tuples(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    def model_copy(
        self,
        *,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> "AresScriptGenerationInputV1":
        if not update:
            return super().model_copy(deep=deep)
        body = self.model_dump(mode="json")
        body.update(update)
        return type(self).model_validate(body, strict=True)

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
