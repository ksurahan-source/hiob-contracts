"""Creative Factory Harmony contract kernel (PRD_CREATIVE_FACTORY_HARMONY §6–§7).

The typed, digest-linked, receipt-bearing envelopes that make every semantic
Planet-to-Planet handoff enforceable:

- `PlanetOutput` / `ArtifactRef` — immutable Planet outputs and binary references.
- `PlanetOutputBuilder` — helper to construct PlanetOutput envelopes with digests.
- `KarmaRefineRequest` / `KarmaEdgeReceipt` — the mandatory edge refinery.
- `StageReceipt` — terminal stage truth (spawn handle ≠ success).
- `StageReceiptBuilder` — helper to construct StageReceipt envelopes (succeeded/failed/blocked).
- `ApprovalReceipt` — human decisions bound to content digests.
- `DegradationReceipt` — the only sanctioned way to skip optional work.
- `FactoryState` + transition guard — the one factory lifecycle vocabulary.
- edge registry — the machine-readable edge graph CI enforces.
- `canonical_json` / `sha256_digest` — the one hashing serialization.

Builders (PlanetOutputBuilder, StageReceiptBuilder) are provided for Planet
node servers to construct compliant envelopes with automatic digest computation.

Additive foundation (Phase 1): nothing consumes these at runtime yet. Grade is
L1 (built) → L2 (property-tested), NOT L4. Wiring Planets to them is Phases 2–6.
"""
from __future__ import annotations

from .approval import ApprovalDecision, ApprovalKind, ApprovalReceipt
from .degradation import DegradationReceipt
from .digest import (
    DIGEST_RE,
    Digest,
    DigestError,
    assert_digest,
    canonical_json,
    is_digest,
    sha256_digest,
)
from .edge_registry import (
    EDGES,
    Criticality,
    SemanticEdge,
    get_edge,
    is_registered_edge,
    required_edges,
)
from .karma_edge import (
    EdgeDecision,
    EdgeViolation,
    KarmaEdgeReceipt,
    KarmaRefineRequest,
    MapperRef,
    PolicyRef,
    TargetRef,
    TransformLogEntry,
    TransformOp,
    TransformOrigin,
    ViolationSeverity,
    derive_idempotency_key,
)
from .planet_output import ArtifactRef, ContractRef, PlanetOutput
from .planet_output_builder import PlanetOutputBuilder
from .stage_receipt import (
    TERMINAL_STAGE_STATUSES,
    StageError,
    StageReceipt,
    StageStatus,
)
from .stage_receipt_builder import StageReceiptBuilder
from .state import (
    TERMINAL_STATES,
    EdgeExecutionState,
    FactoryState,
    StageExecutionState,
    assert_transition,
    can_transition,
)

__all__ = [
    # digest
    "Digest", "DigestError", "DIGEST_RE", "canonical_json", "sha256_digest",
    "is_digest", "assert_digest",
    # planet output
    "PlanetOutput", "ArtifactRef", "ContractRef", "PlanetOutputBuilder",
    # karma edge
    "KarmaRefineRequest", "KarmaEdgeReceipt", "TargetRef", "PolicyRef",
    "TransformLogEntry", "EdgeViolation", "MapperRef", "derive_idempotency_key",
    "EdgeDecision", "TransformOp", "TransformOrigin", "ViolationSeverity",
    # stage receipt
    "StageReceipt", "StageError", "StageStatus", "TERMINAL_STAGE_STATUSES", "StageReceiptBuilder",
    # approval / degradation
    "ApprovalReceipt", "ApprovalKind", "ApprovalDecision", "DegradationReceipt",
    # state
    "FactoryState", "TERMINAL_STATES", "can_transition", "assert_transition",
    "StageExecutionState", "EdgeExecutionState",
    # edge registry
    "SemanticEdge", "EDGES", "Criticality", "get_edge", "is_registered_edge",
    "required_edges",
]

from .lock_registry import LockEntry, LockRegistry, lock_registry_from_dict  # BFA-2

