"""`StageReceipt` — Star's terminal record of one Planet stage execution.

PRD_CREATIVE_FACTORY_HARMONY §6.5.

The single most abused truth in the current factory is that a `202 accepted`, a
Modal call ID, or a queue handle gets mistaken for success (PRD §3.2 "Async
truth"). This contract makes that impossible: `accepted` and `running` are
**non-terminal**, and `succeeded` is only representable with a completion time
and at least one output digest.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .digest import Digest, is_digest

_FROZEN = {"frozen": True, "extra": "forbid"}

StageStatus = Literal[
    "accepted", "running", "succeeded", "failed", "cancelled", "superseded"
]

# `accepted`/`running` are explicitly NOT terminal — a spawn handle is not success.
TERMINAL_STAGE_STATUSES: frozenset[str] = frozenset(
    {"succeeded", "failed", "cancelled", "superseded"}
)


class StageError(BaseModel):
    """Structured stage failure — `retryable` drives Star's retry policy (§9.3)."""

    model_config = _FROZEN

    code: str
    retryable: bool
    details: str = ""


class StageReceipt(BaseModel):
    """Terminal (or in-flight) record of a Planet stage under one operation id (§6.5)."""

    model_config = _FROZEN

    operation_id: str
    stage_id: str
    planet: str
    node_id: str
    producer_revision: str
    image_digest: Digest | None = None
    contract_version: str
    input_digests: tuple[Digest, ...] = ()
    output_digests: tuple[Digest, ...] = ()
    status: StageStatus
    attempt_no: int = Field(ge=1)
    started_at: str
    completed_at: str | None = None
    cost: dict | None = None
    warnings: tuple[str, ...] = ()
    error: StageError | None = None

    @model_validator(mode="after")
    def _check(self) -> "StageReceipt":
        for d in (*self.input_digests, *self.output_digests):
            if not is_digest(d):
                raise ValueError(f"stage receipt digest malformed: {d!r}")

        is_terminal = self.status in TERMINAL_STAGE_STATUSES
        if is_terminal and self.completed_at is None:
            raise ValueError(f"terminal status {self.status!r} requires completed_at")
        if not is_terminal and self.completed_at is not None:
            raise ValueError(f"non-terminal status {self.status!r} must not set completed_at")

        if self.status == "succeeded":
            if not self.output_digests:
                raise ValueError("succeeded stage must produce at least one output digest")
            if self.error is not None:
                raise ValueError("succeeded stage cannot carry an error")
        if self.status == "failed" and self.error is None:
            raise ValueError("failed stage must carry a structured error")
        return self

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STAGE_STATUSES

    @property
    def is_success(self) -> bool:
        return self.status == "succeeded"
