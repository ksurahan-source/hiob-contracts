"""`PlanetOutput` and `ArtifactRef` — the immutable envelopes every Planet emits.

PRD_CREATIVE_FACTORY_HARMONY §6.1 (`PlanetOutputV1<T>`) and §6.4 (`ArtifactRefV1`).

A Planet never hands another Planet a bare payload. It emits a `PlanetOutput`:
an immutable, digest-linked envelope carrying the payload as a canonical JSON
object plus references to any binary artifacts. Binary bytes never travel in the
JSON edge envelope — only `ArtifactRef`s that point at them.

The payload's *type* is owned by the producing Planet and `hiob-contracts`
(referenced via `ContractRef.schema_digest`), not by this envelope; the envelope
carries the already-validated payload as a JSON object and binds it by digest.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from .digest import Digest, assert_digest, is_digest, sha256_digest

_FROZEN = {"frozen": True, "extra": "forbid"}


class ContractRef(BaseModel):
    """Reference to a versioned contract schema (name + version + schema digest)."""

    model_config = _FROZEN

    name: str
    version: str
    schema_digest: Digest

    @model_validator(mode="after")
    def _check_digest(self) -> "ContractRef":
        assert_digest(self.schema_digest, "contract.schema_digest")
        return self


class ArtifactRef(BaseModel):
    """Immutable reference to one produced binary artifact (§6.4).

    JSON carries this reference; the bytes live at `uri` and are bound by `sha256`.
    Lineage is explicit: `source_output_digests` and `edge_receipt_digests` record
    which upstream outputs and Karma edges produced this artifact.
    """

    model_config = _FROZEN

    artifact_id: str
    kind: str
    uri: str
    sha256: Digest
    mime: str
    bytes_len: int = Field(ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    beat_index: int | None = Field(default=None, ge=0)
    producer_planet: str
    producer_node_id: str
    execution_id: str
    producer_revision: str
    image_digest: Digest | None = None
    source_output_digests: tuple[Digest, ...] = ()
    edge_receipt_digests: tuple[Digest, ...] = ()
    provenance_refs: tuple[str, ...] = ()
    consent_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _check_digests(self) -> "ArtifactRef":
        assert_digest(self.sha256, "artifact.sha256")
        if self.image_digest is not None:
            assert_digest(self.image_digest, "artifact.image_digest")
        for d in (*self.source_output_digests, *self.edge_receipt_digests):
            if not is_digest(d):
                raise ValueError(f"artifact lineage digest malformed: {d!r}")
        return self


class PlanetOutput(BaseModel):
    """Immutable typed output a Planet returns over HTTP (§6.1).

    `payload` is a canonical JSON object already validated against `contract`.
    `payload_digest` binds the payload; `output_digest` binds the whole envelope
    (every field except `output_digest` itself). Use `finalize()` to compute both
    deterministically and `verify()` to reject tampering downstream.
    """

    model_config = _FROZEN

    schema_: str = Field(default="hiob.planet-output.v1", alias="schema")
    output_id: str
    run_id: str
    factory_revision: int = Field(ge=0)
    workspace_id: str
    trace_id: str
    execution_id: str
    attempt_no: int = Field(ge=1)
    producer: dict[str, str]  # {planet, node_id, revision}
    contract: ContractRef
    payload: dict[str, Any]
    payload_digest: Digest
    artifacts: tuple[ArtifactRef, ...] = ()
    output_digest: Digest
    prior_edge_receipt_id: str | None = None
    emitted_at: str

    @model_validator(mode="after")
    def _check(self) -> "PlanetOutput":
        for key in ("planet", "node_id", "revision"):
            if key not in self.producer:
                raise ValueError(f"producer missing required key: {key}")
        if self.payload_digest != sha256_digest(self.payload):
            raise ValueError("payload_digest does not match payload")
        if self.output_digest != _compute_output_digest(self):
            raise ValueError("output_digest does not match envelope contents")
        return self

    @classmethod
    def build(
        cls,
        *,
        output_id: str,
        run_id: str,
        factory_revision: int,
        workspace_id: str,
        trace_id: str,
        execution_id: str,
        attempt_no: int,
        producer: dict[str, str],
        contract: ContractRef,
        payload: dict[str, Any],
        emitted_at: str,
        artifacts: tuple[ArtifactRef, ...] = (),
        prior_edge_receipt_id: str | None = None,
    ) -> "PlanetOutput":
        """Construct with `payload_digest`/`output_digest` computed deterministically."""
        payload_digest = sha256_digest(payload)
        draft = cls.model_construct(
            schema_="hiob.planet-output.v1",
            output_id=output_id,
            run_id=run_id,
            factory_revision=factory_revision,
            workspace_id=workspace_id,
            trace_id=trace_id,
            execution_id=execution_id,
            attempt_no=attempt_no,
            producer=dict(producer),
            contract=contract,
            payload=dict(payload),
            payload_digest=payload_digest,
            artifacts=tuple(artifacts),
            output_digest="sha256:" + "0" * 64,
            prior_edge_receipt_id=prior_edge_receipt_id,
            emitted_at=emitted_at,
        )
        output_digest = _compute_output_digest(draft)
        # Re-validate through the normal path so illegal states still fail closed.
        return cls.model_validate(
            {**draft.model_dump(by_alias=True), "output_digest": output_digest}
        )

    def verify(self) -> bool:
        """Recompute digests and confirm the envelope is internally consistent."""
        return self.payload_digest == sha256_digest(self.payload) and (
            self.output_digest == _compute_output_digest(self)
        )


def _compute_output_digest(out: PlanetOutput) -> Digest:
    """Digest of the whole envelope with `output_digest` excluded (avoids self-ref)."""
    body = out.model_dump(by_alias=True)
    body.pop("output_digest", None)
    return sha256_digest(body)
