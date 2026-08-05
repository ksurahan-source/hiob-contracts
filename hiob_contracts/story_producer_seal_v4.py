"""Five-producer V4 seal handoff for Star's future durable ledger.

This is a value contract, not a provider, database, or trusted-runtime
authority.  A producer submits an immutable canonical payload and a
receipt-bound reference.  Star's future RPC is responsible for durable issuer
authentication and ledger persistence; consumers can turn the validated seal
into the already-public Ares V4 authority-reference shape.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import (
    BaseModel,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from .ares_create_story_v4 import (
    AresStoryAuthorityRefV4,
    AresStoryEvidenceBundleV4,
    AresStoryHookDirectiveV4,
    AresStoryNarrativeBriefV4,
    story_authority_ref_receipt_digest_v4,
)
from .ares_script_revision_v1 import (
    DigestStr,
    NonBlankStr,
    _FROZEN_STRICT,
    _deep_freeze_json,
    _json_value,
    _validate_json,
    canonical_contract_digest_v1,
)
from .factory import sha256_digest


StoryProducerV4 = Literal["janus", "karma", "parzifal", "artemis", "metis"]
StoryArtifactTypeV4 = Literal[
    "product_truth",
    "story_brief",
    "identity_lock",
    "evidence_bundle",
    "hook_directive",
]
StoryProducerSealStatusV4 = Literal["sealed"]

STORY_PRODUCER_ARTIFACT_PAIRS_V4: tuple[
    tuple[StoryProducerV4, StoryArtifactTypeV4], ...
] = (
    ("janus", "product_truth"),
    ("karma", "story_brief"),
    ("parzifal", "identity_lock"),
    ("artemis", "evidence_bundle"),
    ("metis", "hook_directive"),
)
_STORY_PRODUCER_ARTIFACT_PAIR_SET_V4 = frozenset(STORY_PRODUCER_ARTIFACT_PAIRS_V4)
_FORBIDDEN_RAW_13Q_KEYS = frozenset({"13q", "raw13q", "intake13q", "thirteenquestions"})
_FORBIDDEN_TRUST_KEYS = frozenset({"verified", "isverified", "trustedrunoutputdigest"})
_RAW_STORY_SHORTCUT_KEYS = frozenset({"beats", "nbeats", "beatcount", "storybeats"})


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _reject_unsealed_payload_keys(
    value: Any,
    *,
    path: str,
    allow_story_brief: bool,
) -> None:
    """Reject caller claims and raw planning shortcuts at every JSON depth."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = _normalized_key(str(key))
            field_path = f"{path}.{key}"
            if normalized in _FORBIDDEN_RAW_13Q_KEYS:
                raise ValueError("raw 13Q is forbidden in a producer seal")
            if normalized in _FORBIDDEN_TRUST_KEYS:
                raise ValueError(
                    "caller-provided verified/trusted flags are forbidden in a producer seal"
                )
            if not allow_story_brief and normalized in _RAW_STORY_SHORTCUT_KEYS:
                raise ValueError(
                    "raw story beat/count shortcut is forbidden outside Karma story_brief"
                )
            _reject_unsealed_payload_keys(
                item,
                path=field_path,
                allow_story_brief=allow_story_brief,
            )
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_unsealed_payload_keys(
                item,
                path=f"{path}[{index}]",
                allow_story_brief=allow_story_brief,
            )


def story_producer_artifact_pair_v4(
    producer: str,
    artifact_type: str,
) -> tuple[StoryProducerV4, StoryArtifactTypeV4]:
    """Return one of the five legal V4 producer/artifact ownership pairs."""

    pair = (producer, artifact_type)
    if pair not in _STORY_PRODUCER_ARTIFACT_PAIR_SET_V4:
        raise ValueError("producer/artifact_type is not an allowed V4 seal pair")
    return pair  # type: ignore[return-value]


def canonical_story_producer_payload_digest_v4(value: Mapping[str, Any]) -> str:
    """Digest a JSON-only artifact payload exactly as its producer sealed it."""

    _validate_json(value, "canonical_payload")
    return sha256_digest(_json_value(value))


def story_producer_seal_payload_digest_v4(
    value: BaseModel | Mapping[str, Any],
) -> str:
    """Canonical digest of a producer seal payload, excluding its self-digest."""

    return canonical_contract_digest_v1(value, exclude={"payload_digest"})


def story_producer_seal_receipt_digest_v4(
    value: BaseModel | Mapping[str, Any],
) -> str:
    """Canonical digest of the immutable producer reference, sans self-digest."""

    return canonical_contract_digest_v1(value, exclude={"receipt_digest"})


class StoryProducerSealScopeV4(BaseModel):
    """Tenant and run scope shared by the producer payload and its receipt."""

    model_config = _FROZEN_STRICT

    workspace_id: NonBlankStr
    run_id: NonBlankStr


class StoryProducerSealPayloadV4(BaseModel):
    """The canonical artifact and causal lineage a producer asks Star to seal."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryProducerSealPayload.v4"]
    scope: StoryProducerSealScopeV4
    producer: StoryProducerV4
    artifact_type: StoryArtifactTypeV4
    artifact_digest: DigestStr
    source_output_digest: DigestStr
    upstream_output_digests: tuple[DigestStr, ...] = Field(min_length=1)
    canonical_payload: Mapping[str, Any]
    canonical_payload_digest: DigestStr
    payload_digest: DigestStr

    @field_validator("upstream_output_digests", mode="before")
    @classmethod
    def _upstream_to_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @field_validator("canonical_payload", mode="after")
    @classmethod
    def _freeze_canonical_payload(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        if not value:
            raise ValueError("canonical_payload must not be empty")
        _validate_json(value, "canonical_payload")
        contract_version = value.get("contract_version")
        if not isinstance(contract_version, str) or not contract_version.strip():
            raise ValueError(
                "canonical_payload must declare a nonblank contract_version"
            )
        return _deep_freeze_json(value)

    @field_serializer("canonical_payload", when_used="always")
    def _serialize_canonical_payload(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return _json_value(value)

    @model_validator(mode="after")
    def _bind_canonical_payload_and_lineage(self) -> "StoryProducerSealPayloadV4":
        story_producer_artifact_pair_v4(self.producer, self.artifact_type)
        canonical_payload = _json_value(self.canonical_payload)
        _reject_unsealed_payload_keys(
            canonical_payload,
            path="canonical_payload",
            allow_story_brief=(self.producer, self.artifact_type)
            == ("karma", "story_brief"),
        )
        if self.canonical_payload_digest != canonical_story_producer_payload_digest_v4(
            canonical_payload
        ):
            raise ValueError(
                "canonical_payload_digest must bind the canonical producer payload"
            )
        if self.source_output_digest in self.upstream_output_digests:
            raise ValueError("source_output_digest must not appear in upstream lineage")
        if len(self.upstream_output_digests) != len(set(self.upstream_output_digests)):
            raise ValueError("upstream_output_digests must not contain duplicates")
        if self.payload_digest != story_producer_seal_payload_digest_v4(self):
            raise ValueError(
                "payload_digest must bind the canonical producer seal payload"
            )

        if (self.producer, self.artifact_type) == ("karma", "story_brief"):
            brief = AresStoryNarrativeBriefV4.model_validate(canonical_payload)
            if self.artifact_digest != brief.story_brief_digest:
                raise ValueError("artifact_digest must equal Karma story_brief_digest")
        elif (self.producer, self.artifact_type) == ("artemis", "evidence_bundle"):
            evidence = AresStoryEvidenceBundleV4.model_validate(canonical_payload)
            if self.artifact_digest != evidence.evidence_bundle_digest:
                raise ValueError(
                    "artifact_digest must equal Artemis evidence_bundle_digest"
                )
        elif (self.producer, self.artifact_type) == ("metis", "hook_directive"):
            hook = AresStoryHookDirectiveV4.model_validate(canonical_payload)
            if self.artifact_digest != hook.directive_digest:
                raise ValueError("artifact_digest must equal Metis directive_digest")
        return self


class StoryProducerSealRefV4(BaseModel):
    """Receipt-bound producer reference that Star can store without trusting flags."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryProducerSealRef.v4"]
    scope: StoryProducerSealScopeV4
    producer: StoryProducerV4
    artifact_type: StoryArtifactTypeV4
    issuer: StoryProducerV4
    status: StoryProducerSealStatusV4
    artifact_digest: DigestStr
    source_output_digest: DigestStr
    upstream_output_digests: tuple[DigestStr, ...] = Field(min_length=1)
    canonical_payload_digest: DigestStr
    payload_digest: DigestStr
    receipt_id: NonBlankStr
    receipt_digest: DigestStr

    @field_validator("upstream_output_digests", mode="before")
    @classmethod
    def _upstream_to_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _bind_issuer_pair_lineage_and_receipt(self) -> "StoryProducerSealRefV4":
        story_producer_artifact_pair_v4(self.producer, self.artifact_type)
        if self.issuer != self.producer:
            raise ValueError("issuer must equal the producer that owns this seal pair")
        if self.source_output_digest in self.upstream_output_digests:
            raise ValueError("source_output_digest must not appear in upstream lineage")
        if len(self.upstream_output_digests) != len(set(self.upstream_output_digests)):
            raise ValueError("upstream_output_digests must not contain duplicates")
        if self.receipt_digest != story_producer_seal_receipt_digest_v4(self):
            raise ValueError("receipt_digest must bind the canonical producer seal ref")
        return self


class StoryProducerSealInputV4(BaseModel):
    """Producer-side handoff: payload plus matching sealed receipt reference."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryProducerSealInput.v4"]
    payload: StoryProducerSealPayloadV4
    ref: StoryProducerSealRefV4

    @model_validator(mode="after")
    def _bind_payload_to_ref(self) -> "StoryProducerSealInputV4":
        if self.payload.scope != self.ref.scope:
            raise ValueError("payload and ref must share the exact seal scope")
        for field in (
            "producer",
            "artifact_type",
            "artifact_digest",
            "source_output_digest",
            "upstream_output_digests",
            "canonical_payload_digest",
            "payload_digest",
        ):
            if getattr(self.payload, field) != getattr(self.ref, field):
                raise ValueError(f"ref.{field} must match the immutable seal payload")
        return self


class StoryProducerSealLedgerRecordV4(BaseModel):
    """Flat canonical record shape for Star's future RPC and DB ledger.

    ``seal_id`` intentionally equals ``receipt_id``.  That leaves no DB primary
    key outside the immutable receipt binding while still keeping the record
    simple to parse into independent columns.
    """

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryProducerSealLedgerRecord.v4"]
    seal_id: NonBlankStr
    workspace_id: NonBlankStr
    run_id: NonBlankStr
    producer: StoryProducerV4
    artifact_type: StoryArtifactTypeV4
    issuer: StoryProducerV4
    status: StoryProducerSealStatusV4
    artifact_digest: DigestStr
    source_output_digest: DigestStr
    upstream_output_digests: tuple[DigestStr, ...] = Field(min_length=1)
    canonical_payload: Mapping[str, Any]
    canonical_payload_digest: DigestStr
    payload_digest: DigestStr
    receipt_digest: DigestStr

    @field_validator("upstream_output_digests", mode="before")
    @classmethod
    def _upstream_to_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @field_validator("canonical_payload", mode="after")
    @classmethod
    def _freeze_canonical_payload(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        _validate_json(value, "canonical_payload")
        return _deep_freeze_json(value)

    @field_serializer("canonical_payload", when_used="always")
    def _serialize_canonical_payload(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return _json_value(value)

    def to_input(self) -> StoryProducerSealInputV4:
        """Reconstruct the exact nested producer handoff from the flat record."""

        return StoryProducerSealInputV4.model_validate(
            {
                "contract_version": "StoryProducerSealInput.v4",
                "payload": {
                    "contract_version": "StoryProducerSealPayload.v4",
                    "scope": {
                        "workspace_id": self.workspace_id,
                        "run_id": self.run_id,
                    },
                    "producer": self.producer,
                    "artifact_type": self.artifact_type,
                    "artifact_digest": self.artifact_digest,
                    "source_output_digest": self.source_output_digest,
                    "upstream_output_digests": self.upstream_output_digests,
                    "canonical_payload": _json_value(self.canonical_payload),
                    "canonical_payload_digest": self.canonical_payload_digest,
                    "payload_digest": self.payload_digest,
                },
                "ref": {
                    "contract_version": "StoryProducerSealRef.v4",
                    "scope": {
                        "workspace_id": self.workspace_id,
                        "run_id": self.run_id,
                    },
                    "producer": self.producer,
                    "artifact_type": self.artifact_type,
                    "issuer": self.issuer,
                    "status": self.status,
                    "artifact_digest": self.artifact_digest,
                    "source_output_digest": self.source_output_digest,
                    "upstream_output_digests": self.upstream_output_digests,
                    "canonical_payload_digest": self.canonical_payload_digest,
                    "payload_digest": self.payload_digest,
                    "receipt_id": self.seal_id,
                    "receipt_digest": self.receipt_digest,
                },
            }
        )

    @model_validator(mode="after")
    def _require_valid_nested_seal(self) -> "StoryProducerSealLedgerRecordV4":
        self.to_input()
        return self

    @classmethod
    def from_input(
        cls, value: StoryProducerSealInputV4 | Mapping[str, Any]
    ) -> "StoryProducerSealLedgerRecordV4":
        seal = StoryProducerSealInputV4.model_validate(value)
        return cls.model_validate(
            {
                "contract_version": "StoryProducerSealLedgerRecord.v4",
                "seal_id": seal.ref.receipt_id,
                "workspace_id": seal.payload.scope.workspace_id,
                "run_id": seal.payload.scope.run_id,
                "producer": seal.payload.producer,
                "artifact_type": seal.payload.artifact_type,
                "issuer": seal.ref.issuer,
                "status": seal.ref.status,
                "artifact_digest": seal.payload.artifact_digest,
                "source_output_digest": seal.payload.source_output_digest,
                "upstream_output_digests": seal.payload.upstream_output_digests,
                "canonical_payload": _json_value(seal.payload.canonical_payload),
                "canonical_payload_digest": seal.payload.canonical_payload_digest,
                "payload_digest": seal.payload.payload_digest,
                "receipt_digest": seal.ref.receipt_digest,
            }
        )


def story_producer_seal_to_ledger_record_v4(
    value: StoryProducerSealInputV4 | Mapping[str, Any],
) -> StoryProducerSealLedgerRecordV4:
    """Normalize an immutable producer handoff into Star's flat ledger record."""

    return StoryProducerSealLedgerRecordV4.from_input(value)


def story_producer_seal_to_ares_authority_ref_v4(
    value: StoryProducerSealInputV4 | Mapping[str, Any],
) -> AresStoryAuthorityRefV4:
    """Project a validated producer seal into the existing Ares V4 ref shape."""

    seal = StoryProducerSealInputV4.model_validate(value)
    return AresStoryAuthorityRefV4(
        producer=seal.payload.producer,
        artifact_type=seal.payload.artifact_type,
        artifact_digest=seal.payload.artifact_digest,
        source_output_digest=seal.payload.source_output_digest,
        payload_digest=seal.payload.canonical_payload_digest,
        receipt_id=seal.ref.receipt_id,
        receipt_digest=story_authority_ref_receipt_digest_v4(
            producer=seal.payload.producer,
            artifact_type=seal.payload.artifact_type,
            artifact_digest=seal.payload.artifact_digest,
            source_output_digest=seal.payload.source_output_digest,
            payload_digest=seal.payload.canonical_payload_digest,
            receipt_id=seal.ref.receipt_id,
            workspace_id=seal.payload.scope.workspace_id,
            run_id=seal.payload.scope.run_id,
        ),
        workspace_id=seal.payload.scope.workspace_id,
        run_id=seal.payload.scope.run_id,
    )


__all__ = [
    "StoryProducerV4",
    "StoryArtifactTypeV4",
    "StoryProducerSealStatusV4",
    "STORY_PRODUCER_ARTIFACT_PAIRS_V4",
    "story_producer_artifact_pair_v4",
    "canonical_story_producer_payload_digest_v4",
    "story_producer_seal_payload_digest_v4",
    "story_producer_seal_receipt_digest_v4",
    "StoryProducerSealScopeV4",
    "StoryProducerSealPayloadV4",
    "StoryProducerSealRefV4",
    "StoryProducerSealInputV4",
    "StoryProducerSealLedgerRecordV4",
    "story_producer_seal_to_ledger_record_v4",
    "story_producer_seal_to_ares_authority_ref_v4",
]
