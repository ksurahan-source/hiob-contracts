"""Karma edge refinery contracts — the mandatory semantic-handoff mechanism.

PRD_CREATIVE_FACTORY_HARMONY §6.2 (`KarmaRefineRequestV1`) and §6.3
(`KarmaEdgeReceiptV1<T>`).

For every semantic edge, Star calls Karma with the source `PlanetOutput`(s) and a
target input contract. Karma validates, judges grounding/quality, maps fields,
validates the target schema, and returns an immutable `KarmaEdgeReceipt`. The
receipt is the *only* thing that authorizes the target Planet to run.

Non-negotiable invariants encoded here (fail closed):
- `accepted`  ⇒ a byte-bound `target_input` + matching `target_input_digest`.
- `blocked` / `needs_human` ⇒ **no** `target_input` (a missing refinement can
  never masquerade as an accepted edge — PRD §14).
- any `error`-severity violation ⇒ cannot be `accepted`.
- every transform-log entry carries lineage (source paths, rule id, origin).
"""
from __future__ import annotations

import hashlib
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .digest import Digest, assert_digest, canonical_json, is_digest, sha256_digest
from .planet_output import ContractRef, PlanetOutput

_FROZEN = {"frozen": True, "extra": "forbid"}

EdgeDecision = Literal["accepted", "blocked", "needs_human"]
TransformOp = Literal["copy", "rename", "normalize", "derive", "drop"]
TransformOrigin = Literal["source", "deterministic_rule", "karma_inference", "human_override"]
ViolationSeverity = Literal["error", "warning"]


class TargetRef(BaseModel):
    """The named consumer an edge refines *for* — one edge, one target."""

    model_config = _FROZEN

    planet: str
    node_id: str
    input_contract: ContractRef


class PolicyRef(BaseModel):
    """The Karma policy/ruleset version that governs an edge decision."""

    model_config = _FROZEN

    id: str
    version: str
    digest: Digest

    @model_validator(mode="after")
    def _check(self) -> "PolicyRef":
        assert_digest(self.digest, "policy.digest")
        return self


class KarmaRefineRequest(BaseModel):
    """Star → Karma refine request (§6.2). `sources` is 1 normally, N for fan-in."""

    model_config = _FROZEN

    edge_id: str
    run_id: str
    factory_revision: int = Field(ge=0)
    workspace_id: str
    trace_id: str
    sources: tuple[PlanetOutput, ...]
    target: TargetRef
    policy: PolicyRef
    evidence_refs: tuple[str, ...] = ()
    approval_receipt_refs: tuple[str, ...] = ()
    idempotency_key: str
    deadline_at: str

    @model_validator(mode="after")
    def _check(self) -> "KarmaRefineRequest":
        if not self.sources:
            raise ValueError("refine request requires at least one source output")
        expected = derive_idempotency_key(
            run_id=self.run_id,
            factory_revision=self.factory_revision,
            edge_id=self.edge_id,
            source_output_digests=[s.output_digest for s in self.sources],
            target_schema_digest=self.target.input_contract.schema_digest,
            policy_digest=self.policy.digest,
        )
        if self.idempotency_key != expected:
            raise ValueError("idempotency_key does not match derived key for this edge")
        return self


class TransformLogEntry(BaseModel):
    """One field-level transformation Karma performed, with full lineage (§6.3)."""

    model_config = _FROZEN

    op: TransformOp
    target_path: str
    source_paths: tuple[str, ...] = ()
    rule_id: str
    evidence_refs: tuple[str, ...] = ()
    value_digest: Digest
    origin: TransformOrigin

    @model_validator(mode="after")
    def _check(self) -> "TransformLogEntry":
        assert_digest(self.value_digest, "transform.value_digest")
        return self


class EdgeViolation(BaseModel):
    """A schema/grounding/policy violation found while refining an edge."""

    model_config = _FROZEN

    code: str
    path: str
    severity: ViolationSeverity


class MapperRef(BaseModel):
    """Which Karma node/policy produced a receipt (audit dimension)."""

    model_config = _FROZEN

    planet: Literal["karma"] = "karma"
    node_id: str
    revision: str
    policy_digest: Digest

    @model_validator(mode="after")
    def _check(self) -> "MapperRef":
        assert_digest(self.policy_digest, "mapper.policy_digest")
        return self


class KarmaEdgeReceipt(BaseModel):
    """Immutable Karma decision that authorizes (or refuses) a target Planet (§6.3)."""

    model_config = _FROZEN

    receipt_id: str
    edge_id: str
    run_id: str
    factory_revision: int = Field(ge=0)
    source_output_digests: tuple[Digest, ...]
    target_contract: ContractRef
    decision: EdgeDecision
    target_input: dict[str, Any] | None = None
    target_input_digest: Digest | None = None
    transform_log: tuple[TransformLogEntry, ...] = ()
    violations: tuple[EdgeViolation, ...] = ()
    waiver_receipt_refs: tuple[str, ...] = ()
    mapper: MapperRef
    created_at: str

    @model_validator(mode="after")
    def _check(self) -> "KarmaEdgeReceipt":
        if not self.source_output_digests:
            raise ValueError("receipt must reference at least one source output digest")
        for d in self.source_output_digests:
            if not is_digest(d):
                raise ValueError(f"source_output_digest malformed: {d!r}")

        has_error = any(v.severity == "error" for v in self.violations)

        if self.decision == "accepted":
            if has_error:
                raise ValueError("accepted receipt cannot carry error-severity violations")
            if self.target_input is None or self.target_input_digest is None:
                raise ValueError("accepted receipt must carry target_input + target_input_digest")
            if self.target_input_digest != sha256_digest(self.target_input):
                raise ValueError("target_input_digest does not match target_input")
        else:  # blocked | needs_human
            if self.target_input is not None or self.target_input_digest is not None:
                raise ValueError(
                    f"{self.decision} receipt must not carry a target_input projection"
                )
        return self

    def authorizes(self, target_input_digest: Digest) -> bool:
        """True iff this receipt accepts an edge whose target input matches byte-for-byte.

        The target Planet calls this after recomputing the digest of what it was
        handed — a mismatch means the input was altered in transit (§4.2 step 6).
        """
        return (
            self.decision == "accepted"
            and self.target_input_digest is not None
            and self.target_input_digest == target_input_digest
        )


def derive_idempotency_key(
    *,
    run_id: str,
    factory_revision: int,
    edge_id: str,
    source_output_digests: list[Digest] | tuple[Digest, ...],
    target_schema_digest: Digest,
    policy_digest: Digest,
) -> str:
    """Deterministic idempotency key for an edge (§6.3).

    ``SHA256(run_id | factory_revision | edge_id | ordered source_output_digests |
             target schema digest | Karma policy digest)``

    Source digest order is significant and preserved (fan-in ordering is part of
    the identity). Same inputs → same key; any change → different key.
    """
    material = canonical_json(
        [
            run_id,
            factory_revision,
            edge_id,
            list(source_output_digests),
            target_schema_digest,
            policy_digest,
        ]
    )
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()
