"""Canonical factory state model + legal transitions.

PRD_CREATIVE_FACTORY_HARMONY §7. Today run/script/job/snapshot/render/Redis/Fable
states use conflicting vocabularies, so illegal combinations are representable and
common (§3.2 "State model"). This module defines the one factory lifecycle, the
supporting ledger vocabularies, and a transition guard so illegal moves fail closed.

Invariants encoded (§7.3): terminal runs never reopen; a run advances only along
the declared lifecycle or into an exception state; `BLOCKED` resumes to a stored
resume state.
"""
from __future__ import annotations

from enum import Enum


class FactoryState(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    WAITING_SCRIPT_APPROVAL = "WAITING_SCRIPT_APPROVAL"
    MEDIA_PLANNING = "MEDIA_PLANNING"
    WAITING_PLAN_APPROVAL = "WAITING_PLAN_APPROVAL"
    MATERIALIZING = "MATERIALIZING"
    MEDIA_READY = "MEDIA_READY"
    DRAFT_ASSEMBLY = "DRAFT_ASSEMBLY"
    EDITORIAL_REVIEW = "EDITORIAL_REVIEW"
    WAITING_FINAL_APPROVAL = "WAITING_FINAL_APPROVAL"
    FINAL_SNAPSHOT_LOCKED = "FINAL_SNAPSHOT_LOCKED"
    RENDER_QUEUED = "RENDER_QUEUED"
    RENDERING = "RENDERING"
    SUCCEEDED = "SUCCEEDED"
    # Exception states
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_STATES: frozenset[FactoryState] = frozenset(
    {FactoryState.SUCCEEDED, FactoryState.FAILED, FactoryState.CANCELLED}
)

# The declared linear lifecycle (§7.1). Every non-terminal state may also move to
# an exception state; approval-wait states may loop back to re-plan on rejection.
_LINEAR: tuple[FactoryState, ...] = (
    FactoryState.CREATED,
    FactoryState.PLANNING,
    FactoryState.WAITING_SCRIPT_APPROVAL,
    FactoryState.MEDIA_PLANNING,
    FactoryState.WAITING_PLAN_APPROVAL,
    FactoryState.MATERIALIZING,
    FactoryState.MEDIA_READY,
    FactoryState.DRAFT_ASSEMBLY,
    FactoryState.EDITORIAL_REVIEW,
    FactoryState.WAITING_FINAL_APPROVAL,
    FactoryState.FINAL_SNAPSHOT_LOCKED,
    FactoryState.RENDER_QUEUED,
    FactoryState.RENDERING,
    FactoryState.SUCCEEDED,
)

_NEXT: dict[FactoryState, FactoryState] = {
    _LINEAR[i]: _LINEAR[i + 1] for i in range(len(_LINEAR) - 1)
}

# Rejection at a gate loops back to the corresponding planning state (revise), never
# forward. Absence/rejection causes zero downstream paid work (FR-4/FR-5).
_REJECT_LOOP: dict[FactoryState, FactoryState] = {
    FactoryState.WAITING_SCRIPT_APPROVAL: FactoryState.PLANNING,
    FactoryState.WAITING_PLAN_APPROVAL: FactoryState.MEDIA_PLANNING,
    FactoryState.WAITING_FINAL_APPROVAL: FactoryState.EDITORIAL_REVIEW,
}

_EXCEPTIONS: frozenset[FactoryState] = frozenset(
    {FactoryState.BLOCKED, FactoryState.FAILED, FactoryState.CANCELLED}
)


def can_transition(src: FactoryState, dst: FactoryState) -> bool:
    """True iff `src → dst` is a legal factory transition.

    - terminal states never transition out (§7.3);
    - any non-terminal state may enter BLOCKED/FAILED/CANCELLED;
    - a non-terminal state may advance to its single linear successor;
    - an approval-wait state may loop back to its planning state on rejection;
    - BLOCKED may resume to any non-terminal, non-exception state (Star supplies
      the stored resume_state).
    """
    if src in TERMINAL_STATES:
        return False
    if dst in _EXCEPTIONS:
        return True
    if src == FactoryState.BLOCKED:
        return dst not in _EXCEPTIONS and dst not in TERMINAL_STATES
    if _NEXT.get(src) == dst:
        return True
    if _REJECT_LOOP.get(src) == dst:
        return True
    return False


def assert_transition(src: FactoryState, dst: FactoryState) -> None:
    """Raise `ValueError` on an illegal transition (fail closed)."""
    if not can_transition(src, dst):
        raise ValueError(f"illegal factory transition: {src.value} → {dst.value}")


class StageExecutionState(str, Enum):
    """`StageExecution` ledger vocabulary (§7.2)."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class EdgeExecutionState(str, Enum):
    """`EdgeExecution` ledger vocabulary (§7.2)."""

    PENDING = "pending"
    REFINING = "refining"
    ACCEPTED = "accepted"
    BLOCKED = "blocked"
    NEEDS_HUMAN = "needs_human"
    FAILED = "failed"
    SUPERSEDED = "superseded"
