"""`DegradationReceipt` — the *only* way optional work may be skipped.

PRD_CREATIVE_FACTORY_HARMONY §6.7 and §9.1.

"No `null`, empty object, missing job, or warning log counts as approved
degradation." Optional music/SFX/editorial enhancement may be omitted only
through an explicit receipt that names what was dropped, the impact shown to the
user, who authorized it, and how to recover it. This turns silent fail-soft
fallbacks (the "throughput vs honesty" dilemma, §1.3) into auditable decisions.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from .digest import Digest, is_digest

_FROZEN = {"frozen": True, "extra": "forbid"}


class DegradationReceipt(BaseModel):
    """Explicit, auditable waiver for one omitted optional stage/artifact (§6.7)."""

    model_config = _FROZEN

    degradation_id: str
    run_id: str
    factory_revision: int = Field(ge=0)
    omitted_stage: str
    omitted_artifact_kind: str
    source_digests: tuple[Digest, ...] = ()
    plan_digest: Digest
    user_impact: str
    authorized_by: str  # human actor id or policy authority id
    policy_authority: str = ""
    expires_at: str | None = None
    recovery_action: str
    created_at: str

    @model_validator(mode="after")
    def _check(self) -> "DegradationReceipt":
        if not is_digest(self.plan_digest):
            raise ValueError(f"plan_digest malformed: {self.plan_digest!r}")
        for d in self.source_digests:
            if not is_digest(d):
                raise ValueError(f"degradation source digest malformed: {d!r}")
        if not self.user_impact.strip():
            raise ValueError("degradation must state the user-visible impact")
        if not self.recovery_action.strip():
            raise ValueError("degradation must state a recovery action")
        if not self.authorized_by.strip():
            raise ValueError("degradation must name an approver or policy authority")
        return self
