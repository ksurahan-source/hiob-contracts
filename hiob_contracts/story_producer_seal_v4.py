"""Five-producer V4 staged-seal contract; Star DB alone accepts authority.

Producers can only stage frozen material.  This module deliberately has no
accepted-authority parser, factory, ledger record, or Ares-reference adapter:
Star's durable RPC resolves an accepted row and the strict Ares request parser
consumes that DB-owned authority.  Keeping those operations out of the public
contract prevents a caller from promoting its own staged candidate.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import (
    BaseModel,
    field_serializer,
    field_validator,
    model_validator,
)

from .ares_create_story_v4 import (
    AresStoryEvidenceBundleV4,
    AresStoryHookDirectiveV4,
    AresStoryNarrativeBriefV4,
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
StoryProducerStagedStatusV4 = Literal["sealed"]
StoryProducerAcceptedAuthorityFieldV4 = Literal[
    "authority_ref",
    "sealed_payload",
    "issuer",
    "status",
    "upstream_output_digests",
]

STORY_PRODUCER_ARTIFACT_PAIRS_V4: tuple[
    tuple[StoryProducerV4, StoryArtifactTypeV4], ...
] = (
    ("janus", "product_truth"),
    ("karma", "story_brief"),
    ("parzifal", "identity_lock"),
    ("artemis", "evidence_bundle"),
    ("metis", "hook_directive"),
)
STORY_PRODUCER_ACCEPTED_AUTHORITY_FIELD_NAMES_V4: tuple[
    StoryProducerAcceptedAuthorityFieldV4, ...
] = (
    "authority_ref",
    "sealed_payload",
    "issuer",
    "status",
    "upstream_output_digests",
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
    """Reject raw inputs and caller trust claims at every JSON depth."""

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
    """Digest a JSON-only artifact payload exactly as its producer staged it."""

    _validate_json(value, "canonical_payload")
    return sha256_digest(_json_value(value))


def story_producer_seal_payload_digest_v4(
    value: BaseModel | Mapping[str, Any],
) -> str:
    """Canonical digest of staged payload metadata, excluding its self-digest."""

    return canonical_contract_digest_v1(value, exclude={"payload_digest"})


def story_producer_staged_ref_digest_v4(
    value: BaseModel | Mapping[str, Any],
) -> str:
    """Canonical digest of a staged reference, excluding its self-digest."""

    return canonical_contract_digest_v1(value, exclude={"candidate_digest"})


def story_producer_accepted_authority_projection_v4_schema_descriptor() -> dict[
    str, Any
]:
    """Describe, but never parse or mint, Star's DB-owned accepted record.

    The tuple of fields is intentionally the full public surface.  A producer
    cannot submit this shape through the staged-candidate model, and contracts
    offers no conversion to an Ares authority reference.  Star's concrete RPC
    validates the row before the strict Ares request parser consumes it.
    """

    return {
        "owner": "star_db_rpc",
        "accepted_authority": "external_only",
        "fields": list(STORY_PRODUCER_ACCEPTED_AUTHORITY_FIELD_NAMES_V4),
        "issuer": "<producer>.authority",
        "status": "accepted",
        "consumer": "ares_strict_request_parser",
    }


class StoryProducerSealScopeV4(BaseModel):
    """Tenant and run scope shared by staged payload and staged reference."""

    model_config = _FROZEN_STRICT

    workspace_id: NonBlankStr
    run_id: NonBlankStr


def _require_staged_upstream_lineage(
    *,
    producer: StoryProducerV4,
    upstream_output_digests: tuple[str, ...],
) -> None:
    """Enforce only lineage a producer may stage before Star DB resolution.

    Janus starts the chain.  Karma and Parzifal may name one prior producer
    output, whose real producer is resolved by Star.  Artemis and Metis must
    not carry a trusted-run digest at this stage; Star DB adds that accepted
    lineage after resolving its durable run record.
    """

    count = len(upstream_output_digests)
    if producer == "janus" and count != 0:
        raise ValueError(
            "Janus staged candidate must be the root with no upstream digest"
        )
    if producer == "karma" and count != 1:
        raise ValueError("Karma staged candidate must name exactly one Janus output")
    if producer == "parzifal" and count != 1:
        raise ValueError("Parzifal staged candidate must name exactly one Karma output")
    if producer in {"artemis", "metis"} and count != 0:
        raise ValueError(
            f"{producer.title()} staged candidate must leave trusted-run lineage to Star DB"
        )


def _validate_artifact_payload(
    *,
    producer: StoryProducerV4,
    artifact_type: StoryArtifactTypeV4,
    artifact_digest: str,
    canonical_payload: Mapping[str, Any],
) -> None:
    canonical_value = _json_value(canonical_payload)
    _reject_unsealed_payload_keys(
        canonical_value,
        path="canonical_payload",
        allow_story_brief=(producer, artifact_type) == ("karma", "story_brief"),
    )
    if (producer, artifact_type) == ("karma", "story_brief"):
        brief = AresStoryNarrativeBriefV4.model_validate(canonical_value)
        if artifact_digest != brief.story_brief_digest:
            raise ValueError("artifact_digest must equal Karma story_brief_digest")
    elif (producer, artifact_type) == ("artemis", "evidence_bundle"):
        evidence = AresStoryEvidenceBundleV4.model_validate(canonical_value)
        if artifact_digest != evidence.evidence_bundle_digest:
            raise ValueError(
                "artifact_digest must equal Artemis evidence_bundle_digest"
            )
    elif (producer, artifact_type) == ("metis", "hook_directive"):
        hook = AresStoryHookDirectiveV4.model_validate(canonical_value)
        if artifact_digest != hook.directive_digest:
            raise ValueError("artifact_digest must equal Metis directive_digest")


class StoryProducerSealPayloadV4(BaseModel):
    """Frozen artifact and pre-DB causal material a producer stages."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryProducerSealPayload.v4"]
    scope: StoryProducerSealScopeV4
    producer: StoryProducerV4
    artifact_type: StoryArtifactTypeV4
    artifact_digest: DigestStr
    source_output_digest: DigestStr
    upstream_output_digests: tuple[DigestStr, ...] = ()
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
        _require_staged_upstream_lineage(
            producer=self.producer,
            upstream_output_digests=self.upstream_output_digests,
        )
        if self.source_output_digest in self.upstream_output_digests:
            raise ValueError("source_output_digest must not appear in upstream lineage")
        if len(self.upstream_output_digests) != len(set(self.upstream_output_digests)):
            raise ValueError("upstream_output_digests must not contain duplicates")
        if self.canonical_payload_digest != canonical_story_producer_payload_digest_v4(
            self.canonical_payload
        ):
            raise ValueError(
                "canonical_payload_digest must bind the canonical producer payload"
            )
        if self.payload_digest != story_producer_seal_payload_digest_v4(self):
            raise ValueError(
                "payload_digest must bind the canonical producer seal payload"
            )
        _validate_artifact_payload(
            producer=self.producer,
            artifact_type=self.artifact_type,
            artifact_digest=self.artifact_digest,
            canonical_payload=self.canonical_payload,
        )
        return self


class StoryProducerStagedRefV4(BaseModel):
    """Producer-issued staging reference; it is not a Star authority receipt."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryProducerStagedRef.v4"]
    scope: StoryProducerSealScopeV4
    producer: StoryProducerV4
    artifact_type: StoryArtifactTypeV4
    issuer: StoryProducerV4
    status: StoryProducerStagedStatusV4
    artifact_digest: DigestStr
    source_output_digest: DigestStr
    upstream_output_digests: tuple[DigestStr, ...] = ()
    canonical_payload_digest: DigestStr
    payload_digest: DigestStr
    candidate_id: NonBlankStr
    candidate_digest: DigestStr

    @field_validator("upstream_output_digests", mode="before")
    @classmethod
    def _upstream_to_tuple(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _bind_staging_identity_and_lineage(self) -> "StoryProducerStagedRefV4":
        story_producer_artifact_pair_v4(self.producer, self.artifact_type)
        if self.issuer != self.producer:
            raise ValueError(
                "issuer must equal the producer that owns this staged pair"
            )
        _require_staged_upstream_lineage(
            producer=self.producer,
            upstream_output_digests=self.upstream_output_digests,
        )
        if self.source_output_digest in self.upstream_output_digests:
            raise ValueError("source_output_digest must not appear in upstream lineage")
        if len(self.upstream_output_digests) != len(set(self.upstream_output_digests)):
            raise ValueError("upstream_output_digests must not contain duplicates")
        if self.candidate_digest != story_producer_staged_ref_digest_v4(self):
            raise ValueError(
                "candidate_digest must bind the canonical staged reference"
            )
        return self


class StoryProducerSealCandidateV4(BaseModel):
    """Public producer input: staged material only, never accepted authority."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["StoryProducerSealCandidate.v4"]
    payload: StoryProducerSealPayloadV4
    staged_ref: StoryProducerStagedRefV4

    @model_validator(mode="after")
    def _bind_payload_to_staged_ref(self) -> "StoryProducerSealCandidateV4":
        if self.payload.scope != self.staged_ref.scope:
            raise ValueError("payload and staged_ref must share the exact seal scope")
        for field in (
            "producer",
            "artifact_type",
            "artifact_digest",
            "source_output_digest",
            "upstream_output_digests",
            "canonical_payload_digest",
            "payload_digest",
        ):
            if getattr(self.payload, field) != getattr(self.staged_ref, field):
                raise ValueError(
                    f"staged_ref.{field} must match the immutable seal payload"
                )
        return self


__all__ = [
    "StoryProducerV4",
    "StoryArtifactTypeV4",
    "StoryProducerStagedStatusV4",
    "StoryProducerAcceptedAuthorityFieldV4",
    "STORY_PRODUCER_ARTIFACT_PAIRS_V4",
    "STORY_PRODUCER_ACCEPTED_AUTHORITY_FIELD_NAMES_V4",
    "story_producer_artifact_pair_v4",
    "canonical_story_producer_payload_digest_v4",
    "story_producer_seal_payload_digest_v4",
    "story_producer_staged_ref_digest_v4",
    "story_producer_accepted_authority_projection_v4_schema_descriptor",
    "StoryProducerSealScopeV4",
    "StoryProducerSealPayloadV4",
    "StoryProducerStagedRefV4",
    "StoryProducerSealCandidateV4",
]
