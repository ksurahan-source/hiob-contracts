"""Typed, immutable Parzifal identity authority for the V3 JKPA seam.

The durable record remains Parzifal-owned: this module validates its immutable
value shape and digest, but does not resolve or authorize a record.  The
five-field material wrapper is deliberately exact because Star persists the
record reference separately and sends only this material through PlanetOutput.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Annotated, Literal, Mapping

from pydantic import (
    AfterValidator,
    BaseModel,
    field_serializer,
    field_validator,
    model_validator,
)

from .ares_create_script_v2 import AresIdentitySealedV2
from .ares_script_revision_v1 import (
    DigestStr,
    _FROZEN_STRICT,
    _deep_freeze_json,
    _json_value,
    _validate_json,
)
from .character_lock_v1 import PositiveVersion
from .factory.digest import sha256_digest


_RECORD_FIELDS = (
    "id",
    "version",
    "workspace_id",
    "run_id",
    "status",
    "emitted_at",
    "identity_lock",
    "master_sheet",
    "cast_sheets",
)
_UTC_OFFSET_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?\+00:00$"
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


def _canonical_text(value: str) -> str:
    normalized = _normalize_unicode_scalars(value).strip()
    if not normalized:
        raise ValueError("string must not be blank")
    return normalized


def _canonical_utc_offset_timestamp(value: str) -> str:
    normalized = _canonical_text(value)
    source = normalized[:-1] + "+00:00" if normalized.endswith("Z") else normalized
    if _UTC_OFFSET_TIMESTAMP_RE.fullmatch(source) is None:
        raise ValueError("timestamp must be an ISO-8601 UTC value")
    try:
        parsed = datetime.fromisoformat(source)
    except ValueError as exc:
        raise ValueError("timestamp must be an ISO-8601 UTC value") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("timestamp must be UTC")
    return parsed.astimezone(timezone.utc).isoformat()


CanonicalText = Annotated[str, AfterValidator(_canonical_text)]
CanonicalUtcOffsetTimestamp = Annotated[
    str, AfterValidator(_canonical_utc_offset_timestamp)
]


def _mapping_data(value: Mapping[str, Any] | BaseModel) -> dict[str, Any]:
    return (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else dict(value)
    )


def _record_digest_payload(
    value: Mapping[str, Any] | BaseModel,
) -> dict[str, Any]:
    data = _mapping_data(value)
    try:
        record = {field: data[field] for field in _RECORD_FIELDS}
    except KeyError as exc:
        raise ValueError(f"record is missing {exc.args[0]}") from exc
    if isinstance(record["version"], bool) or not isinstance(record["version"], int):
        raise ValueError("version must be a positive integer")
    if record["version"] < 1:
        raise ValueError("version must be a positive integer")
    if record["status"] not in {"approved", "sealed"}:
        raise ValueError("status must be approved or sealed")
    documents: dict[str, Any] = {}
    for field in ("identity_lock", "master_sheet", "cast_sheets"):
        raw = record[field]
        if not isinstance(raw, Mapping):
            raise ValueError(f"{field} must be a JSON object")
        _validate_json(raw, field)
        documents[field] = _json_value(raw)
    return {
        "contract_version": "ParzifalIdentityAuthorityRecord.v1",
        "id": _canonical_text(record["id"]),
        "version": record["version"],
        "workspace_id": _canonical_text(record["workspace_id"]),
        "run_id": _canonical_text(record["run_id"]),
        "status": record["status"],
        "emitted_at": _canonical_utc_offset_timestamp(record["emitted_at"]),
        **documents,
    }


def derive_parzifal_identity_authority_record_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    """Digest exactly one durable Parzifal identity record.

    The preimage intentionally matches the existing producer-owned
    ``ParzifalIdentityAuthorityRecord.v1`` record digest.  A digest validates
    content consistency only; consumers still resolve the referenced record
    through Parzifal's durable authority port.
    """

    return sha256_digest(_record_digest_payload(value))


class ParzifalIdentityRecordRefV1(BaseModel):
    """The exact three-field opaque reference accepted by ``identity.seal``."""

    model_config = _FROZEN_STRICT

    id: CanonicalText
    version: PositiveVersion
    digest: DigestStr


class ParzifalIdentityAuthorityRecordV1(BaseModel):
    """One immutable Parzifal-owned record behind an identity authority ref."""

    model_config = _FROZEN_STRICT

    id: CanonicalText
    version: PositiveVersion
    digest: DigestStr
    workspace_id: CanonicalText
    run_id: CanonicalText
    status: Literal["approved", "sealed"]
    emitted_at: CanonicalUtcOffsetTimestamp
    identity_lock: Mapping[str, Any]
    master_sheet: Mapping[str, Any]
    cast_sheets: Mapping[str, Any]

    @field_validator(
        "identity_lock",
        "master_sheet",
        "cast_sheets",
        mode="after",
    )
    @classmethod
    def _freeze_documents(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        _validate_json(value, "Parzifal identity authority record")
        frozen = _deep_freeze_json(value)
        if not isinstance(frozen, Mapping):  # defensive: input annotation is Mapping
            raise ValueError("identity authority document must be a JSON object")
        return frozen

    @field_serializer(
        "identity_lock", "master_sheet", "cast_sheets", when_used="always"
    )
    def _serialize_documents(self, value: Mapping[str, Any]) -> dict[str, Any]:
        rendered = _json_value(value)
        if not isinstance(rendered, dict):  # defensive: frozen mappings serialize as dicts
            raise TypeError("identity authority document must serialize as an object")
        return rendered

    @model_validator(mode="after")
    def _bind_record_digest(self) -> "ParzifalIdentityAuthorityRecordV1":
        if self.digest != derive_parzifal_identity_authority_record_digest_v1(self):
            raise ValueError("digest does not match Parzifal identity authority record")
        return self


def derive_parzifal_identity_authority_material_payload_digest_v1(
    value: Mapping[str, Any] | AresIdentitySealedV2,
) -> str:
    """Digest the exact fully-populated Ares identity payload in the wrapper."""

    sealed = (
        value
        if isinstance(value, AresIdentitySealedV2)
        else AresIdentitySealedV2.model_validate(value)
    )
    return sha256_digest(sealed.model_dump(mode="json"))


class ParzifalIdentityAuthorityMaterialV1(BaseModel):
    """Exact five-field output of ``parzifal.identity.seal``.

    This is evidence, not bearer authority.  Star must separately retain the
    request's :class:`ParzifalIdentityRecordRefV1` and resolve current durable
    state before it treats this wrapper as an authority input.
    """

    model_config = _FROZEN_STRICT

    artifact_type: Literal["identity_lock"]
    artifact_digest: DigestStr
    payload_digest: DigestStr
    receipt_id: CanonicalText
    sealed_payload: AresIdentitySealedV2

    @field_validator("sealed_payload", mode="after")
    @classmethod
    def _require_fully_sealed_speakers(
        cls, value: AresIdentitySealedV2
    ) -> AresIdentitySealedV2:
        for speaker in value.speakers:
            if (
                speaker.face_id is None
                or speaker.voice_id is None
                or speaker.identity_binding_digest is None
            ):
                raise ValueError(
                    "sealed_payload speakers must include face_id, voice_id, "
                    "and identity_binding_digest"
                )
        return value

    @model_validator(mode="after")
    def _bind_material(self) -> "ParzifalIdentityAuthorityMaterialV1":
        if self.artifact_digest != self.sealed_payload.identity_lock_digest:
            raise ValueError("artifact_digest must equal sealed identity_lock_digest")
        expected = derive_parzifal_identity_authority_material_payload_digest_v1(
            self.sealed_payload
        )
        if self.payload_digest != expected:
            raise ValueError("payload_digest does not match sealed_payload")
        return self


__all__ = [
    "ParzifalIdentityRecordRefV1",
    "ParzifalIdentityAuthorityRecordV1",
    "ParzifalIdentityAuthorityMaterialV1",
    "derive_parzifal_identity_authority_record_digest_v1",
    "derive_parzifal_identity_authority_material_payload_digest_v1",
]
