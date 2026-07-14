"""`ApprovalReceipt` — a human decision bound to exact content by digest.

PRD_CREATIVE_FACTORY_HARMONY §6.6.

Today editor approval is a mutable timestamp and Atropos sends
`approvedFinalRender: true` (PRD §3.2 "Human approval"). This contract replaces
self-asserted booleans with a receipt bound to a specific `target_digest`. Any
upstream change creates a new `factory_revision`; old receipts remain auditable
but no longer match the new digest, so they cannot authorize the changed content.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .digest import Digest, assert_digest

_FROZEN = {"frozen": True, "extra": "forbid"}

ApprovalKind = Literal["script", "production_plan", "composition_snapshot", "waiver"]
ApprovalDecision = Literal["approved", "rejected"]


class ApprovalReceipt(BaseModel):
    """Immutable human decision bound to `target_digest` (§6.6).

    Star mints this from an authenticated human command. It is the only thing that
    authorizes a gate to open — G1 (script+identity), G2 (plan), G3 (final snapshot).
    Hephaestus independently resolves the G3 receipt and re-verifies it (FR-8).
    """

    model_config = _FROZEN

    approval_id: str
    kind: ApprovalKind
    run_id: str
    factory_revision: int = Field(ge=0)
    target_id: str
    target_digest: Digest
    decision: ApprovalDecision
    approved_by: str
    approved_at: str
    policy_version: str
    expires_at: str | None = None
    revoked_at: str | None = None

    @model_validator(mode="after")
    def _check(self) -> "ApprovalReceipt":
        assert_digest(self.target_digest, "approval.target_digest")
        return self

    def authorizes(self, target_digest: Digest, *, now: str | None = None) -> bool:
        """True iff this receipt approves exactly `target_digest` and is still valid.

        Rejects boolean-only, stale (revision mismatch handled by caller), revoked,
        expired, and mismatched-digest approvals — the checks FR-8 requires of
        Hephaestus. `now` is an ISO-8601 string compared lexicographically (ISO-8601
        UTC sorts chronologically), passed by the caller (no wall-clock in contracts).
        """
        if self.decision != "approved":
            return False
        if self.revoked_at is not None:
            return False
        if self.target_digest != target_digest:
            return False
        if self.expires_at is not None and now is not None and now >= self.expires_at:
            return False
        return True
