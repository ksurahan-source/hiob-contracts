"""LockRegistry schema (BFA-2) — lock key · owner · force level.

Consumer (not co-committed): hiob-karma enforce of production locks
(see karma reconcile / set_run_attr lock keys). Karma BFA-3 stamps prompt
SHA; this schema is the typed lock vocabulary karma will enforce later.

U-G4 footnote: consumer dep-pair is karma enforce — not wired in this commit.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

ForceLevel = Literal["advisory", "soft", "hard"]


class LockEntry(BaseModel):
    """Single production lock row."""

    model_config = {"extra": "forbid"}

    lock_key: str = Field(min_length=1, description="Stable lock id e.g. environment_lock")
    owner: str = Field(min_length=1, description="Planet or service that owns the lock")
    force_level: ForceLevel = Field(default="advisory")
    value: Any = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LockRegistry(BaseModel):
    """Registry of locks for a run/workspace.

    Intended consumer: karma enforce (BFA-3 sibling — not co-committed).
    """

    model_config = {"extra": "forbid"}

    run_id: str = ""
    workspace_id: str = ""
    locks: list[LockEntry] = Field(default_factory=list)

    def get(self, lock_key: str) -> Optional[LockEntry]:
        for lock in self.locks:
            if lock.lock_key == lock_key:
                return lock
        return None

    def upsert(self, entry: LockEntry) -> "LockRegistry":
        """Return new registry with entry upserted (immutable)."""
        others = [l for l in self.locks if l.lock_key != entry.lock_key]
        return self.model_copy(update={"locks": others + [entry]})


def lock_registry_from_dict(data: dict[str, Any]) -> LockRegistry:
    return LockRegistry.model_validate(data)
