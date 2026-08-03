"""Star-owned read projection for one Reels factory state.

This is deliberately a view, not an authority or approval receipt.  Callers may
display it and echo ``review_digest`` into an approval command, but may not use
the projection itself as execution authority.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ares_script_revision_v1 import (
    AresApprovalReceiptV1,
    DigestStr,
    NonBlankStr,
    UuidStr,
    canonical_contract_digest_v1,
)
from .all_beat_video import BeatArtifactSetReceiptV1, ReelsFactoryReceiptV2
from .artemis_product_lock_v1 import ProductElementLockDraftV1
from .reels_factory_failure_v1 import (
    ReelsFactoryFailureReceiptV1,
    ReelsFactoryFailureReceiptV2,
)
from .reels_factory_progress_v1 import (
    ReelsFactoryProgressReceiptV1,
    ReelsFactoryProgressReceiptV2,
    ReelsFactoryProviderAttemptsV1,
)


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


class _StarReelsBudgetMultiBeatV1(BaseModel):
    """Structural all-beat budget fragment used before the V2 view is sealed."""

    model_config = _STRICT_FROZEN

    script: Literal[1]
    image: int = Field(ge=1, le=64)
    voice: int = Field(ge=1, le=64)
    render: Literal[1]
    retries: Literal[0]
    fallbacks: Literal[0]
    character_lock: Literal[0]


class _StarReelsBudgetV2(BaseModel):
    model_config = _STRICT_FROZEN

    script: Literal[1]
    image: int = Field(ge=1, le=16)
    video: int = Field(ge=1, le=16)
    voice: int = Field(ge=1, le=16)
    render: Literal[1]
    retries: Literal[0]
    fallbacks: Literal[0]
    character_lock: Literal[0]
    all_beat_count: int = Field(ge=1, le=16)
    paid_budget_authority_digest: DigestStr
    beat_artifact_set_receipt: BeatArtifactSetReceiptV1 | None

    @model_validator(mode="after")
    def _bind_all_paid_beat_lanes(self) -> "_StarReelsBudgetV2":
        if not (
            self.image
            == self.video
            == self.voice
            == self.all_beat_count
        ):
            raise ValueError("all-beat paid lanes must match all_beat_count")
        artifact_set = self.beat_artifact_set_receipt
        if artifact_set is not None and (
            artifact_set.expected_beat_count != self.all_beat_count
            or artifact_set.paid_budget_authority_digest
            != self.paid_budget_authority_digest
        ):
            raise ValueError("ready artifact count does not match paid budget")
        return self


class _AtroposRenderArtifactV1(BaseModel):
    model_config = _STRICT_FROZEN

    storage_key: NonBlankStr
    artifact_sha256: DigestStr
    mime: Literal["video/mp4"]
    bytes_len: int = Field(gt=0)


class _AtroposRenderReceiptV1(BaseModel):
    model_config = _STRICT_FROZEN

    contract_version: Literal["AtroposRenderReceipt.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    snapshot_digest: DigestStr
    output_url: NonBlankStr
    artifact: _AtroposRenderArtifactV1
    receipt_digest: DigestStr

    @field_validator("output_url")
    @classmethod
    def _require_https_output(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("output_url must be durable HTTPS")
        return value

    @model_validator(mode="after")
    def _bind_render_digest(self) -> "_AtroposRenderReceiptV1":
        body = self.model_dump(mode="json")
        observed = body.pop("receipt_digest")
        if observed != canonical_contract_digest_v1(body):
            raise ValueError("render receipt digest mismatch")
        return self


class _ZeroProviderReplaysV1(BaseModel):
    model_config = _STRICT_FROZEN

    script: Literal[0]
    image: Literal[0]
    voice: Literal[0]
    render: Literal[0]


class _ReelsFactoryReadyReceiptV1(BaseModel):
    model_config = _STRICT_FROZEN

    contract_version: Literal["ReelsFactoryReceipt.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: int = Field(ge=0)
    idempotency_key: NonBlankStr
    request_digest: DigestStr
    script_revision_digest: DigestStr
    beat_plan_revision_digest: DigestStr
    athena_receipt_digest: DigestStr
    voice_review: dict[str, Any]
    media_receipt_digests: list[DigestStr] = Field(min_length=1)
    audio_receipt_digests: list[DigestStr] = Field(min_length=1)
    sfx_receipt_digest: DigestStr
    snapshot: dict[str, Any]
    render_receipt: _AtroposRenderReceiptV1
    provider_attempts: ReelsFactoryProviderAttemptsV1
    provider_replays: _ZeroProviderReplaysV1
    fallback_calls: Literal[0]
    receipt_digest: DigestStr

    @model_validator(mode="after")
    def _bind_ready_success(self) -> "_ReelsFactoryReadyReceiptV1":
        if self.provider_attempts.model_dump() != {
            "script": 1,
            "image": 1,
            "voice": 1,
            "render": 1,
        }:
            raise ValueError("ready receipt requires exactly one attempt each")
        if (
            self.render_receipt.workspace_id != self.workspace_id
            or self.render_receipt.run_id != self.run_id
        ):
            raise ValueError("render receipt scope mismatch")
        body = self.model_dump(mode="json")
        observed = body.pop("receipt_digest")
        if observed != canonical_contract_digest_v1(body):
            raise ValueError("ready receipt digest mismatch")
        return self


class _StarReelsViewReceiptsV1(BaseModel):
    model_config = _STRICT_FROZEN

    factory: (
        ReelsFactoryProgressReceiptV1
        | ReelsFactoryFailureReceiptV1
        | _ReelsFactoryReadyReceiptV1
        | None
    )
    script_approval: AresApprovalReceiptV1 | None
    plan_approval: AresApprovalReceiptV1 | None


class _StarReelsViewReceiptsV2(BaseModel):
    model_config = _STRICT_FROZEN

    factory: (
        ReelsFactoryProgressReceiptV2
        | ReelsFactoryFailureReceiptV2
        | ReelsFactoryReceiptV2
        | None
    )
    script_approval: AresApprovalReceiptV1 | None
    plan_approval: AresApprovalReceiptV1 | None


def derive_star_product_lock_review_digest_v1(
    draft: ProductElementLockDraftV1,
) -> str:
    return canonical_contract_digest_v1(
        {
            "contract_version": "StarProductLockReviewDigest.v1",
            "workspace_id": draft.workspace_id,
            "run_id": draft.run_id,
            "compile_request_digest": draft.compile_request_digest,
            "draft_digest": draft.draft_digest,
        }
    )


class StarReelsViewV1(BaseModel):
    """Refresh-safe projection of every durable factory state."""

    model_config = _STRICT_FROZEN

    contract_version: Literal["StarReelsView.v1"]
    section: Literal["LockGate", "ScriptReview", "PlanReview", "RunStatus"]
    status: Literal[
        "missing",
        "awaiting_product_approval",
        "revoked",
        "digest_drift",
        "awaiting_script_approval",
        "awaiting_plan_approval",
        "pending",
        "rendering",
        "ready",
        "failed",
    ]
    revision: int = Field(ge=0)
    stage_output: ProductElementLockDraftV1 | dict[str, Any] | None
    budget: _StarReelsBudgetV1
    review_digest: DigestStr | None
    receipts: _StarReelsViewReceiptsV1
    provider_call: Literal["none", "confirmed", "unknown"]
    error: NonBlankStr | None

    @field_validator("stage_output", mode="before")
    @classmethod
    def _freeze_product_review(
        cls,
        value: Any,
    ) -> Any:
        if (
            isinstance(value, dict)
            and value.get("contract_version")
            == "ProductElementLockDraft.v1"
        ):
            return ProductElementLockDraftV1.model_validate(value)
        return value

    @model_validator(mode="after")
    def _bind_view_shape_to_state(self) -> "StarReelsViewV1":
        valid_pair = (
            self.section == "LockGate"
            and self.status
            in {
                "missing",
                "awaiting_product_approval",
                "revoked",
                "digest_drift",
                "ready",
            }
        ) or (
            self.section == "ScriptReview"
            and self.status == "awaiting_script_approval"
        ) or (
            self.section == "PlanReview"
            and self.status == "awaiting_plan_approval"
        ) or (
            self.section == "RunStatus"
            and self.status in {"pending", "rendering", "ready", "failed"}
        )
        if not valid_pair:
            raise ValueError("section does not match durable status")

        reviewing = self.section in {
            "ScriptReview",
            "PlanReview",
        }
        product_review = (
            self.section == "LockGate"
            and self.status == "awaiting_product_approval"
        )
        lock_gate = self.section == "LockGate"
        if reviewing or product_review:
            if self.stage_output is None or self.review_digest is None:
                raise ValueError(
                    "review state requires stage_output and review_digest"
                )
            if product_review:
                if not isinstance(
                    self.stage_output,
                    ProductElementLockDraftV1,
                ):
                    raise ValueError(
                        "product review requires typed product draft"
                    )
                if self.review_digest != (
                    derive_star_product_lock_review_digest_v1(
                        self.stage_output
                    )
                ):
                    raise ValueError(
                        "product review digest does not bind the draft"
                    )
                if self.provider_call != "none" or self.error is not None:
                    raise ValueError(
                        "product review cannot carry provider work or error"
                    )
            elif self.provider_call != "confirmed" or self.error is not None:
                raise ValueError(
                    "review state requires one confirmed script call"
                )
        elif self.stage_output is not None or self.review_digest is not None:
            raise ValueError(
                "non-review state cannot carry review-only fields"
            )

        if lock_gate:
            if self.provider_call != "none" or self.receipts.factory is not None:
                raise ValueError("LockGate cannot carry provider work")
            lock_has_no_error = self.status in {
                "ready",
                "awaiting_product_approval",
            }
            if lock_has_no_error != (self.error is None):
                raise ValueError("LockGate error does not match lock state")
        elif self.status == "failed":
            if (
                self.error is None
                or not isinstance(
                    self.receipts.factory,
                    (ReelsFactoryFailureReceiptV1, ReelsFactoryFailureReceiptV2),
                )
            ):
                raise ValueError(
                    "failed state requires error and failure receipt"
                )
        elif self.error is not None:
            raise ValueError("non-failed state cannot carry an error")

        if self.status in {"pending", "rendering"} and not isinstance(
            self.receipts.factory,
            (ReelsFactoryProgressReceiptV1, ReelsFactoryProgressReceiptV2),
        ):
            raise ValueError("active state requires progress receipt")
        if (
            self.section == "RunStatus"
            and self.status == "ready"
            and not isinstance(
                self.receipts.factory,
                (_ReelsFactoryReadyReceiptV1, ReelsFactoryReceiptV2),
            )
        ):
            raise ValueError("ready state requires final factory receipt")
        if (reviewing or product_review) and self.receipts.factory is not None:
            raise ValueError("review state cannot carry factory receipt")
        factory = self.receipts.factory
        if isinstance(
            factory,
            (ReelsFactoryFailureReceiptV1, ReelsFactoryFailureReceiptV2),
        ):
            expected_provider_call = factory.provider_call
        elif isinstance(
            factory,
            (ReelsFactoryProgressReceiptV1, ReelsFactoryProgressReceiptV2),
        ):
            expected_provider_call = (
                "confirmed"
                if sum(factory.provider_attempts.model_dump().values()) > 0
                else "none"
            )
        elif isinstance(
            factory,
            (_ReelsFactoryReadyReceiptV1, ReelsFactoryReceiptV2),
        ):
            expected_provider_call = "confirmed"
        else:
            expected_provider_call = None
        if (
            expected_provider_call is not None
            and self.provider_call != expected_provider_call
        ):
            raise ValueError(
                "provider_call does not match typed factory receipt"
            )
        return self


class StarReelsViewV2(StarReelsViewV1):
    """All-beat projection with explicit video cost and V2 receipts."""

    contract_version: Literal["StarReelsView.v2"]
    budget: _StarReelsBudgetV2
    receipts: _StarReelsViewReceiptsV2

    @model_validator(mode="after")
    def _bind_budget_to_ready_authority(self) -> "StarReelsViewV2":
        factory = self.receipts.factory
        if isinstance(factory, ReelsFactoryReceiptV2) and (
            self.budget.beat_artifact_set_receipt is None
            or factory.paid_budget_authority_digest
            != self.budget.paid_budget_authority_digest
            or factory.beat_artifact_set_receipt_digest
            != self.budget.beat_artifact_set_receipt.receipt_digest
        ):
            raise ValueError("sealed all-beat budget does not match ready receipt")
        return self


__all__ = [
    "StarReelsViewV1",
    "StarReelsViewV2",
    "_StarReelsBudgetMultiBeatV1",
    "derive_star_product_lock_review_digest_v1",
]
