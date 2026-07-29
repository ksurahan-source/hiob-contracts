"""Durable non-terminal receipt for one asynchronous Reels factory run."""

from __future__ import annotations

from typing import Literal, Mapping, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ares_script_revision_v1 import (
    DigestStr,
    NonBlankStr,
    UuidStr,
    canonical_contract_digest_v1,
)


_STRICT_FROZEN = ConfigDict(
    extra="forbid",
    frozen=True,
    strict=True,
    revalidate_instances="always",
)


class ReelsFactoryProviderAttemptsV1(BaseModel):
    """Exact paid-attempt ledger; retries and fallback have no field."""

    model_config = _STRICT_FROZEN

    script: int = Field(ge=0)
    image: int = Field(ge=0)
    voice: int = Field(ge=0)
    render: int = Field(ge=0)


def derive_reels_factory_progress_receipt_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    data = (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else dict(value)
    )
    data.pop("receipt_digest", None)
    return canonical_contract_digest_v1(data)


class ReelsFactoryProgressReceiptV1(BaseModel):
    """Persisted proof that work is queued or running, never final success."""

    model_config = _STRICT_FROZEN

    contract_version: Literal["ReelsFactoryProgressReceipt.v1"]
    run_id: UuidStr
    idempotency_key: NonBlankStr
    revision: int = Field(ge=1)
    stage: Literal["script", "image", "voice", "render"]
    provider_attempts: ReelsFactoryProviderAttemptsV1
    receipt_digest: DigestStr

    @model_validator(mode="after")
    def _digest_matches_payload(self) -> "ReelsFactoryProgressReceiptV1":
        if (
            self.receipt_digest
            != derive_reels_factory_progress_receipt_digest_v1(self)
        ):
            raise ValueError("receipt_digest does not match progress payload")
        return self


__all__ = [
    "ReelsFactoryProgressReceiptV1",
    "ReelsFactoryProviderAttemptsV1",
    "derive_reels_factory_progress_receipt_digest_v1",
]
