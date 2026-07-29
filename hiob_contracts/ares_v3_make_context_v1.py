"""Atomic, server-owned make context for one Ares V3 command."""

from __future__ import annotations

from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field, model_validator

from .ares_script_revision_v1 import (
    DigestStr,
    NonBlankStr,
    UuidStr,
    _FROZEN_STRICT,
)
from .brand_scope import CanonicalBrandSlug, canonical_brand_slug
from .factory import sha256_digest


_DIGEST_FIELDS = (
    "workspace_id",
    "run_id",
    "brand_slug",
    "subject_id",
    "product_id",
    "character_lock_digest",
    "character_lock_version",
    "product_lock_digest",
    "artemis_approval_receipt_id",
    "artemis_approval_receipt_digest",
    "artemis_approval_state_revision",
)


def derive_ares_v3_make_context_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    """Digest the ready snapshot without command execution identifiers."""

    data = (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else dict(value)
    )
    payload = {field: data[field] for field in _DIGEST_FIELDS}
    payload["brand_slug"] = canonical_brand_slug(payload["brand_slug"])
    return sha256_digest(payload)


class AresV3MakeContextV1(BaseModel):
    """The only public make-readiness contract used by Star."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AresV3MakeContext.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    brand_slug: CanonicalBrandSlug
    subject_id: NonBlankStr
    product_id: NonBlankStr
    character_lock_digest: DigestStr
    character_lock_version: int = Field(
        gt=0,
        le=9_007_199_254_740_991,
        strict=True,
    )
    product_lock_digest: DigestStr
    artemis_approval_receipt_id: NonBlankStr
    artemis_approval_receipt_digest: DigestStr
    artemis_approval_state_revision: int = Field(
        gt=0,
        le=9_007_199_254_740_991,
        strict=True,
    )
    make_context_digest: DigestStr

    @model_validator(mode="after")
    def _bind_make_context(self) -> "AresV3MakeContextV1":
        if (
            self.make_context_digest
            != derive_ares_v3_make_context_digest_v1(self)
        ):
            raise ValueError(
                "make_context_digest does not match server make context"
            )
        return self


__all__ = [
    "AresV3MakeContextV1",
    "derive_ares_v3_make_context_digest_v1",
]
