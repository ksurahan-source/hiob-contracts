"""Star-owned read projection for one Reels factory state.

This is deliberately a view, not an authority or approval receipt.  Callers may
display it and echo ``review_digest`` into an approval command, but may not use
the projection itself as execution authority.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ares_script_revision_v1 import DigestStr, NonBlankStr


_STRICT_FROZEN = ConfigDict(
    extra="forbid",
    frozen=True,
    strict=True,
    revalidate_instances="always",
)


class _StarReelsBudgetV1(BaseModel):
    model_config = _STRICT_FROZEN

    script: Literal[1]
    image: Literal[1]
    voice: Literal[1]
    render: Literal[1]
    retries: Literal[0]
    fallbacks: Literal[0]
    character_lock: Literal[0]


class StarReelsViewV1(BaseModel):
    """Refresh-safe projection of every durable factory state."""

    model_config = _STRICT_FROZEN

    contract_version: Literal["StarReelsView.v1"]
    section: Literal["ScriptReview", "PlanReview", "RunStatus"]
    status: Literal[
        "new",
        "awaiting_script_approval",
        "awaiting_plan_approval",
        "pending",
        "rendering",
        "ready",
        "failed",
    ]
    revision: int = Field(ge=0)
    stage_output: dict[str, Any] | None
    budget: _StarReelsBudgetV1
    review_digest: DigestStr | None
    receipts: dict[str, dict[str, Any]]
    provider_call: Literal["none", "confirmed", "unknown"]
    error: NonBlankStr | None

    @model_validator(mode="after")
    def _bind_view_shape_to_state(self) -> "StarReelsViewV1":
        expected_section = {
            "awaiting_script_approval": "ScriptReview",
            "awaiting_plan_approval": "PlanReview",
        }.get(self.status, "RunStatus")
        if self.section != expected_section:
            raise ValueError("section does not match durable status")

        reviewing = self.status in {
            "awaiting_script_approval",
            "awaiting_plan_approval",
        }
        if reviewing:
            if self.stage_output is None or self.review_digest is None:
                raise ValueError(
                    "review state requires stage_output and review_digest"
                )
            if self.provider_call != "none" or self.error is not None:
                raise ValueError("review state cannot carry a terminal error")
        elif self.stage_output is not None or self.review_digest is not None:
            raise ValueError(
                "non-review state cannot carry review-only fields"
            )

        if self.status == "failed":
            if self.error is None or "factory" not in self.receipts:
                raise ValueError(
                    "failed state requires error and factory receipt"
                )
        elif self.error is not None:
            raise ValueError("non-failed state cannot carry an error")

        if (
            self.status in {"pending", "rendering", "ready"}
            and "factory" not in self.receipts
        ):
            raise ValueError("active/final state requires factory receipt")
        return self


__all__ = ["StarReelsViewV1"]
