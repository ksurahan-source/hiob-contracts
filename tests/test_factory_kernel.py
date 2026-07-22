"""Property tests for the Creative Factory Harmony kernel (PRD 2026-07-14 §6–§7).

Phase 1 exit gate: "deterministic offline contract graph and property tests
reject illegal states." Every test below asserts either a valid construction
round-trips with consistent digests, or an *illegal* state fails closed.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiob_contracts.factory import (
    ApprovalReceipt,
    ArtifactRef,
    ContractRef,
    DegradationReceipt,
    EdgeViolation,
    EDGES,
    FactoryState,
    KarmaEdgeReceipt,
    KarmaRefineRequest,
    MapperRef,
    PlanetOutput,
    PolicyRef,
    StageError,
    StageReceipt,
    TargetRef,
    assert_transition,
    can_transition,
    canonical_json,
    derive_idempotency_key,
    get_edge,
    is_digest,
    is_registered_edge,
    required_edges,
    sha256_digest,
)
from hiob_contracts.factory.digest import DigestError

# ── helpers ──────────────────────────────────────────────────────────────────
SCHEMA_DIGEST = sha256_digest({"schema": "example.v1"})
POLICY_DIGEST = sha256_digest({"policy": "p1"})


def _contract(name: str = "JanusBrief") -> ContractRef:
    return ContractRef(name=name, version="v1", schema_digest=SCHEMA_DIGEST)


def _planet_output(payload: dict | None = None, planet: str = "janus") -> PlanetOutput:
    return PlanetOutput.build(
        output_id=f"out-{planet}",
        run_id="run-1",
        factory_revision=0,
        workspace_id="ws-1",
        trace_id="trace-1",
        execution_id="exec-1",
        attempt_no=1,
        producer={"planet": planet, "node_id": f"{planet}.node", "revision": "r1"},
        contract=_contract(),
        payload=payload if payload is not None else {"brief": "hello", "n": 3},
        emitted_at="2026-07-14T00:00:00Z",
    )


# ── digest ───────────────────────────────────────────────────────────────────
def test_canonical_json_sorts_keys_recursively():
    a = canonical_json({"b": 1, "a": {"y": 2, "x": 1}})
    b = canonical_json({"a": {"x": 1, "y": 2}, "b": 1})
    assert a == b == '{"a":{"x":1,"y":2},"b":1}'


def test_canonical_json_preserves_array_order():
    assert canonical_json([3, 1, 2]) != canonical_json([1, 2, 3])


def test_sha256_digest_shape_and_stability():
    d = sha256_digest({"x": 1})
    assert is_digest(d)
    assert d == sha256_digest({"x": 1})


def test_canonical_json_rejects_non_finite():
    with pytest.raises(DigestError):
        canonical_json({"x": float("nan")})
    with pytest.raises(DigestError):
        canonical_json([float("inf")])


# ── PlanetOutput / ArtifactRef ────────────────────────────────────────────────
def test_planet_output_build_verifies():
    out = _planet_output()
    assert out.verify()
    assert out.payload_digest == sha256_digest(out.payload)
    assert is_digest(out.output_digest)


def test_planet_output_tampered_payload_digest_rejected():
    out = _planet_output()
    data = out.model_dump(by_alias=True)
    data["payload"] = {"brief": "TAMPERED"}  # digest no longer matches
    with pytest.raises(ValidationError):
        PlanetOutput.model_validate(data)


def test_planet_output_tampered_output_digest_rejected():
    out = _planet_output()
    data = out.model_dump(by_alias=True)
    data["output_digest"] = sha256_digest({"not": "the envelope"})
    with pytest.raises(ValidationError):
        PlanetOutput.model_validate(data)


def test_planet_output_missing_producer_key_rejected():
    with pytest.raises((ValidationError, ValueError)):
        PlanetOutput.build(
            output_id="o", run_id="r", factory_revision=0, workspace_id="w",
            trace_id="t", execution_id="e", attempt_no=1,
            producer={"planet": "janus"},  # missing node_id, revision
            contract=_contract(), payload={"a": 1}, emitted_at="2026-07-14T00:00:00Z",
        )


def test_artifact_ref_malformed_sha_rejected():
    with pytest.raises(ValidationError):
        ArtifactRef(
            artifact_id="a1", kind="image", uri="s3://x", sha256="notadigest",
            mime="image/png", bytes_len=10, producer_planet="athena",
            producer_node_id="athena.materialize", execution_id="e", producer_revision="r",
        )


def test_artifact_ref_negative_bytes_rejected():
    with pytest.raises(ValidationError):
        ArtifactRef(
            artifact_id="a1", kind="image", uri="s3://x", sha256=SCHEMA_DIGEST,
            mime="image/png", bytes_len=-1, producer_planet="athena",
            producer_node_id="athena.materialize", execution_id="e", producer_revision="r",
        )


# ── idempotency key ───────────────────────────────────────────────────────────
def test_idempotency_key_deterministic_and_order_sensitive():
    base = dict(run_id="r", factory_revision=0, edge_id="j2p",
                target_schema_digest=SCHEMA_DIGEST, policy_digest=POLICY_DIGEST)
    d1, d2 = sha256_digest({"a": 1}), sha256_digest({"a": 2})
    k1 = derive_idempotency_key(source_output_digests=[d1, d2], **base)
    k2 = derive_idempotency_key(source_output_digests=[d1, d2], **base)
    k_swapped = derive_idempotency_key(source_output_digests=[d2, d1], **base)
    assert k1 == k2
    assert k1 != k_swapped  # fan-in order is part of identity
    assert is_digest(k1)


def test_refine_request_bad_idempotency_key_rejected():
    src = _planet_output()
    good = derive_idempotency_key(
        run_id="run-1", factory_revision=0, edge_id="j2p",
        source_output_digests=[src.output_digest],
        target_schema_digest=SCHEMA_DIGEST, policy_digest=POLICY_DIGEST,
    )
    common = dict(
        edge_id="j2p", run_id="run-1", factory_revision=0, workspace_id="ws-1",
        trace_id="t", sources=(src,),
        target=TargetRef(planet="parzifal", node_id="parzifal.target.consolidate",
                         input_contract=_contract("ParzifalTargetInput")),
        policy=PolicyRef(id="policy.j2p", version="v1", digest=POLICY_DIGEST),
        deadline_at="2026-07-14T01:00:00Z",
    )
    KarmaRefineRequest(idempotency_key=good, **common)  # ok
    with pytest.raises(ValidationError):
        KarmaRefineRequest(idempotency_key="sha256:" + "0" * 64, **common)


def test_refine_request_requires_sources():
    with pytest.raises(ValidationError):
        KarmaRefineRequest(
            edge_id="j2p", run_id="r", factory_revision=0, workspace_id="w", trace_id="t",
            sources=(), target=TargetRef(planet="p", node_id="n", input_contract=_contract()),
            policy=PolicyRef(id="x", version="v1", digest=POLICY_DIGEST),
            idempotency_key="sha256:" + "0" * 64, deadline_at="2026-07-14T01:00:00Z",
        )


# ── KarmaEdgeReceipt invariants ───────────────────────────────────────────────
def _mapper() -> MapperRef:
    return MapperRef(node_id="karma.edge.refine", revision="r1", policy_digest=POLICY_DIGEST)


def _accepted_receipt(target_input: dict) -> KarmaEdgeReceipt:
    return KarmaEdgeReceipt(
        receipt_id="rcpt-1", edge_id="j2p", run_id="r", factory_revision=0,
        source_output_digests=(sha256_digest({"a": 1}),),
        target_contract=_contract("ParzifalTargetInput"),
        decision="accepted", target_input=target_input,
        target_input_digest=sha256_digest(target_input),
        mapper=_mapper(), created_at="2026-07-14T00:00:00Z",
    )


def test_accepted_receipt_authorizes_matching_digest():
    ti = {"target": "value"}
    r = _accepted_receipt(ti)
    assert r.authorizes(sha256_digest(ti))
    assert not r.authorizes(sha256_digest({"other": 1}))


def test_accepted_without_target_input_rejected():
    with pytest.raises(ValidationError):
        KarmaEdgeReceipt(
            receipt_id="r", edge_id="j2p", run_id="r", factory_revision=0,
            source_output_digests=(sha256_digest({"a": 1}),),
            target_contract=_contract(), decision="accepted",
            mapper=_mapper(), created_at="2026-07-14T00:00:00Z",
        )


def test_accepted_with_mismatched_target_digest_rejected():
    with pytest.raises(ValidationError):
        KarmaEdgeReceipt(
            receipt_id="r", edge_id="j2p", run_id="r", factory_revision=0,
            source_output_digests=(sha256_digest({"a": 1}),),
            target_contract=_contract(), decision="accepted",
            target_input={"x": 1}, target_input_digest=sha256_digest({"x": 2}),
            mapper=_mapper(), created_at="2026-07-14T00:00:00Z",
        )


def test_accepted_with_error_violation_rejected():
    with pytest.raises(ValidationError):
        KarmaEdgeReceipt(
            receipt_id="r", edge_id="j2p", run_id="r", factory_revision=0,
            source_output_digests=(sha256_digest({"a": 1}),),
            target_contract=_contract(), decision="accepted",
            target_input={"x": 1}, target_input_digest=sha256_digest({"x": 1}),
            violations=(EdgeViolation(code="E1", path="/x", severity="error"),),
            mapper=_mapper(), created_at="2026-07-14T00:00:00Z",
        )


@pytest.mark.parametrize("decision", ["blocked", "needs_human"])
def test_blocked_receipt_must_not_carry_target_input(decision):
    with pytest.raises(ValidationError):
        KarmaEdgeReceipt(
            receipt_id="r", edge_id="j2p", run_id="r", factory_revision=0,
            source_output_digests=(sha256_digest({"a": 1}),),
            target_contract=_contract(), decision=decision,
            target_input={"x": 1}, target_input_digest=sha256_digest({"x": 1}),
            mapper=_mapper(), created_at="2026-07-14T00:00:00Z",
        )


@pytest.mark.parametrize("decision", ["blocked", "needs_human"])
def test_blocked_receipt_does_not_authorize(decision):
    r = KarmaEdgeReceipt(
        receipt_id="r", edge_id="j2p", run_id="r", factory_revision=0,
        source_output_digests=(sha256_digest({"a": 1}),),
        target_contract=_contract(), decision=decision,
        mapper=_mapper(), created_at="2026-07-14T00:00:00Z",
    )
    assert not r.authorizes(sha256_digest({"anything": 1}))


# ── StageReceipt invariants (spawn handle ≠ success) ──────────────────────────
def test_succeeded_requires_output_and_completion():
    r = StageReceipt(
        operation_id="op", stage_id="s", planet="athena", node_id="athena.materialize",
        producer_revision="r", contract_version="v1", output_digests=(sha256_digest({"a": 1}),),
        status="succeeded", attempt_no=1, started_at="t0", completed_at="t1",
    )
    assert r.is_success and r.is_terminal


def test_succeeded_without_output_rejected():
    with pytest.raises(ValidationError):
        StageReceipt(
            operation_id="op", stage_id="s", planet="athena", node_id="n",
            producer_revision="r", contract_version="v1", status="succeeded",
            attempt_no=1, started_at="t0", completed_at="t1",
        )


def test_accepted_status_is_not_terminal_and_forbids_completed_at():
    r = StageReceipt(
        operation_id="op", stage_id="s", planet="athena", node_id="n",
        producer_revision="r", contract_version="v1", status="accepted",
        attempt_no=1, started_at="t0",
    )
    assert not r.is_terminal and not r.is_success
    with pytest.raises(ValidationError):
        StageReceipt(
            operation_id="op", stage_id="s", planet="athena", node_id="n",
            producer_revision="r", contract_version="v1", status="running",
            attempt_no=1, started_at="t0", completed_at="t1",
        )


def test_failed_requires_error():
    with pytest.raises(ValidationError):
        StageReceipt(
            operation_id="op", stage_id="s", planet="athena", node_id="n",
            producer_revision="r", contract_version="v1", status="failed",
            attempt_no=1, started_at="t0", completed_at="t1",
        )
    StageReceipt(
        operation_id="op", stage_id="s", planet="athena", node_id="n",
        producer_revision="r", contract_version="v1", status="failed",
        attempt_no=1, started_at="t0", completed_at="t1",
        error=StageError(code="X", retryable=True),
    )


# ── ApprovalReceipt ───────────────────────────────────────────────────────────
def test_approval_authorizes_exact_digest_only():
    d = sha256_digest({"snapshot": "final"})
    a = ApprovalReceipt(
        approval_id="ap", kind="composition_snapshot", run_id="r", factory_revision=1,
        target_id="snap-1", target_digest=d, decision="approved", approved_by="u1",
        approved_at="t", policy_version="v1",
    )
    assert a.authorizes(d)
    assert not a.authorizes(sha256_digest({"snapshot": "other"}))


def test_approval_rejects_revoked_expired_and_rejected():
    d = sha256_digest({"s": 1})
    revoked = ApprovalReceipt(
        approval_id="ap", kind="script", run_id="r", factory_revision=0, target_id="t",
        target_digest=d, decision="approved", approved_by="u", approved_at="t",
        policy_version="v1", revoked_at="t2",
    )
    assert not revoked.authorizes(d)
    expired = ApprovalReceipt(
        approval_id="ap", kind="script", run_id="r", factory_revision=0, target_id="t",
        target_digest=d, decision="approved", approved_by="u", approved_at="t",
        policy_version="v1", expires_at="2026-01-01T00:00:00Z",
    )
    assert not expired.authorizes(d, now="2026-07-14T00:00:00Z")
    rejected = ApprovalReceipt(
        approval_id="ap", kind="script", run_id="r", factory_revision=0, target_id="t",
        target_digest=d, decision="rejected", approved_by="u", approved_at="t",
        policy_version="v1",
    )
    assert not rejected.authorizes(d)


# ── DegradationReceipt ────────────────────────────────────────────────────────
def test_degradation_requires_impact_and_recovery():
    ok = DegradationReceipt(
        degradation_id="dg", run_id="r", factory_revision=0, omitted_stage="apollo.materialize",
        omitted_artifact_kind="sfx", plan_digest=sha256_digest({"plan": 1}),
        user_impact="No sound effects", authorized_by="policy.optional_sfx",
        recovery_action="Re-run apollo edge", created_at="t",
    )
    assert ok.omitted_stage == "apollo.materialize"
    with pytest.raises(ValidationError):
        DegradationReceipt(
            degradation_id="dg", run_id="r", factory_revision=0, omitted_stage="x",
            omitted_artifact_kind="sfx", plan_digest=sha256_digest({"plan": 1}),
            user_impact="   ", authorized_by="p", recovery_action="y", created_at="t",
        )


# ── FactoryState transitions ──────────────────────────────────────────────────
def test_linear_transition_allowed_but_skips_rejected():
    assert can_transition(FactoryState.CREATED, FactoryState.PLANNING)
    assert not can_transition(FactoryState.CREATED, FactoryState.MEDIA_PLANNING)


def test_terminal_states_never_reopen():
    for term in (FactoryState.SUCCEEDED, FactoryState.FAILED, FactoryState.CANCELLED):
        assert not can_transition(term, FactoryState.PLANNING)


def test_any_nonterminal_can_enter_exception():
    assert can_transition(FactoryState.MATERIALIZING, FactoryState.BLOCKED)
    assert can_transition(FactoryState.PLANNING, FactoryState.FAILED)


def test_blocked_resumes_to_nonterminal():
    assert can_transition(FactoryState.BLOCKED, FactoryState.MATERIALIZING)
    assert not can_transition(FactoryState.BLOCKED, FactoryState.SUCCEEDED)


def test_gate_rejection_loops_back():
    assert can_transition(FactoryState.WAITING_SCRIPT_APPROVAL, FactoryState.PLANNING)
    assert can_transition(FactoryState.WAITING_FINAL_APPROVAL, FactoryState.EDITORIAL_REVIEW)


def test_assert_transition_raises_on_illegal():
    with pytest.raises(ValueError):
        assert_transition(FactoryState.CREATED, FactoryState.RENDERING)


# ── edge registry ─────────────────────────────────────────────────────────────
def test_registered_edges_cover_flow():
    ids = {e.edge_id for e in EDGES}
    assert {"j2p", "p2a", "a2athena", "a2orpheus", "a2apollo",
            "media2atropos", "atropos2artemis", "artemis2atropos",
            "atropos2hephaestus"} <= ids


def test_is_registered_edge_direct_and_fanin():
    assert is_registered_edge("janus", "parzifal")
    assert is_registered_edge("ares", "athena")
    # fan-in: each media component is a registered source into atropos
    assert is_registered_edge("athena", "atropos")
    assert is_registered_edge("orpheus", "atropos")
    assert is_registered_edge("apollo", "atropos")


def test_unregistered_edge_rejected():
    assert not is_registered_edge("janus", "hephaestus")
    assert not is_registered_edge("ares", "atropos")


def test_optional_and_required_edge_criticality():
    # Optional: Apollo SFX enhancement + SUNSET editorial loop (not on F1 spine).
    assert get_edge("a2apollo").criticality == "optional"
    assert get_edge("atropos2artemis").criticality == "optional"
    assert get_edge("artemis2atropos").criticality == "optional"
    assert get_edge("a2apollo") not in required_edges()
    assert get_edge("atropos2artemis") not in required_edges()
    assert get_edge("artemis2atropos") not in required_edges()
    # Required spine still blocks without these.
    assert get_edge("j2p").criticality == "required"
    assert get_edge("j2p") in required_edges()
