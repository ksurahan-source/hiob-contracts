"""Strict receipt proving one run is ready without a provider call."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ares_script_revision_v1 import DigestStr, NonBlankStr
from .character_identity_v1 import character_identity_binding_errors_v1
from .factory.digest import sha256_digest

_STRICT_FROZEN = ConfigDict(
    extra="forbid",
    frozen=True,
    strict=True,
    revalidate_instances="always",
)
PositiveVersion = Annotated[int, Field(gt=0, strict=True)]

_PARZIFAL_PAYLOAD_FIELDS = (
    "contract_version",
    "receipt_id",
    "workspace_id",
    "run_id",
    "subject_id",
    "face_id",
    "voice_id",
    "identity_binding_digest",
    "element_lock_digest",
)
_MAKE_READY_PAYLOAD_FIELDS = (
    "contract_version",
    "workspace_id",
    "run_id",
    "parzifal_record_ref",
    "parzifal_receipt",
    "current_element_lock_digest",
    "provider_call",
)


def _json_mapping(value: Mapping[str, Any] | BaseModel) -> dict[str, Any]:
    return (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else dict(value)
    )


def _digest_fields(
    value: Mapping[str, Any] | BaseModel,
    fields: tuple[str, ...],
) -> str:
    data = _json_mapping(value)
    return sha256_digest({field: data[field] for field in fields})


def derive_parzifal_identity_receipt_payload_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    """Bind the exact Parzifal identity receipt payload, excluding its digest."""

    return _digest_fields(value, _PARZIFAL_PAYLOAD_FIELDS)


def derive_star_make_ready_receipt_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    """Bind the exact make-ready receipt, excluding its receipt digest."""

    return _digest_fields(value, _MAKE_READY_PAYLOAD_FIELDS)


class ParzifalRecordRefV1(BaseModel):
    model_config = _STRICT_FROZEN

    id: NonBlankStr
    version: PositiveVersion
    digest: DigestStr


class ParzifalIdentityReceiptV1(BaseModel):
    """Server-owned Parzifal authority consumed by Star without reinterpretation."""

    model_config = _STRICT_FROZEN

    contract_version: Literal["ParzifalIdentityReceipt.v1"]
    receipt_id: NonBlankStr
    workspace_id: NonBlankStr
    run_id: NonBlankStr
    subject_id: NonBlankStr
    face_id: NonBlankStr
    voice_id: NonBlankStr
    identity_binding_digest: DigestStr
    element_lock_digest: DigestStr
    payload_digest: DigestStr

    @model_validator(mode="after")
    def _validate_bindings(self) -> "ParzifalIdentityReceiptV1":
        errors = character_identity_binding_errors_v1(
            subject_id=self.subject_id,
            face_id=self.face_id,
            voice_id=self.voice_id,
            identity_binding_digest=self.identity_binding_digest,
        )
        if errors:
            raise ValueError(errors[0])
        expected = derive_parzifal_identity_receipt_payload_digest_v1(self)
        if self.payload_digest != expected:
            raise ValueError(
                "payload_digest does not match Parzifal identity receipt payload"
            )
        return self


class StarMakeReadyReceiptV1(BaseModel):
    """Fail-closed evidence that current server-owned character locks are ready."""

    model_config = _STRICT_FROZEN

    contract_version: Literal["StarMakeReadyReceipt.v1"]
    workspace_id: NonBlankStr
    run_id: NonBlankStr
    parzifal_record_ref: ParzifalRecordRefV1
    parzifal_receipt: ParzifalIdentityReceiptV1
    current_element_lock_digest: DigestStr
    provider_call: Literal["none"]
    receipt_digest: DigestStr

    @model_validator(mode="after")
    def _validate_bindings(self) -> "StarMakeReadyReceiptV1":
        receipt = self.parzifal_receipt
        record_ref = self.parzifal_record_ref
        if receipt.workspace_id != self.workspace_id:
            raise ValueError(
                "parzifal_receipt.workspace_id must match workspace_id"
            )
        if receipt.run_id != self.run_id:
            raise ValueError("parzifal_receipt.run_id must match run_id")
        if record_ref.id != receipt.receipt_id:
            raise ValueError(
                "parzifal_record_ref.id must match parzifal_receipt.receipt_id"
            )
        if record_ref.digest != receipt.payload_digest:
            raise ValueError(
                "parzifal_record_ref.digest must match "
                "parzifal_receipt.payload_digest"
            )
        if self.current_element_lock_digest != receipt.element_lock_digest:
            raise ValueError(
                "current_element_lock_digest must match "
                "parzifal_receipt.element_lock_digest"
            )
        expected = derive_star_make_ready_receipt_digest_v1(self)
        if self.receipt_digest != expected:
            raise ValueError(
                "receipt_digest does not match Star make-ready receipt payload"
            )
        return self


__all__ = [
    "ParzifalIdentityReceiptV1",
    "ParzifalRecordRefV1",
    "StarMakeReadyReceiptV1",
    "derive_parzifal_identity_receipt_payload_digest_v1",
    "derive_star_make_ready_receipt_digest_v1",
]
