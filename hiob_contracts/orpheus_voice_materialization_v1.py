"""Private provider input for one sealed Orpheus voice materialization."""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal, Mapping

from pydantic import AfterValidator, BaseModel, model_validator

from .ares_script_revision_v1 import (
    DigestStr,
    NonBlankStr,
    NonNegativeInt,
    _FROZEN_STRICT,
    canonical_contract_digest_v1,
)
from .factory.digest import sha256_digest


_INPUT_DIGEST_FIELDS = (
    "contract_version",
    "workspace_id",
    "run_id",
    "beat_index",
    "source_text",
    "source_text_digest",
    "voice_id",
    "voice_receipt",
    "voice_receipt_digest",
)
ORPHEUS_VOICE_SOURCE_TEXT_MAX_CHARS_V1 = 48
ORPHEUS_VOICE_SOURCE_TEXT_MAX_UTF8_BYTES_V1 = 144
_TYPECAST_PROVIDER_VOICE_ID = re.compile(
    r"^(?:tc|uc)_[0-9a-f]{24}$"
)


def _as_json_dict(value: Mapping[str, Any] | BaseModel) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return dict(value)


def _sealed_provider_voice_id(value: str) -> str:
    if _TYPECAST_PROVIDER_VOICE_ID.fullmatch(value) is None:
        raise ValueError("voice_id must be a sealed provider identity")
    return value


def _bounded_source_text(value: str) -> str:
    if len(value) > ORPHEUS_VOICE_SOURCE_TEXT_MAX_CHARS_V1:
        raise ValueError(
            "source_text must be at most 48 Unicode characters"
        )
    if (
        len(value.encode("utf-8"))
        > ORPHEUS_VOICE_SOURCE_TEXT_MAX_UTF8_BYTES_V1
    ):
        raise ValueError("source_text must be at most 144 UTF-8 bytes")
    return value


SealedProviderVoiceId = Annotated[
    NonBlankStr,
    AfterValidator(_sealed_provider_voice_id),
]
BoundedVoiceSourceText = Annotated[
    NonBlankStr,
    AfterValidator(_bounded_source_text),
]


class _OrpheusVoiceReceiptV1(BaseModel):
    """Typed view of the existing receipt; its public JSON shape is unchanged."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["OrpheusVoiceReceipt.v1"]
    workspace_id: NonBlankStr
    run_id: NonBlankStr
    subject_id: NonBlankStr
    voice_id: SealedProviderVoiceId
    beat_index: NonNegativeInt
    source: Literal["sealed"]
    beat_plan_revision_digest: DigestStr
    identity_binding_digest: DigestStr
    voice_spec_digest: DigestStr
    voice_envelope_digest: DigestStr
    source_text_digest: DigestStr
    receipt_digest: DigestStr

    @model_validator(mode="after")
    def _receipt_digest_matches(self) -> "_OrpheusVoiceReceiptV1":
        expected = canonical_contract_digest_v1(
            self,
            exclude={"receipt_digest"},
        )
        if self.receipt_digest != expected:
            raise ValueError(
                "receipt_digest does not match OrpheusVoiceReceipt.v1"
            )
        return self


def derive_orpheus_voice_materialization_input_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    """Bind the exact text, voice, beat, scope, and existing voice receipt."""

    data = _as_json_dict(value)
    return canonical_contract_digest_v1(
        {
            field: data[field]
            for field in _INPUT_DIGEST_FIELDS
            if field in data
        }
    )


class OrpheusVoiceMaterializationInputV1(BaseModel):
    """One provider-call input with no database lookup or voice reselection."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["OrpheusVoiceMaterializationInput.v1"]
    workspace_id: NonBlankStr
    run_id: NonBlankStr
    beat_index: NonNegativeInt
    source_text: BoundedVoiceSourceText
    source_text_digest: DigestStr
    voice_id: SealedProviderVoiceId
    voice_receipt: _OrpheusVoiceReceiptV1
    voice_receipt_digest: DigestStr
    input_digest: DigestStr

    @model_validator(mode="after")
    def _authority_matches(self) -> "OrpheusVoiceMaterializationInputV1":
        receipt = self.voice_receipt
        expected_source_digest = sha256_digest(
            {"source_text": self.source_text}
        )
        if self.source_text_digest != expected_source_digest:
            raise ValueError(
                "source_text_digest does not match exact source_text"
            )
        if (
            receipt.workspace_id != self.workspace_id
            or receipt.run_id != self.run_id
            or receipt.beat_index != self.beat_index
        ):
            raise ValueError(
                "voice receipt scope or beat does not match materialization input"
            )
        if receipt.voice_id != self.voice_id:
            raise ValueError(
                "voice_id does not match sealed Orpheus voice receipt"
            )
        if receipt.source_text_digest != self.source_text_digest:
            raise ValueError(
                "source_text_digest does not match Orpheus voice receipt"
            )
        if receipt.receipt_digest != self.voice_receipt_digest:
            raise ValueError(
                "voice_receipt_digest does not match Orpheus voice receipt"
            )
        expected_input_digest = (
            derive_orpheus_voice_materialization_input_digest_v1(self)
        )
        if self.input_digest != expected_input_digest:
            raise ValueError(
                "input_digest does not match voice materialization input"
            )
        return self


__all__ = [
    "ORPHEUS_VOICE_SOURCE_TEXT_MAX_CHARS_V1",
    "ORPHEUS_VOICE_SOURCE_TEXT_MAX_UTF8_BYTES_V1",
    "OrpheusVoiceMaterializationInputV1",
    "derive_orpheus_voice_materialization_input_digest_v1",
]
