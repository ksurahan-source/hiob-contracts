"""Strict first-customer truth-seam contracts (C2-C6, version 2).

Version 2 fixes the identity and validation weaknesses in the overnight v1
helpers:

* one external order has one stable key, independent of payload revisions,
  runs, and attempts; the stored canonical digest decides replay vs conflict;
* every approval/effect/render object is frozen and rejects extra/coerced data;
* paid work carries an explicit currency and spend ceiling;
* a verified render is representable only for QA PASS and an exact byte hash.
"""

from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime
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

from .factory.digest import is_digest, sha256_digest


FIRST_CUSTOMER_CONTRACT_VERSIONS_V2 = {
    "CreativeOrder": "CreativeOrder.v2",
    "ScriptApprovalReceipt": "ScriptApprovalReceipt.v2",
    "EditorApprovalReceipt": "EditorApprovalReceipt.v2",
    "PaidEffectIntent": "PaidEffectIntent.v2",
    "PaidEffectAttempt": "PaidEffectAttempt.v2",
    "VerifiedRenderReceipt": "VerifiedRenderReceipt.v2",
}

_FROZEN_STRICT = ConfigDict(frozen=True, extra="forbid", strict=True)
_KEY_RE = re.compile(r"^[0-9a-f]{64}$")
_UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
_EPHEMERAL_ORDER_FIELDS = frozenset(
    {"run_id", "attempt_id", "lease_id", "provider_job_id"}
)


def _valid_utc(value: str) -> str:
    if not _UTC_RE.fullmatch(value):
        raise ValueError("timestamp must be an ISO-8601 UTC value ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("timestamp is not a valid calendar value") from exc
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError("timestamp must be UTC")
    return value


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
DigestStr = Annotated[
    str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")
]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
UtcTimestamp = Annotated[str, AfterValidator(_valid_utc)]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
PositiveMoney = Annotated[float, Field(gt=0, allow_inf_nan=False)]
NonNegativeMoney = Annotated[float, Field(ge=0, allow_inf_nan=False)]
PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]

EffectKind = Literal["visual", "video", "voiceover", "music", "sfx", "render"]
PaidEffectState = Literal[
    "PLANNED",
    "CLAIMED",
    "PROVIDER_STARTING",
    "PROVIDER_STARTED",
    "RECONCILE_REQUIRED",
    "SUCCEEDED",
    "FAILED_CONFIRMED",
    "NOT_STARTED_CONFIRMED",
]


def _non_empty(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _digest(value: str, field: str) -> str:
    if not isinstance(value, str) or not is_digest(value):
        raise ValueError(f"{field} must be sha256:<64 lowercase hex>")
    return value


def _sha256_text(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def derive_customer_order_key_v2(
    workspace_id: str,
    customer_external_order_id: str,
) -> str:
    """Stable business key: payload digest/run/attempt never participate.

    A persistence owner must compare ``canonical_order_digest`` separately:
    equal means idempotent replay; different means conflict for the same key.
    """

    workspace = _non_empty(workspace_id, "workspace_id")
    external = _non_empty(customer_external_order_id, "customer_external_order_id")
    return _sha256_text(f"{workspace}|{external}")


def derive_effect_key_v2(
    customer_order_key: str,
    approved_script_digest: str,
    effect_kind: str,
    asset_slot: str,
) -> str:
    """Stable paid-effect identity, excluding provider/run/attempt/lease data."""

    if not isinstance(customer_order_key, str) or not _KEY_RE.fullmatch(
        customer_order_key
    ):
        raise ValueError("customer_order_key must be 64 lowercase hex")
    script = _digest(approved_script_digest, "approved_script_digest")
    kind = _non_empty(effect_kind, "effect_kind")
    slot = _non_empty(asset_slot, "asset_slot")
    return _sha256_text(f"{customer_order_key}|{script}|{kind}|{slot}")


def derive_editor_approval_digest_v2(
    customer_order_key: str,
    approved_script_digest: str,
    timeline_digest: str,
    media_manifest_digest: str,
    render_policy_digest: str,
) -> str:
    """Content digest authorizing exactly one final-render input set."""

    if not isinstance(customer_order_key, str) or not _KEY_RE.fullmatch(
        customer_order_key
    ):
        raise ValueError("customer_order_key must be 64 lowercase hex")
    body = {
        "customer_order_key": customer_order_key,
        "approved_script_digest": _digest(
            approved_script_digest, "approved_script_digest"
        ),
        "timeline_digest": _digest(timeline_digest, "timeline_digest"),
        "media_manifest_digest": _digest(
            media_manifest_digest, "media_manifest_digest"
        ),
        "render_policy_digest": _digest(
            render_policy_digest, "render_policy_digest"
        ),
    }
    return sha256_digest(body)


def _validate_json_value(value: Any, path: str = "canonical_order_payload") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contains a non-finite number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} contains a non-string key")
            if key in _EPHEMERAL_ORDER_FIELDS:
                raise ValueError(f"{path} cannot contain ephemeral field {key!r}")
            _validate_json_value(item, f"{path}.{key}")
        return
    raise ValueError(f"{path} contains non-JSON value {type(value).__name__}")


def _validate_revisions(value: Mapping[str, str], field: str) -> Mapping[str, str]:
    if not value:
        raise ValueError(f"{field} must contain at least one revision")
    for name, revision in value.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{field} contains an empty component name")
        if not isinstance(revision, str) or not revision.strip():
            raise ValueError(f"{field}.{name} contains an empty revision")
    return value


class CreativeOrderV2(BaseModel):
    model_config = _FROZEN_STRICT

    contract_version: Literal["CreativeOrder.v2"]
    customer_order_key: Sha256Hex
    workspace_id: NonEmptyStr
    account_id: NonEmptyStr
    brand_id: NonEmptyStr
    product_or_listing_id: NonEmptyStr
    customer_external_order_id: NonEmptyStr
    canonical_order_payload: dict[str, Any]
    canonical_order_digest: DigestStr
    created_at_utc: UtcTimestamp

    @model_validator(mode="after")
    def _bind_identity(self) -> "CreativeOrderV2":
        if not self.canonical_order_payload:
            raise ValueError("canonical_order_payload must not be empty")
        _validate_json_value(self.canonical_order_payload)
        expected_digest = sha256_digest(self.canonical_order_payload)
        if self.canonical_order_digest != expected_digest:
            raise ValueError("canonical_order_digest does not match canonical_order_payload")
        expected_key = derive_customer_order_key_v2(
            self.workspace_id, self.customer_external_order_id
        )
        if self.customer_order_key != expected_key:
            raise ValueError("customer_order_key does not match external order identity")
        return self


class ScriptApprovalReceiptV2(BaseModel):
    model_config = _FROZEN_STRICT

    contract_version: Literal["ScriptApprovalReceipt.v2"]
    approval_receipt_id: NonEmptyStr
    customer_order_key: Sha256Hex
    workspace_id: NonEmptyStr
    approval_kind: Literal["script"]
    approver_account_id: NonEmptyStr
    order_digest: DigestStr
    script_digest: DigestStr
    policy_digest: DigestStr
    approved_at_utc: UtcTimestamp
    transaction_audit_id: NonEmptyStr

    def binds(
        self,
        order: CreativeOrderV2,
        script_digest: str,
        policy_digest: str,
    ) -> bool:
        return (
            self.customer_order_key == order.customer_order_key
            and self.workspace_id == order.workspace_id
            and self.order_digest == order.canonical_order_digest
            and self.script_digest == script_digest
            and self.policy_digest == policy_digest
        )


class EditorApprovalReceiptV2(BaseModel):
    model_config = _FROZEN_STRICT

    contract_version: Literal["EditorApprovalReceipt.v2"]
    editor_approval_receipt_id: NonEmptyStr
    customer_order_key: Sha256Hex
    workspace_id: NonEmptyStr
    editor_account_id: NonEmptyStr
    approved_script_digest: DigestStr
    timeline_digest: DigestStr
    media_manifest_digest: DigestStr
    render_policy_digest: DigestStr
    editor_approval_digest: DigestStr
    approved_at_utc: UtcTimestamp
    transaction_audit_id: NonEmptyStr

    @model_validator(mode="after")
    def _bind_digest(self) -> "EditorApprovalReceiptV2":
        expected = derive_editor_approval_digest_v2(
            self.customer_order_key,
            self.approved_script_digest,
            self.timeline_digest,
            self.media_manifest_digest,
            self.render_policy_digest,
        )
        if self.editor_approval_digest != expected:
            raise ValueError("editor_approval_digest does not match approved inputs")
        return self

    def binds(self, script_receipt: ScriptApprovalReceiptV2) -> bool:
        return (
            self.customer_order_key == script_receipt.customer_order_key
            and self.workspace_id == script_receipt.workspace_id
            and self.approved_script_digest == script_receipt.script_digest
            and self.render_policy_digest == script_receipt.policy_digest
        )


class PaidEffectIntentV2(BaseModel):
    model_config = _FROZEN_STRICT

    contract_version: Literal["PaidEffectIntent.v2"]
    effect_key: Sha256Hex
    customer_order_key: Sha256Hex
    workspace_id: NonEmptyStr
    approved_script_digest: DigestStr
    effect_kind: EffectKind
    asset_slot: NonEmptyStr
    request_digest: DigestStr
    spend_ceiling: PositiveMoney
    currency: CurrencyCode
    created_at_utc: UtcTimestamp

    @model_validator(mode="after")
    def _bind_effect_key(self) -> "PaidEffectIntentV2":
        expected = derive_effect_key_v2(
            self.customer_order_key,
            self.approved_script_digest,
            self.effect_kind,
            self.asset_slot,
        )
        if self.effect_key != expected:
            raise ValueError("effect_key does not match immutable paid-effect inputs")
        return self


class PaidEffectAttemptV2(BaseModel):
    model_config = _FROZEN_STRICT

    contract_version: Literal["PaidEffectAttempt.v2"]
    effect_key: Sha256Hex
    customer_order_key: Sha256Hex
    workspace_id: NonEmptyStr
    approved_script_digest: DigestStr
    effect_kind: EffectKind
    asset_slot: NonEmptyStr
    attempt_id: NonEmptyStr
    attempt_number: PositiveInt
    provider: NonEmptyStr
    provider_idempotency_key: NonEmptyStr
    provider_job_id: NonEmptyStr | None
    state: PaidEffectState
    lease_owner: NonEmptyStr | None
    lease_expires_at_utc: UtcTimestamp | None
    fencing_token: NonNegativeInt
    request_digest: DigestStr
    spend_ceiling: PositiveMoney
    currency: CurrencyCode
    response_digest: DigestStr | None
    cost_currency: CurrencyCode | None
    cost_amount: NonNegativeMoney | None
    last_reconciled_at_utc: UtcTimestamp | None
    created_at_utc: UtcTimestamp
    updated_at_utc: UtcTimestamp

    @model_validator(mode="after")
    def _bind_and_check_state(self) -> "PaidEffectAttemptV2":
        expected = derive_effect_key_v2(
            self.customer_order_key,
            self.approved_script_digest,
            self.effect_kind,
            self.asset_slot,
        )
        if self.effect_key != expected:
            raise ValueError("effect_key does not match immutable paid-effect inputs")
        if self.state != "PLANNED" and self.fencing_token < 1:
            raise ValueError("claimed or terminal attempts require a positive fencing_token")
        if self.state in {"CLAIMED", "PROVIDER_STARTING"} and (
            self.lease_owner is None or self.lease_expires_at_utc is None
        ):
            raise ValueError("claimed/provider-starting attempts require an active lease")
        if self.state in {"PROVIDER_STARTED", "SUCCEEDED"} and (
            self.provider_job_id is None
        ):
            raise ValueError(f"{self.state} requires provider_job_id")
        if self.state == "SUCCEEDED" and self.response_digest is None:
            raise ValueError("SUCCEEDED requires response_digest")
        if (self.cost_currency is None) != (self.cost_amount is None):
            raise ValueError("cost_currency and cost_amount must be present together")
        if self.cost_currency is not None and self.cost_currency != self.currency:
            raise ValueError("cost_currency must match authorized currency")
        if self.cost_amount is not None and self.cost_amount > self.spend_ceiling:
            raise ValueError("cost_amount exceeds authorized spend_ceiling")
        updated_at = _parse_utc_instant(self.updated_at_utc)
        created_at = _parse_utc_instant(self.created_at_utc)
        if updated_at is None or created_at is None:
            raise ValueError("attempt timestamps must be valid UTC instants")
        if updated_at < created_at:
            raise ValueError("updated_at_utc cannot precede created_at_utc")
        return self

    def binds(self, intent: PaidEffectIntentV2) -> bool:
        return (
            self.effect_key == intent.effect_key
            and self.customer_order_key == intent.customer_order_key
            and self.workspace_id == intent.workspace_id
            and self.approved_script_digest == intent.approved_script_digest
            and self.effect_kind == intent.effect_kind
            and self.asset_slot == intent.asset_slot
            and self.request_digest == intent.request_digest
            and self.spend_ceiling == intent.spend_ceiling
            and self.currency == intent.currency
        )

    def allows_new_attempt(self) -> bool:
        """Whether prior provider state proves another attempt is safe to start.

        Reconciliation is deliberately not retriable: a timeout can conceal a
        provider-side paid job even when no job id was returned.  Only pristine
        work or an explicitly terminal no/failed start may create an attempt.
        """
        return self.state in {"PLANNED", "FAILED_CONFIRMED", "NOT_STARTED_CONFIRMED"}


class VerifiedRenderReceiptV2(BaseModel):
    model_config = _FROZEN_STRICT

    contract_version: Literal["VerifiedRenderReceipt.v2"]
    verified_render_receipt_id: NonEmptyStr
    customer_order_key: Sha256Hex
    workspace_id: NonEmptyStr
    run_id: NonEmptyStr
    render_job_id: NonEmptyStr
    render_effect_key: Sha256Hex
    editor_approval_digest: DigestStr
    output_url: Annotated[str, StringConstraints(pattern=r"^https://\S+$")]
    storage_key: NonEmptyStr
    output_sha256: Sha256Hex
    output_bytes: PositiveInt
    duration_ms: PositiveInt
    video_codec: NonEmptyStr
    audio_codec: NonEmptyStr
    mechanical_checker_version: NonEmptyStr
    qa_checker_version: NonEmptyStr
    qa_verdict: Literal["PASS"]
    qa_evidence_digest: DigestStr
    source_revisions: dict[str, NonEmptyStr]
    deployed_revisions: dict[str, NonEmptyStr]
    created_at_utc: UtcTimestamp
    transaction_audit_id: NonEmptyStr

    @field_validator("source_revisions", "deployed_revisions")
    @classmethod
    def _non_empty_revisions(cls, value: Mapping[str, str], info: Any) -> Mapping[str, str]:
        return _validate_revisions(value, info.field_name)

    def binds(self, editor_receipt: EditorApprovalReceiptV2) -> bool:
        return (
            self.customer_order_key == editor_receipt.customer_order_key
            and self.workspace_id == editor_receipt.workspace_id
            and self.editor_approval_digest == editor_receipt.editor_approval_digest
        )

    def matches_output_bytes(self, data: bytes) -> bool:
        return hashlib.sha256(data).hexdigest() == self.output_sha256


def _parse_utc_instant(value: str) -> datetime | None:
    """Parse a contract timestamp for chronology, not lexicographic ordering."""
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except (TypeError, ValueError):
        return None


def validate_creative_order_v2(obj: Mapping[str, Any]) -> CreativeOrderV2:
    return CreativeOrderV2.model_validate(obj)


def validate_script_approval_receipt_v2(
    obj: Mapping[str, Any],
) -> ScriptApprovalReceiptV2:
    return ScriptApprovalReceiptV2.model_validate(obj)


def validate_editor_approval_receipt_v2(
    obj: Mapping[str, Any],
) -> EditorApprovalReceiptV2:
    return EditorApprovalReceiptV2.model_validate(obj)


def validate_paid_effect_intent_v2(obj: Mapping[str, Any]) -> PaidEffectIntentV2:
    return PaidEffectIntentV2.model_validate(obj)


def validate_paid_effect_attempt_v2(obj: Mapping[str, Any]) -> PaidEffectAttemptV2:
    return PaidEffectAttemptV2.model_validate(obj)


def validate_verified_render_receipt_v2(
    obj: Mapping[str, Any],
) -> VerifiedRenderReceiptV2:
    return VerifiedRenderReceiptV2.model_validate(obj)


__all__ = [
    "FIRST_CUSTOMER_CONTRACT_VERSIONS_V2",
    "CreativeOrderV2",
    "ScriptApprovalReceiptV2",
    "EditorApprovalReceiptV2",
    "PaidEffectIntentV2",
    "PaidEffectAttemptV2",
    "VerifiedRenderReceiptV2",
    "EffectKind",
    "PaidEffectState",
    "derive_customer_order_key_v2",
    "derive_effect_key_v2",
    "derive_editor_approval_digest_v2",
    "validate_creative_order_v2",
    "validate_script_approval_receipt_v2",
    "validate_editor_approval_receipt_v2",
    "validate_paid_effect_intent_v2",
    "validate_paid_effect_attempt_v2",
    "validate_verified_render_receipt_v2",
]
