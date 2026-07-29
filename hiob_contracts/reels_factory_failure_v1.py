"""Durable terminal failure proof for one Reels factory operation."""

from __future__ import annotations

from typing import Any, Literal, Mapping

from pydantic import BaseModel, model_validator

from .ares_script_revision_v1 import DigestStr, NonBlankStr, UuidStr
from .reels_factory_progress_v1 import (
    ReelsFactoryProviderAttemptsV1,
    _STRICT_FROZEN,
)
from .ares_script_revision_v1 import canonical_contract_digest_v1


def derive_reels_factory_failure_receipt_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    data = (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else dict(value)
    )
    data.pop("receipt_digest", None)
    return canonical_contract_digest_v1(data)


class ReelsFactoryFailureReceiptV1(BaseModel):
    """Terminal state with explicit paid-side-effect certainty."""

    model_config = _STRICT_FROZEN

    contract_version: Literal["ReelsFactoryFailureReceipt.v1"]
    run_id: UuidStr
    idempotency_key: NonBlankStr
    revision: int
    stage: Literal[
        "authority",
        "script",
        "project_script",
        "plan",
        "project_plan",
        "scheduler",
        "image",
        "voice",
        "render",
    ]
    code: NonBlankStr
    provider_call: Literal["none", "confirmed", "unknown"]
    provider_attempts: ReelsFactoryProviderAttemptsV1
    receipt_digest: DigestStr

    @model_validator(mode="after")
    def _bind_terminal_payload(self) -> "ReelsFactoryFailureReceiptV1":
        if self.revision < 1:
            raise ValueError("revision must be positive")
        if (
            self.receipt_digest
            != derive_reels_factory_failure_receipt_digest_v1(self)
        ):
            raise ValueError("receipt_digest does not match failure payload")
        return self


__all__ = [
    "ReelsFactoryFailureReceiptV1",
    "derive_reels_factory_failure_receipt_digest_v1",
]
