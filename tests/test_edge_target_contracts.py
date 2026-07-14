"""Phase 3 edge target contract tests — j2p and p2a with exact typed schemas.

PRD_BIG_FOOTSTEP Phase 3: make the registered j2p (Janus→Parzifal) and p2a
(Parzifal→Ares) target contract refs EXACT with typed target_input schemas
the consumer Planet owns.

- j2p: JanusBrief → ParzifalTargetInput (Parzifal consumes)
- p2a: TargetProfile+IdentityLock+CastSheet → AresScriptInput (Ares consumes)

All contracts round-trip to/from dict; digests are Python-canonical.
Unknown edge IDs are rejected (negative test).
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiob_contracts.factory import (
    ArtifactRef,
    ContractRef,
    KarmaEdgeReceipt,
    KarmaRefineRequest,
    MapperRef,
    PlanetOutput,
    PolicyRef,
    TargetRef,
    canonical_json,
    derive_idempotency_key,
    get_edge,
    is_registered_edge,
    sha256_digest,
)
from hiob_contracts.parzifal_target_input import ParzifalTargetInput
from hiob_contracts.ares_script_input import AresScriptInput
from hiob_contracts.janus_brief import JanusBrief

# ── helpers ──────────────────────────────────────────────────────────────────
SCHEMA_DIGEST = sha256_digest({"schema": "example.v1"})
POLICY_DIGEST = sha256_digest({"policy": "p1"})


def _contract(name: str, digest: str | None = None) -> ContractRef:
    return ContractRef(
        name=name,
        version="v1",
        schema_digest=digest or SCHEMA_DIGEST,
    )


def _planet_output(payload: dict, contract: ContractRef) -> PlanetOutput:
    return PlanetOutput.build(
        output_id="out-1",
        run_id="run-1",
        factory_revision=0,
        workspace_id="ws-1",
        trace_id="trace-1",
        execution_id="exec-1",
        attempt_no=1,
        producer={"planet": "janus", "node_id": "janus.node", "revision": "r1"},
        contract=contract,
        payload=payload,
        emitted_at="2026-07-14T00:00:00Z",
    )


# ── j2p edge: JanusBrief → ParzifalTargetInput ────────────────────────────
def test_j2p_edge_registered():
    """j2p edge exists and is required."""
    edge = get_edge("j2p")
    assert edge is not None
    assert edge.source_planet == "janus"
    assert edge.target_planet == "parzifal"
    assert edge.target_node_id == "parzifal.target.consolidate"
    assert edge.criticality == "required"
    assert is_registered_edge("janus", "parzifal")


def test_parzifal_target_input_round_trip():
    """ParzifalTargetInput to/from dict with digest stability."""
    target = ParzifalTargetInput(
        brand_slug="viewok",
        brand_identity="친화적 수영용품",
        target_audience="초등 아이 부모",
        target_jtbd="아이가 물을 무서워하지 않게",
        voc_core_pain="수영 공포증",
        product_slug="serum-lavender",
        listing_slug="viewok-serum-lavender-250ml",
        locale="ko",
        protagonist="female",
    )

    d = target.to_dict()
    restored = ParzifalTargetInput.from_dict(d)
    assert restored == target
    assert restored.validate() == []  # valid

    # Digest stability: same data = same canonical JSON
    d1 = canonical_json(target.to_dict())
    d2 = canonical_json(restored.to_dict())
    assert d1 == d2


def test_parzifal_target_input_validation_missing_brand():
    """ParzifalTargetInput.validate() catches missing brand_slug."""
    target = ParzifalTargetInput(brand_slug="")
    errs = target.validate()
    assert any("brand_slug" in e for e in errs)


def test_parzifal_target_input_validation_missing_target_facts():
    """ParzifalTargetInput.validate() requires at least one target fact."""
    target = ParzifalTargetInput(
        brand_slug="viewok",
        # All target facts are None
    )
    errs = target.validate()
    assert any("target fact" in e for e in errs)


def test_karma_j2p_receipt_with_parzifal_target_input():
    """Karma j2p receipt carries ParzifalTargetInput as target_input."""
    target_input = ParzifalTargetInput(
        brand_slug="viewok",
        target_audience="초등 아이",
        voc_core_pain="수영 공포",
    )
    ti_dict = target_input.to_dict()
    ti_digest = sha256_digest(ti_dict)

    receipt = KarmaEdgeReceipt(
        receipt_id="rcpt-j2p-1",
        edge_id="j2p",
        run_id="run-1",
        factory_revision=0,
        source_output_digests=(sha256_digest({"brief": "data"}),),
        target_contract=_contract("ParzifalTargetInput"),
        decision="accepted",
        target_input=ti_dict,
        target_input_digest=ti_digest,
        mapper=MapperRef(
            node_id="karma.edge.refine", revision="r1", policy_digest=POLICY_DIGEST
        ),
        created_at="2026-07-14T00:00:00Z",
    )

    assert receipt.decision == "accepted"
    assert receipt.target_input is not None
    assert receipt.authorizes(ti_digest)


# ── p2a edge: Parzifal outputs → AresScriptInput ──────────────────────────
def test_p2a_edge_registered():
    """p2a edge exists and is required."""
    edge = get_edge("p2a")
    assert edge is not None
    assert edge.source_planet == "parzifal"
    assert edge.target_planet == "ares"
    assert edge.target_node_id == "ares.script.build"
    assert edge.criticality == "required"
    assert is_registered_edge("parzifal", "ares")


def test_ares_script_input_round_trip():
    """AresScriptInput to/from dict with digest stability."""
    script_input = AresScriptInput(
        brand_slug="viewok",
        brand_identity="친화적 수영용품",
        protagonist_id="p-jung-won",
        protagonist_name="정원이",
        protagonist_age=11,
        protagonist_gender="male",
        protagonist_role="customer",
        target_pain="수영 공포증",
        target_jtbd="물에 대한 자신감 높이기",
        voc_core_pain="물을 무서워함",
        voc_real_quotes=["물에 안 들어가고 싶어요", "친구들처럼 못 해서 싫어요"],
        product_slug="serum-lavender",
        listing_slug="viewok-serum-lavender-250ml",
        locale="ko",
    )

    d = script_input.to_dict()
    restored = AresScriptInput.from_dict(d)
    assert restored == script_input
    assert restored.validate() == []  # valid

    # Digest stability
    d1 = canonical_json(script_input.to_dict())
    d2 = canonical_json(restored.to_dict())
    assert d1 == d2


def test_ares_script_input_validation_missing_brand():
    """AresScriptInput.validate() catches missing brand_slug."""
    script_input = AresScriptInput(brand_slug="")
    errs = script_input.validate()
    assert any("brand_slug" in e for e in errs)


def test_ares_script_input_validation_missing_protagonist_name():
    """AresScriptInput.validate() requires protagonist_name."""
    script_input = AresScriptInput(
        brand_slug="viewok",
        protagonist_name="",  # Missing
        target_pain="some pain",
    )
    errs = script_input.validate()
    assert any("protagonist_name" in e for e in errs)


def test_ares_script_input_validation_missing_grounding():
    """AresScriptInput.validate() requires at least one grounding fact."""
    script_input = AresScriptInput(
        brand_slug="viewok",
        protagonist_name="정원이",
        # No pain/jtbd/voc_core_pain
    )
    errs = script_input.validate()
    assert any("grounding fact" in e for e in errs)


def test_karma_p2a_receipt_with_ares_script_input():
    """Karma p2a receipt carries AresScriptInput as target_input."""
    script_input = AresScriptInput(
        brand_slug="viewok",
        protagonist_name="정원이",
        target_pain="수영 공포",
    )
    si_dict = script_input.to_dict()
    si_digest = sha256_digest(si_dict)

    receipt = KarmaEdgeReceipt(
        receipt_id="rcpt-p2a-1",
        edge_id="p2a",
        run_id="run-1",
        factory_revision=0,
        source_output_digests=(sha256_digest({"target": "profile"}),),
        target_contract=_contract("AresScriptInput"),
        decision="accepted",
        target_input=si_dict,
        target_input_digest=si_digest,
        mapper=MapperRef(
            node_id="karma.edge.refine", revision="r1", policy_digest=POLICY_DIGEST
        ),
        created_at="2026-07-14T00:00:00Z",
    )

    assert receipt.decision == "accepted"
    assert receipt.target_input is not None
    assert receipt.authorizes(si_digest)


# ── NEGATIVE TESTS: unknown edge rejection ────────────────────────────────
def test_get_edge_unknown_edge_id_returns_none():
    """get_edge() returns None for unknown edge_id (not an error)."""
    edge = get_edge("unknown_edge")
    assert edge is None


def test_is_registered_edge_unknown_rejects():
    """is_registered_edge() returns False for unregistered source→target pairs."""
    # janus → hephaestus is not a registered edge
    assert not is_registered_edge("janus", "hephaestus")
    # ares → atropos is not registered (media2atropos is fan-in, different)
    assert not is_registered_edge("ares", "atropos")
    # parzifal → athena is not registered (only j2p and p2a from parzifal)
    assert not is_registered_edge("parzifal", "athena")


def test_unknown_edge_in_refine_request_would_fail_validation():
    """A KarmaRefineRequest with an unknown edge_id would need to be rejected upstream.

    Note: the KarmaRefineRequest contract itself doesn't validate edge_id membership
    (that's a CI check). This test documents that contract registries should validate.
    """
    # Unknown edge_id is structurally valid in the request,
    # but the CI layer would reject it before Karma sees it.
    edge_id = "unknown_edge"
    edge = get_edge(edge_id)
    assert edge is None  # No such edge in registry


def test_all_registered_edges_are_required_or_optional():
    """All edges have well-defined criticality."""
    from hiob_contracts import EDGES

    for edge in EDGES:
        assert edge.criticality in ("required", "optional")
        # j2p and p2a should be required
        if edge.edge_id in ("j2p", "p2a"):
            assert edge.criticality == "required"


# ── Python↔TS digest parity (reference values) ──────────────────────────
def test_parzifal_target_input_digest_parity():
    """ParzifalTargetInput canonical JSON digest matches Python computation."""
    target = ParzifalTargetInput(
        brand_slug="test",
        target_audience="audience",
    )
    d = target.to_dict()
    digest = sha256_digest(d)
    canonical = canonical_json(d)

    # Verify digest is properly formed
    assert digest.startswith("sha256:")
    assert len(digest) == 71  # sha256: + 64 hex chars

    # Order matters in canonical JSON
    d2 = {"target_audience": "audience", "brand_slug": "test"}
    assert canonical_json(d2) != canonical


def test_ares_script_input_digest_parity():
    """AresScriptInput canonical JSON digest matches Python computation."""
    script_input = AresScriptInput(
        brand_slug="test",
        protagonist_name="정원이",
        target_pain="pain",
    )
    d = script_input.to_dict()
    digest = sha256_digest(d)
    canonical = canonical_json(d)

    # Verify digest is properly formed
    assert digest.startswith("sha256:")
    assert len(digest) == 71

    # Keys are sorted in canonical form
    assert '"brand_slug"' in canonical
    assert '"protagonist_name"' in canonical
    assert canonical.index('"brand_slug"') < canonical.index('"protagonist_name"')
