"""Tests for PlanetOutputBuilder — verifying digest-linked envelope construction."""
from __future__ import annotations

import pytest

from hiob_contracts.factory import (
    PlanetOutputBuilder,
    sha256_digest,
    is_digest,
)


def test_builder_constructs_valid_planet_output():
    """PlanetOutputBuilder produces valid, digest-verified PlanetOutput."""
    builder = PlanetOutputBuilder(
        run_id="run-1",
        workspace_id="ws-1",
        trace_id="trace-1",
        execution_id="exec-1",
        node_id="janus.intake.interpret",
        planet="janus",
    )

    output = builder.build_output(
        output={"brief": "test brief", "items": [1, 2, 3]},
        output_id="out-janus-abc123",
        producer_revision="1.0.0",
        contract_name="hiob.janus.brief",
        contract_version="1.0.0",
        contract_schema_digest=sha256_digest({"schema": "janus.v1"}),
    )

    # Verify envelope is valid
    assert output.verify()
    assert output.output_id == "out-janus-abc123"
    assert output.run_id == "run-1"
    assert output.workspace_id == "ws-1"
    assert output.producer["planet"] == "janus"
    assert output.producer["node_id"] == "janus.intake.interpret"
    assert output.producer["revision"] == "1.0.0"
    assert is_digest(output.payload_digest)
    assert is_digest(output.output_digest)


def test_builder_payload_digest_deterministic():
    """Identical payloads produce identical payload digests."""
    builder1 = PlanetOutputBuilder(
        run_id="r1", workspace_id="w1", trace_id="t1", execution_id="e1",
        node_id="node1", planet="janus",
    )
    builder2 = PlanetOutputBuilder(
        run_id="r2", workspace_id="w2", trace_id="t2", execution_id="e2",
        node_id="node2", planet="ares",
    )

    payload = {"a": 1, "b": {"c": 2}}
    out1 = builder1.build_output(
        payload, output_id="out1",
        contract_name="test", contract_version="1.0", contract_schema_digest=sha256_digest({})
    )
    out2 = builder2.build_output(
        payload, output_id="out2",
        contract_name="test", contract_version="1.0", contract_schema_digest=sha256_digest({})
    )

    # Same payload → same payload_digest (despite different producers/metadata)
    assert out1.payload_digest == out2.payload_digest
    # Different output metadata → different output_digest
    assert out1.output_digest != out2.output_digest


def test_builder_output_digest_changes_with_payload():
    """Different payloads produce different digests."""
    builder = PlanetOutputBuilder(
        run_id="r", workspace_id="w", trace_id="t", execution_id="e",
        node_id="node", planet="janus",
    )

    out1 = builder.build_output(
        {"x": 1}, output_id="out1",
        contract_name="test", contract_version="1.0", contract_schema_digest=sha256_digest({})
    )
    out2 = builder.build_output(
        {"x": 2}, output_id="out2",
        contract_name="test", contract_version="1.0", contract_schema_digest=sha256_digest({})
    )

    assert out1.payload_digest != out2.payload_digest
    assert out1.output_digest != out2.output_digest


def test_builder_with_artifacts():
    """Builder can include ArtifactRef objects (binary metadata)."""
    from hiob_contracts.factory import ArtifactRef

    artifact = ArtifactRef(
        artifact_id="a1",
        kind="image",
        uri="s3://bucket/image.png",
        sha256=sha256_digest({"image": "data"}),
        mime="image/png",
        bytes_len=1024,
        producer_planet="athena",
        producer_node_id="athena.materialize",
        execution_id="exec-1",
        producer_revision="r1",
    )

    builder = PlanetOutputBuilder(
        run_id="r", workspace_id="w", trace_id="t", execution_id="e",
        node_id="athena.node", planet="athena",
    )

    output = builder.build_output(
        {"images": [{"uri": "s3://..."}]},
        output_id="out-1",
        contract_name="hiob.athena.media",
        contract_version="1.0.0",
        contract_schema_digest=sha256_digest({}),
        artifacts=(artifact,),
    )

    assert output.artifacts == (artifact,)
    assert output.verify()


def test_verify_output_static_method():
    """Static verify_output method works on constructed outputs."""
    builder = PlanetOutputBuilder(
        run_id="r", workspace_id="w", trace_id="t", execution_id="e",
        node_id="node", planet="janus",
    )

    output = builder.build_output(
        {"data": "test"}, output_id="out1",
        contract_name="test", contract_version="1.0", contract_schema_digest=sha256_digest({})
    )

    assert PlanetOutputBuilder.verify_output(output) is True


def test_builder_with_custom_contract_schema_digest():
    """Builder accepts explicit contract schema digest."""
    custom_digest = sha256_digest({"my_contract": "schema"})
    builder = PlanetOutputBuilder(
        run_id="r", workspace_id="w", trace_id="t", execution_id="e",
        node_id="node", planet="test",
    )

    output = builder.build_output(
        {"x": 1}, output_id="out1",
        contract_name="custom.contract",
        contract_version="2.1.0",
        contract_schema_digest=custom_digest,
    )

    assert output.contract.schema_digest == custom_digest
    assert output.contract.name == "custom.contract"
    assert output.contract.version == "2.1.0"
