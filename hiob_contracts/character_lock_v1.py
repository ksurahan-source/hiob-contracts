"""Reusable Star-owned face and voice lock."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ares_script_revision_v1 import DigestStr, NonBlankStr
from .factory.digest import sha256_digest

_STRICT_FROZEN = ConfigDict(
    extra="forbid",
    frozen=True,
    strict=True,
    revalidate_instances="always",
)
UuidStr = Annotated[
    str,
    Field(
        pattern=(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
            r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        ),
        strict=True,
    ),
]
PositiveVersion = Annotated[
    int,
    Field(gt=0, le=9_007_199_254_740_991, strict=True),
]

_DIGEST_FIELDS = (
    "contract_version",
    "workspace_id",
    "brand_id",
    "subject_id",
    "version",
    "face_id",
    "voice_id",
    "source_receipt_ref",
    "source_record_version",
    "source_receipt_digest",
)


def _normalize_unicode_scalars(value: str) -> str:
    normalized: list[str] = []
    index = 0
    while index < len(value):
        code = ord(value[index])
        if 0xD800 <= code <= 0xDBFF:
            if index + 1 >= len(value):
                raise ValueError("text must contain valid Unicode scalar values")
            low = ord(value[index + 1])
            if not 0xDC00 <= low <= 0xDFFF:
                raise ValueError("text must contain valid Unicode scalar values")
            normalized.append(
                chr(0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00))
            )
            index += 2
            continue
        if 0xDC00 <= code <= 0xDFFF:
            raise ValueError("text must contain valid Unicode scalar values")
        normalized.append(value[index])
        index += 1
    return "".join(normalized)


def derive_character_lock_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    """Bind one immutable scope, identity pair, version, and source receipt."""

    data = (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else dict(value)
    )
    payload = {field: data[field] for field in _DIGEST_FIELDS}
    for field, item in payload.items():
        if isinstance(item, str):
            payload[field] = _normalize_unicode_scalars(item)
    return sha256_digest(payload)


class CharacterLockV1(BaseModel):
    """Append-only reusable identity owned by Star, never by a run."""

    model_config = _STRICT_FROZEN

    contract_version: Literal["CharacterLock.v1"]
    workspace_id: UuidStr
    brand_id: UuidStr
    subject_id: NonBlankStr
    version: PositiveVersion
    face_id: NonBlankStr
    voice_id: NonBlankStr
    source_receipt_ref: NonBlankStr
    source_record_version: PositiveVersion
    source_receipt_digest: DigestStr
    digest: DigestStr

    @field_validator(
        "subject_id",
        "face_id",
        "voice_id",
        "source_receipt_ref",
        mode="after",
    )
    @classmethod
    def _valid_unicode(cls, value: str) -> str:
        return _normalize_unicode_scalars(value)

    @model_validator(mode="after")
    def _validate_digest(self) -> "CharacterLockV1":
        if self.digest != derive_character_lock_digest_v1(self):
            raise ValueError("digest does not match CharacterLock payload")
        return self


__all__ = ["CharacterLockV1", "derive_character_lock_digest_v1"]
