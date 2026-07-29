"""Parzifal acceptance receipt bound to one exact face and voice."""

from __future__ import annotations

from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, model_validator

from .ares_script_revision_v1 import DigestStr, NonBlankStr, UuidStr
from .brand_scope import CanonicalBrandSlug, canonical_brand_slug
from .character_lock_v1 import PositiveVersion
from .factory.digest import sha256_digest


_DIGEST_FIELDS = (
    "contract_version",
    "workspace_id",
    "brand_slug",
    "subject_id",
    "source_receipt_ref",
    "source_record_version",
    "state",
    "face_id",
    "voice_id",
)


def derive_accepted_identity_receipt_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    data = (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else dict(value)
    )
    payload = {field: data[field] for field in _DIGEST_FIELDS}
    payload["brand_slug"] = canonical_brand_slug(payload["brand_slug"])
    return sha256_digest(payload)


class AcceptedIdentityReceiptV1(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )

    contract_version: Literal["AcceptedIdentityReceipt.v1"]
    workspace_id: UuidStr
    brand_slug: CanonicalBrandSlug
    subject_id: NonBlankStr
    source_receipt_ref: NonBlankStr
    source_record_version: PositiveVersion
    state: Literal["accepted"]
    face_id: NonBlankStr
    voice_id: NonBlankStr
    receipt_digest: DigestStr

    @model_validator(mode="after")
    def _bind_identity(self) -> "AcceptedIdentityReceiptV1":
        if (
            self.receipt_digest
            != derive_accepted_identity_receipt_digest_v1(self)
        ):
            raise ValueError(
                "receipt_digest does not match accepted identity"
            )
        return self


__all__ = [
    "AcceptedIdentityReceiptV1",
    "derive_accepted_identity_receipt_digest_v1",
]
