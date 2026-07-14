"""Immutable PlanetOutput envelope builder — digest-linked node output.

PRD_BIG_FOOTSTEP phase 6: Version node outputs to emit verifiable PlanetOutput
with payload digest, producer metadata, contract version, and trace binding.
Preserves legacy compatibility by including both PlanetOutput and raw output.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .planet_output import (
    PlanetOutput,
    ContractRef,
    ArtifactRef,
)
from .digest import sha256_digest


class PlanetOutputBuilder:
    """Build immutable PlanetOutput envelopes with digest verification.

    Builder captures execution metadata (run_id, workspace_id, trace_id, execution_id)
    and wraps the node handler output, computing payload digest and output digest
    deterministically. Every PlanetOutput is immutable and digest-linked.
    """

    def __init__(
        self,
        *,
        run_id: str,
        workspace_id: str,
        trace_id: str,
        execution_id: str,
        node_id: str,
        planet: str,
    ):
        self.run_id = run_id
        self.workspace_id = workspace_id
        self.trace_id = trace_id
        self.execution_id = execution_id
        self.node_id = node_id
        self.planet = planet

    def build_output(
        self,
        output: dict[str, Any],
        *,
        output_id: str,
        producer_revision: str = "1.0.0",
        contract_name: str,
        contract_version: str,
        contract_schema_digest: str,
        attempt_no: int = 1,
        artifacts: tuple[ArtifactRef, ...] = (),
        prior_edge_receipt_id: str | None = None,
        factory_revision: int = 0,
    ) -> PlanetOutput:
        """Build immutable PlanetOutput with digest verification.

        Args:
            output: Handler's raw output dict.
            output_id: Unique output identifier (e.g., "out-janus-abc123").
            producer_revision: Producer planet's code revision.
            contract_name: Consumer contract name (e.g., "hiob.janus.brief").
            contract_version: Consumer contract version (e.g., "1.0.0").
            contract_schema_digest: Digest of consumer contract schema.
            attempt_no: Attempt number (≥1).
            artifacts: Tuple of ArtifactRef objects (binary artifact metadata).
            prior_edge_receipt_id: Previous Karma edge receipt ID (if chained).
            factory_revision: Factory schema revision (≥0).

        Returns:
            Immutable PlanetOutput with payload_digest and output_digest computed.
        Raises:
            ValueError: If digests don't match payload or if producer is invalid.
        """
        producer_dict = {
            "planet": self.planet,
            "node_id": self.node_id,
            "revision": producer_revision,
        }

        contract = ContractRef(
            name=contract_name,
            version=contract_version,
            schema_digest=contract_schema_digest,
        )

        # Emit timestamp in ISO 8601 UTC
        emitted_at = datetime.now(tz=timezone.utc).isoformat()

        # PlanetOutput.build() computes payload_digest and output_digest deterministically
        planet_output = PlanetOutput.build(
            output_id=output_id,
            run_id=self.run_id,
            factory_revision=factory_revision,
            workspace_id=self.workspace_id,
            trace_id=self.trace_id,
            execution_id=self.execution_id,
            attempt_no=attempt_no,
            producer=producer_dict,
            contract=contract,
            payload=dict(output),  # Ensure copy
            emitted_at=emitted_at,
            artifacts=artifacts,
            prior_edge_receipt_id=prior_edge_receipt_id,
        )

        return planet_output

    @staticmethod
    def verify_output(planet_output: PlanetOutput) -> bool:
        """Verify PlanetOutput is internally consistent (digests match payload).

        Returns:
            True iff payload_digest and output_digest are valid.
        """
        return planet_output.verify()
