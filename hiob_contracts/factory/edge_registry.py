"""The mandatory semantic-edge registry — one row per directed Planet→Planet edge.

PRD_CREATIVE_FACTORY_HARMONY FR-2 and §5 (target factory flow). This is both the
Phase 0 "edge graph" artifact and the Phase 1 machine-readable authority that CI
checks: "CI rejects an unregistered direct edge" and "the runtime manifest and
live `.well-known` surfaces must match the registry."

Every row records the source output contract, the target input contract, the
Karma policy, the timeout, and the criticality. Binary uploads, control polling,
health probes, and human-approval commands are NOT semantic edges and are absent
here by design (§4.2).

Exact schema digests are resolved from each Planet's manifest at runtime; this
static registry binds *which* edges exist, *who* consumes, and *under which
policy* — the topology CI enforces.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Criticality = Literal["required", "optional"]


@dataclass(frozen=True)
class SemanticEdge:
    """One directed, Karma-mediated handoff between two Planets."""

    edge_id: str
    source_planet: str
    source_contract: str
    target_planet: str
    target_node_id: str
    target_contract: str
    policy_id: str
    timeout_ms: int
    criticality: Criticality
    note: str = ""


# ── The factory edge graph (§5). Order follows the flow. ─────────────────────
EDGES: tuple[SemanticEdge, ...] = (
    # Planning slice (Phase 2): Janus → Parzifal → Ares.
    SemanticEdge(
        "j2p", "janus", "JanusBrief", "parzifal", "parzifal.target.consolidate",
        "ParzifalTargetInput", "policy.j2p", 30_000, "required",
        "Janus evidence brief refined for Parzifal target/identity derivation",
    ),
    SemanticEdge(
        "p2a", "parzifal", "TargetProfile+IdentityLock+CastSheet", "ares", "ares.script.build",
        "AresScriptInput", "policy.p2a", 30_000, "required",
        "Parzifal identity/target refined for Ares; Ares cannot run without this receipt (FR-3)",
    ),
    # Media plan slice (Phase 3): Ares → {Athena, Orpheus, Apollo} plans.
    SemanticEdge(
        "a2athena", "ares", "ScriptPackage+BeatPlan", "athena", "athena.plan",
        "AthenaPlanInput", "policy.a2media", 30_000, "required",
        "Ares beats refined for Athena visual planning",
    ),
    SemanticEdge(
        "a2orpheus", "ares", "ScriptPackage+BeatPlan", "orpheus", "orpheus.plan",
        "OrpheusPlanInput", "policy.a2media", 30_000, "required",
        "Ares beats refined for Orpheus voice/music planning (voice required)",
    ),
    SemanticEdge(
        "a2apollo", "ares", "ScriptPackage+BeatPlan", "apollo", "apollo.plan",
        "ApolloPlanInput", "policy.a2media", 30_000, "optional",
        "Ares beats refined for Apollo SFX planning (optional enhancement, §9.1)",
    ),
    # Fan-in (Phase 3/4): materialized media bundle → Atropos draft.
    SemanticEdge(
        "media2atropos", "athena+orpheus+apollo",
        "VisualArtifactSet+VoiceMusicArtifactSet+SfxArtifactSet",
        "atropos", "atropos.draft", "AtroposDraftInput", "policy.media2atropos",
        45_000, "required",
        "Required-media fan-in refined into an Atropos draft snapshot input",
    ),
    # Editorial loop (Phase 4) — SUNSET 2026-07-21.
    # Artemis identity is product/evidence seal only (artemis.references.snapshot).
    # Edges kept for contract validation / historical receipts; criticality optional
    # so they never block F1. Hard-delete after consumer cleanup (see hiob-artemis/docs/SUNSET.md S7).
    SemanticEdge(
        "atropos2artemis", "atropos", "CompositionSnapshot", "artemis", "artemis.review",
        "ArtemisReviewInput", "policy.atropos2artemis", 45_000, "optional",
        "SUNSET: not on F1 spine; Artemis = product/evidence seal only (was editorial QA)",
    ),
    SemanticEdge(
        "artemis2atropos", "artemis", "EditorialProposal", "atropos", "atropos.apply",
        "AtroposApplyInput", "policy.artemis2atropos", 30_000, "optional",
        "SUNSET: human-accepted editorial proposals (optional; not live produce path)",
    ),
    # Final render (Phase 5): carries the G3 ApprovalReceipt reference, not a boolean.
    SemanticEdge(
        "atropos2hephaestus", "atropos", "CompositionSnapshot", "hephaestus", "hephaestus.render",
        "HephaestusRenderInput", "policy.atropos2hephaestus", 60_000, "required",
        "Final snapshot + G3 approval reference refined for render authorization (FR-8)",
    ),
)

_BY_ID: dict[str, SemanticEdge] = {e.edge_id: e for e in EDGES}


def get_edge(edge_id: str) -> SemanticEdge | None:
    """Look up a registered edge by id, or None."""
    return _BY_ID.get(edge_id)


def is_registered_edge(source_planet: str, target_planet: str) -> bool:
    """True iff a semantic edge from `source_planet` to `target_planet` is registered.

    CI uses this to reject any direct Planet→Planet consumption that is not a
    declared, Karma-mediated edge (FR-2). Fan-in sources are recorded as a joined
    `a+b+c` source_planet token; membership is checked per component.
    """
    for e in EDGES:
        sources = e.source_planet.split("+")
        if target_planet == e.target_planet and source_planet in sources:
            return True
    return False


def required_edges() -> tuple[SemanticEdge, ...]:
    """Edges whose failure must block the run (fan-in cannot advance without them)."""
    return tuple(e for e in EDGES if e.criticality == "required")
