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
    AresBeatPlanRevisionV1,
    AresScriptRevisionV1,
    DigestStr,
    NonBlankStr,
    NonNegativeInt,
    UtcTimestamp,
    UuidStr,
    _parse_utc,
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
from .storyboard_two_stage_v1 import (
    FactoryPaidBudgetApprovalReceiptV2,
    FactoryPaidBudgetAuthorityV2,
    FactoryPaidBudgetPurposeV2,
    ReelsFactoryCompletionSummaryV3,
    ReelsFactoryFailureReceiptV3,
    ReelsFactoryProgressReceiptV3,
    StoryboardDraftV1,
    StoryboardImageSetReceiptV1,
    StoryboardSceneVideoSetSummaryV1,
    factory_paid_call_cardinality_v2,
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
    image: int = Field(ge=1, le=16)
    voice: int = Field(ge=1, le=16)
    render: Literal[1]
    retries: Literal[0]
    fallbacks: Literal[0]
    character_lock: Literal[0]

    @model_validator(mode="after")
    def _bind_per_beat_lanes(self) -> "_StarReelsBudgetMultiBeatV1":
        if self.image != self.voice:
            raise ValueError(
                "all-beat paid lanes must have equal image and voice counts"
            )
        return self


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
        if not (self.image == self.video == self.voice == self.all_beat_count):
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


class _StarReelsViewReceiptsV3(BaseModel):
    model_config = _STRICT_FROZEN

    factory: (
        ReelsFactoryProgressReceiptV3
        | ReelsFactoryFailureReceiptV3
        | ReelsFactoryCompletionSummaryV3
        | None
    )
    script_approval: AresApprovalReceiptV1 | None
    plan_approval: AresApprovalReceiptV1 | None
    paid_budget_approval_receipt: FactoryPaidBudgetApprovalReceiptV2 | None
    paid_budget_authority: FactoryPaidBudgetAuthorityV2 | None
    storyboard_phase_a_completion_summary: StoryboardPhaseACompletionSummaryV1 | None


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
            and value.get("contract_version") == "ProductElementLockDraft.v1"
        ):
            return ProductElementLockDraftV1.model_validate(value)
        return value

    @model_validator(mode="after")
    def _bind_view_shape_to_state(self) -> "StarReelsViewV1":
        valid_pair = (
            (
                self.section == "LockGate"
                and self.status
                in {
                    "missing",
                    "awaiting_product_approval",
                    "revoked",
                    "digest_drift",
                    "ready",
                }
            )
            or (
                self.section == "ScriptReview"
                and self.status == "awaiting_script_approval"
            )
            or (
                self.section == "PlanReview" and self.status == "awaiting_plan_approval"
            )
            or (
                self.section == "RunStatus"
                and self.status in {"pending", "rendering", "ready", "failed"}
            )
        )
        if not valid_pair:
            raise ValueError("section does not match durable status")

        reviewing = self.section in {
            "ScriptReview",
            "PlanReview",
        }
        product_review = (
            self.section == "LockGate" and self.status == "awaiting_product_approval"
        )
        lock_gate = self.section == "LockGate"
        if reviewing or product_review:
            if self.stage_output is None or self.review_digest is None:
                raise ValueError("review state requires stage_output and review_digest")
            if product_review:
                if not isinstance(
                    self.stage_output,
                    ProductElementLockDraftV1,
                ):
                    raise ValueError("product review requires typed product draft")
                if self.review_digest != (
                    derive_star_product_lock_review_digest_v1(self.stage_output)
                ):
                    raise ValueError("product review digest does not bind the draft")
                if self.provider_call != "none" or self.error is not None:
                    raise ValueError(
                        "product review cannot carry provider work or error"
                    )
            elif self.provider_call != "confirmed" or self.error is not None:
                raise ValueError("review state requires one confirmed script call")
        elif self.stage_output is not None or self.review_digest is not None:
            raise ValueError("non-review state cannot carry review-only fields")

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
            if self.error is None or not isinstance(
                self.receipts.factory,
                (ReelsFactoryFailureReceiptV1, ReelsFactoryFailureReceiptV2),
            ):
                raise ValueError("failed state requires error and failure receipt")
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
            raise ValueError("provider_call does not match typed factory receipt")
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


class FactoryStoryboardCarrierV1(BaseModel):
    """Digest-only storyboard pointer safe for a Star read projection."""

    model_config = _STRICT_FROZEN

    contract_version: Literal["FactoryStoryboardCarrier.v1"]
    storyboard_revision: int = Field(ge=1)
    storyboard_digest: DigestStr
    image_set_receipt_digest: DigestStr
    approval_receipt_digest: DigestStr | None
    execution_manifest_digest: DigestStr | None

    @model_validator(mode="after")
    def _require_approval_before_execution(self) -> "FactoryStoryboardCarrierV1":
        if (
            self.execution_manifest_digest is not None
            and self.approval_receipt_digest is None
        ):
            raise ValueError("execution manifest requires approval receipt")
        return self


def derive_factory_storyboard_carrier_digest_v1(
    value: FactoryStoryboardCarrierV1 | dict[str, Any],
) -> str:
    payload = (
        value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    )
    return canonical_contract_digest_v1(
        {
            "purpose": "factory-storyboard-carrier.v1",
            "carrier": payload,
        }
    )


def derive_storyboard_phase_a_completion_receipt_digest_v1(
    value: BaseModel | dict[str, Any],
) -> str:
    return canonical_contract_digest_v1(value, exclude={"receipt_digest"})


def derive_storyboard_phase_a_completion_summary_digest_v1(
    value: BaseModel | dict[str, Any],
) -> str:
    return canonical_contract_digest_v1(value, exclude={"summary_digest"})


class StoryboardPhaseACompletionReceiptV1(BaseModel):
    """Server-only proof of the complete paid still phase and draft output."""

    model_config = _STRICT_FROZEN

    contract_version: Literal["StoryboardPhaseACompletionReceipt.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    purpose: Literal["storyboard_draft", "storyboard_regen"]
    plan_digest: DigestStr
    ares_script_revision_digest: DigestStr
    ares_beat_plan_revision_digest: DigestStr
    ares_script_revision: AresScriptRevisionV1
    ares_beat_plan_revision: AresBeatPlanRevisionV1
    paid_budget_approval_receipt: FactoryPaidBudgetApprovalReceiptV2
    paid_budget_authority: FactoryPaidBudgetAuthorityV2
    paid_budget_authority_digest: DigestStr
    paid_source_beat_indices: tuple[int, ...] = Field(min_length=1, max_length=16)
    input_storyboard_draft: StoryboardDraftV1 | None
    input_image_set_receipt: StoryboardImageSetReceiptV1 | None
    paid_image_provider_receipt_digests: tuple[DigestStr, ...] = Field(
        min_length=1,
        max_length=16,
    )
    output_image_set_receipt: StoryboardImageSetReceiptV1
    output_storyboard_draft: StoryboardDraftV1
    output_storyboard_carrier: FactoryStoryboardCarrierV1
    completed_at_utc: UtcTimestamp
    receipt_digest: DigestStr

    @field_validator(
        "paid_source_beat_indices",
        "paid_image_provider_receipt_digests",
        mode="before",
    )
    @classmethod
    def _tuple_fields(cls, value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def _bind_completion(self) -> "StoryboardPhaseACompletionReceiptV1":
        approval = self.paid_budget_approval_receipt
        authority = self.paid_budget_authority
        image_set = self.output_image_set_receipt
        draft = self.output_storyboard_draft
        script_revision = self.ares_script_revision
        plan_revision = self.ares_beat_plan_revision
        if (
            not approval.structurally_binds(authority)
            or authority.purpose != self.purpose
            or authority.workspace_id != self.workspace_id
            or authority.run_id != self.run_id
            or authority.factory_revision != self.factory_revision
            or authority.authority_digest != self.paid_budget_authority_digest
            or tuple(authority.image_source_beat_indices)
            != self.paid_source_beat_indices
            or self.ares_beat_plan_revision_digest != self.plan_digest
            or script_revision.revision_digest != self.ares_script_revision_digest
            or plan_revision.revision_digest != self.plan_digest
            or not plan_revision.binds_script_revision(script_revision)
            or script_revision.workspace_id != self.workspace_id
            or script_revision.run_id != self.run_id
            or script_revision.factory_revision != self.factory_revision
            or len(plan_revision.beat_plan.beats) != 16
        ):
            raise ValueError("Phase-A paid authority does not bind completion scope")
        if self.purpose == "storyboard_draft":
            if (
                authority.plan_digest is not None
                or self.input_storyboard_draft is not None
                or self.input_image_set_receipt is not None
                or self.paid_source_beat_indices != tuple(range(16))
                or draft.revision != 1
                or draft.parent_draft_digest is not None
            ):
                raise ValueError("storyboard_draft completion requires initial output")
        else:
            previous = self.input_storyboard_draft
            previous_image_set = self.input_image_set_receipt
            if (
                previous is None
                or previous_image_set is None
                or not previous.binds_image_set(previous_image_set)
                or authority.plan_digest != self.plan_digest
                or authority.storyboard_draft_digest != previous.draft_digest
                or not draft.is_valid_successor_of(
                    previous,
                    replacement_image_set=image_set,
                )
            ):
                raise ValueError("storyboard_regen input does not bind valid successor")
            previous_by_source = {
                card.source_beat_index: card for card in previous.cards
            }
            current_by_source = {card.source_beat_index: card for card in draft.cards}
            paid_sources = set(self.paid_source_beat_indices)
            for source in range(16):
                before = previous_by_source[source]
                after = current_by_source[source]
                before_data = before.model_dump(mode="json")
                after_data = after.model_dump(mode="json")
                for mutable_digest_field in ("card_digest",):
                    before_data.pop(mutable_digest_field)
                    after_data.pop(mutable_digest_field)
                if source in paid_sources:
                    before_data.pop("selected_artifact")
                    after_data.pop("selected_artifact")
                if before_data != after_data or (
                    source not in paid_sources
                    and before.selected_artifact != after.selected_artifact
                ):
                    raise ValueError("regen changed an unpaid storyboard card")
        if (
            image_set.workspace_id != self.workspace_id
            or image_set.run_id != self.run_id
            or image_set.factory_revision != self.factory_revision
            or image_set.plan_digest != self.plan_digest
            or image_set.paid_budget_authority_digest != authority.authority_digest
            or image_set.paid_source_beat_indices != self.paid_source_beat_indices
            or not draft.binds_image_set(image_set)
        ):
            raise ValueError("Phase-A output image set does not bind output draft")
        requests = [receipt.request for receipt in image_set.provider_receipts]
        if any(
            request.ares_script_revision_digest != self.ares_script_revision_digest
            or request.ares_beat_plan_revision_digest != self.plan_digest
            for request in requests
        ):
            raise ValueError("Phase-A image request revision evidence drifted")
        card_by_source = {card.source_beat_index: card for card in draft.cards}
        for source_index, beat in enumerate(plan_revision.beat_plan.beats):
            card = card_by_source[source_index]
            if (
                card.voice_text != beat.text
                or card.caption_text != beat.caption
                or card.voice_text
                != script_revision.script_package.voice_script[source_index].text
                or card.caption_text
                != script_revision.script_package.caption_script[source_index].text
            ):
                raise ValueError("storyboard card text does not match Ares revisions")
        paid_receipts = [
            image_set.provider_receipts[index]
            for index in self.paid_source_beat_indices
        ]
        if tuple(
            receipt.receipt_digest for receipt in paid_receipts
        ) != self.paid_image_provider_receipt_digests or any(
            receipt.request.paid_budget_authority_digest != authority.authority_digest
            or receipt.request.purpose != self.purpose
            for receipt in paid_receipts
        ):
            raise ValueError("paid source receipts do not match Phase-A authority")
        expected_carrier = FactoryStoryboardCarrierV1(
            contract_version="FactoryStoryboardCarrier.v1",
            storyboard_revision=draft.revision,
            storyboard_digest=draft.draft_digest,
            image_set_receipt_digest=image_set.receipt_digest,
            approval_receipt_digest=None,
            execution_manifest_digest=None,
        )
        if self.output_storyboard_carrier != expected_carrier:
            raise ValueError(
                "output storyboard carrier does not bind output storyboard"
            )
        if self.purpose == "storyboard_draft" and any(
            request.paid_budget_authority_digest != authority.authority_digest
            for request in requests
        ):
            raise ValueError("initial completion contains an alien image authority")
        if self.purpose == "storyboard_regen":
            previous = self.input_storyboard_draft
            previous_image_set = self.input_image_set_receipt
            assert previous is not None
            assert previous_image_set is not None
            if image_set.previous_image_set_receipt_digest != (
                previous_image_set.receipt_digest
            ):
                raise ValueError("regen image set does not bind prior sealed image set")
            images_by_source = {
                image.source_beat_index: image for image in image_set.images
            }
            previous_by_source = {
                card.source_beat_index: card for card in previous.cards
            }
            prior_receipts = {
                receipt.request.source_beat_index: receipt
                for receipt in previous_image_set.provider_receipts
            }
            output_receipts = {
                receipt.request.source_beat_index: receipt
                for receipt in image_set.provider_receipts
            }
            for source in set(range(16)) - set(self.paid_source_beat_indices):
                image = images_by_source[source]
                if (
                    previous_by_source[source].selected_artifact.artifact_id
                    != image.artifact_id
                    or previous_by_source[source].selected_artifact.artifact_digest
                    != image.artifact_digest
                    or output_receipts[source] != prior_receipts[source]
                ):
                    raise ValueError("regen replaced an unpaid image artifact")
        if _parse_utc(self.completed_at_utc) < _parse_utc(image_set.completed_at_utc):
            raise ValueError("completed_at_utc precedes output image set completion")
        if self.receipt_digest != (
            derive_storyboard_phase_a_completion_receipt_digest_v1(self)
        ):
            raise ValueError("receipt_digest does not match Phase-A completion")
        return self

    def binds_paid_operations(
        self,
        authority: object,
        operation_proofs: tuple[object, ...],
    ) -> bool:
        return self.output_image_set_receipt.binds_paid_operations(
            authority,
            operation_proofs,
            previous_image_set=self.input_image_set_receipt,
        )


class StoryboardPhaseACompletionSummaryV1(BaseModel):
    """Browser-safe digest projection of the server-only Phase-A proof."""

    model_config = _STRICT_FROZEN

    contract_version: Literal["StoryboardPhaseACompletionSummary.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: NonNegativeInt
    purpose: Literal["storyboard_draft", "storyboard_regen"]
    plan_digest: DigestStr
    paid_budget_authority_digest: DigestStr
    max_total_cost_microunits: int = Field(gt=0)
    currency: Literal["USD"]
    output_storyboard_revision: int = Field(ge=1)
    output_storyboard_digest: DigestStr
    output_image_set_receipt_digest: DigestStr
    output_storyboard_carrier_digest: DigestStr
    image_count: Literal[16]
    completed_at_utc: UtcTimestamp
    completion_receipt_digest: DigestStr
    summary_digest: DigestStr

    @model_validator(mode="after")
    def _bind_summary_digest(self) -> "StoryboardPhaseACompletionSummaryV1":
        if self.summary_digest != (
            derive_storyboard_phase_a_completion_summary_digest_v1(self)
        ):
            raise ValueError("summary_digest does not match Phase-A summary")
        return self

    @classmethod
    def from_completion(
        cls,
        completion: StoryboardPhaseACompletionReceiptV1,
        *,
        authority: object,
        operation_proofs: tuple[object, ...],
    ) -> "StoryboardPhaseACompletionSummaryV1":
        if not completion.binds_paid_operations(authority, operation_proofs):
            raise ValueError(
                "Phase-A summary requires verified live or historical operation proof"
            )
        body: dict[str, Any] = {
            "contract_version": "StoryboardPhaseACompletionSummary.v1",
            "workspace_id": completion.workspace_id,
            "run_id": completion.run_id,
            "factory_revision": completion.factory_revision,
            "purpose": completion.purpose,
            "plan_digest": completion.plan_digest,
            "paid_budget_authority_digest": (completion.paid_budget_authority_digest),
            "max_total_cost_microunits": (
                completion.paid_budget_authority.max_total_cost_microunits
            ),
            "currency": completion.paid_budget_authority.currency,
            "output_storyboard_revision": (completion.output_storyboard_draft.revision),
            "output_storyboard_digest": (
                completion.output_storyboard_draft.draft_digest
            ),
            "output_image_set_receipt_digest": (
                completion.output_image_set_receipt.receipt_digest
            ),
            "output_storyboard_carrier_digest": (
                derive_factory_storyboard_carrier_digest_v1(
                    completion.output_storyboard_carrier
                )
            ),
            "image_count": 16,
            "completed_at_utc": completion.completed_at_utc,
            "completion_receipt_digest": completion.receipt_digest,
        }
        body["summary_digest"] = derive_storyboard_phase_a_completion_summary_digest_v1(
            body
        )
        return cls.model_validate(body)

    def binds(
        self,
        completion: StoryboardPhaseACompletionReceiptV1,
        *,
        authority: object,
        operation_proofs: tuple[object, ...],
    ) -> bool:
        return self == self.from_completion(
            completion,
            authority=authority,
            operation_proofs=operation_proofs,
        )


_StarReelsViewReceiptsV3.model_rebuild()


_STAR_REELS_PURPOSE_LABELS_V3 = {
    "storyboard_draft": "스토리보드 이미지 16장",
    "storyboard_regen": "선택 이미지 재생성",
    "final_production": "최종 영상 제작",
}


class StarReelsBudgetV3(BaseModel):
    """Purpose-discriminated zero-capable paid-call projection."""

    model_config = _STRICT_FROZEN

    purpose: FactoryPaidBudgetPurposeV2
    purpose_label: Literal[
        "스토리보드 이미지 16장",
        "선택 이미지 재생성",
        "최종 영상 제작",
    ]
    script: int = Field(ge=0, le=1)
    image: int = Field(ge=0, le=16)
    video: int = Field(ge=0, le=16)
    voice: int = Field(ge=0, le=16)
    render: int = Field(ge=0, le=1)
    retries: Literal[0]
    fallbacks: Literal[0]
    character_lock: Literal[0]
    all_beat_count: Literal[16]
    storyboard_scene_count: int | None = Field(ge=1, le=16)
    paid_budget_authority_digest: DigestStr | None
    storyboard_scene_video_set_summary: StoryboardSceneVideoSetSummaryV1 | None

    @model_validator(mode="after")
    def _bind_purpose_label_and_paid_call_mask(self) -> "StarReelsBudgetV3":
        if self.purpose_label != _STAR_REELS_PURPOSE_LABELS_V3[self.purpose]:
            raise ValueError("purpose_label does not match purpose")
        expected = factory_paid_call_cardinality_v2(
            self.purpose,
            regen_image_count=(
                self.image if self.purpose == "storyboard_regen" else None
            ),
            storyboard_scene_count=self.storyboard_scene_count,
        )
        observed = {
            "script": self.script,
            "image": self.image,
            "video": self.video,
            "voice": self.voice,
            "render": self.render,
            "retries": self.retries,
            "fallbacks": self.fallbacks,
            "character_lock": self.character_lock,
        }
        if observed != expected:
            raise ValueError("paid call mask does not match purpose")
        scene_video_set = self.storyboard_scene_video_set_summary
        if self.purpose != "final_production" and scene_video_set is not None:
            raise ValueError("storyboard budget cannot carry scene video summary")
        if scene_video_set is not None and (
            self.paid_budget_authority_digest is None
            or scene_video_set.storyboard_scene_count != self.storyboard_scene_count
            or scene_video_set.final_production_authority_digest
            != self.paid_budget_authority_digest
        ):
            raise ValueError("scene video summary does not match final paid budget")
        return self


class StarReelsViewV3(BaseModel):
    """Two-stage storyboard projection; V2 replay semantics remain untouched."""

    model_config = _STRICT_FROZEN

    contract_version: Literal["StarReelsView.v3"]
    section: Literal[
        "LockGate",
        "ScriptReview",
        "PlanReview",
        "StoryboardReview",
        "ProductionBudgetApproval",
        "RunStatus",
    ]
    status: Literal[
        "missing",
        "awaiting_product_approval",
        "revoked",
        "digest_drift",
        "awaiting_script_approval",
        "awaiting_plan_approval",
        "storyboard_generating",
        "awaiting_storyboard_review",
        "awaiting_production_budget_approval",
        "pending",
        "rendering",
        "ready",
        "failed",
    ]
    revision: int = Field(ge=0)
    stage_output: (
        ProductElementLockDraftV1 | FactoryStoryboardCarrierV1 | dict[str, Any] | None
    )
    budget: StarReelsBudgetV3
    review_digest: DigestStr | None
    receipts: _StarReelsViewReceiptsV3
    provider_call: Literal["none", "confirmed", "unknown"]
    error: NonBlankStr | None
    storyboard: FactoryStoryboardCarrierV1 | None

    @field_validator("stage_output", mode="before")
    @classmethod
    def _freeze_typed_review_output(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        contract_version = value.get("contract_version")
        if contract_version == "ProductElementLockDraft.v1":
            return ProductElementLockDraftV1.model_validate(value)
        if contract_version == "FactoryStoryboardCarrier.v1":
            return FactoryStoryboardCarrierV1.model_validate(value)
        return value

    @model_validator(mode="after")
    def _bind_view_shape_to_state(self) -> "StarReelsViewV3":
        self._require_valid_section_status_pair()
        if self.section in {"LockGate", "ScriptReview", "PlanReview"}:
            self._bind_legacy_gate()
        elif self.section == "StoryboardReview":
            self._bind_storyboard_review()
        elif self.section == "ProductionBudgetApproval":
            self._bind_production_budget_gate()
        else:
            self._bind_two_stage_run()
        self._bind_phase_a_completion_summary()
        self._bind_paid_budget_evidence()
        self._bind_factory_receipt_provider_state()
        return self

    def _require_valid_section_status_pair(self) -> None:
        valid_pair = (
            (
                self.section == "LockGate"
                and self.status
                in {
                    "missing",
                    "awaiting_product_approval",
                    "revoked",
                    "digest_drift",
                    "ready",
                }
            )
            or (
                self.section == "ScriptReview"
                and self.status == "awaiting_script_approval"
            )
            or (
                self.section == "PlanReview" and self.status == "awaiting_plan_approval"
            )
            or (
                self.section == "StoryboardReview"
                and self.status
                in {"storyboard_generating", "awaiting_storyboard_review"}
            )
            or (
                self.section == "ProductionBudgetApproval"
                and self.status == "awaiting_production_budget_approval"
            )
            or (
                self.section == "RunStatus"
                and self.status in {"pending", "rendering", "ready", "failed"}
            )
        )
        if not valid_pair:
            raise ValueError("section does not match durable status")

    def _bind_legacy_gate(self) -> None:
        if self.budget.purpose != "storyboard_draft":
            raise ValueError("legacy pre-storyboard gate requires draft budget purpose")
        if self.storyboard is not None:
            raise ValueError("pre-storyboard gate cannot carry storyboard pointer")
        if self.section == "LockGate":
            self._bind_lock_gate()
            return
        if self.stage_output is None or self.review_digest is None:
            raise ValueError("review state requires stage_output and review_digest")
        if self.provider_call != "confirmed" or self.error is not None:
            raise ValueError("review state requires one confirmed script call")
        if not isinstance(self.receipts.factory, ReelsFactoryProgressReceiptV3):
            raise ValueError("review state requires V3 progress receipt")

    def _bind_lock_gate(self) -> None:
        product_review = self.status == "awaiting_product_approval"
        if product_review:
            if not isinstance(self.stage_output, ProductElementLockDraftV1):
                raise ValueError("product review requires typed product draft")
            if self.review_digest != derive_star_product_lock_review_digest_v1(
                self.stage_output
            ):
                raise ValueError("product review digest does not bind the draft")
        elif self.stage_output is not None or self.review_digest is not None:
            raise ValueError("non-review state cannot carry review-only fields")
        if self.provider_call != "none" or self.receipts.factory is not None:
            raise ValueError("LockGate cannot carry provider work")
        lock_has_no_error = self.status in {
            "ready",
            "awaiting_product_approval",
        }
        if lock_has_no_error != (self.error is None):
            raise ValueError("LockGate error does not match lock state")

    def _bind_storyboard_review(self) -> None:
        if self.budget.purpose not in {"storyboard_draft", "storyboard_regen"}:
            raise ValueError("StoryboardReview budget purpose is invalid")
        if (
            self.provider_call != "confirmed"
            or self.error is not None
            or not isinstance(
                self.receipts.factory,
                ReelsFactoryProgressReceiptV3,
            )
        ):
            raise ValueError("StoryboardReview requires confirmed image work")
        pointer = self.storyboard
        if self.status == "storyboard_generating":
            if self.budget.purpose == "storyboard_draft":
                if (
                    pointer is not None
                    or self.stage_output is not None
                    or self.review_digest is not None
                ):
                    raise ValueError(
                        "storyboard draft generating cannot carry a projection"
                    )
                return
            if pointer is None:
                raise ValueError("storyboard regen generating requires a pointer")
            if (
                pointer.approval_receipt_digest is not None
                or pointer.execution_manifest_digest is not None
            ):
                raise ValueError(
                    "generating storyboard cannot carry approval or execution manifest"
                )
            if self.stage_output != pointer or self.review_digest is not None:
                raise ValueError(
                    "regen generating pointer must be echoed without review digest"
                )
            return
        if pointer is None or self.stage_output != pointer:
            raise ValueError(
                "storyboard review requires the current storyboard pointer"
            )
        if pointer.approval_receipt_digest is not None:
            raise ValueError("unapproved storyboard review cannot carry approval")
        if pointer.execution_manifest_digest is not None:
            raise ValueError("storyboard review cannot carry execution manifest")
        if self.review_digest != pointer.storyboard_digest:
            raise ValueError("review_digest does not bind current storyboard")

    def _bind_production_budget_gate(self) -> None:
        if self.budget.purpose != "final_production":
            raise ValueError("ProductionBudgetApproval budget purpose is invalid")
        pointer = self.storyboard
        if pointer is None or self.stage_output != pointer:
            raise ValueError("production budget gate requires storyboard pointer")
        if pointer.approval_receipt_digest is None:
            raise ValueError("production budget gate requires storyboard approval")
        if pointer.execution_manifest_digest is not None:
            raise ValueError("production budget gate cannot carry execution manifest")
        if self.review_digest != pointer.approval_receipt_digest:
            raise ValueError("review_digest does not bind storyboard approval")
        if self.budget.paid_budget_authority_digest is not None:
            raise ValueError("unapproved final budget cannot carry authority digest")
        if (
            self.provider_call != "none"
            or self.error is not None
            or self.receipts.factory is not None
        ):
            raise ValueError("production budget gate cannot carry provider work")

    def _bind_two_stage_run(self) -> None:
        if self.budget.purpose != "final_production":
            raise ValueError("RunStatus budget purpose must be final_production")
        if self.budget.paid_budget_authority_digest is None:
            raise ValueError("RunStatus requires final paid authority digest")
        pointer = self.storyboard
        if (
            pointer is None
            or pointer.approval_receipt_digest is None
            or pointer.execution_manifest_digest is None
        ):
            raise ValueError("RunStatus requires approved execution manifest pointer")
        if self.stage_output is not None or self.review_digest is not None:
            raise ValueError("RunStatus cannot carry review-only fields")
        if self.status == "failed":
            if self.error is None or not isinstance(
                self.receipts.factory,
                ReelsFactoryFailureReceiptV3,
            ):
                raise ValueError("failed state requires error and failure receipt")
        elif self.error is not None:
            raise ValueError("non-failed state cannot carry an error")
        if self.status in {"pending", "rendering"} and not isinstance(
            self.receipts.factory,
            ReelsFactoryProgressReceiptV3,
        ):
            raise ValueError("active state requires progress receipt")
        if self.status == "ready" and not isinstance(
            self.receipts.factory,
            ReelsFactoryCompletionSummaryV3,
        ):
            raise ValueError("ready state requires final factory summary")

    def _bind_paid_budget_evidence(self) -> None:
        approval = self.receipts.paid_budget_approval_receipt
        authority = self.receipts.paid_budget_authority
        if self.section == "ProductionBudgetApproval":
            if (
                approval is not None
                or authority is not None
                or self.budget.paid_budget_authority_digest is not None
            ):
                raise ValueError(
                    "unapproved final budget cannot carry paid budget pair or authority"
                )
            return

        if approval is None or authority is None:
            raise ValueError("V3 purpose state requires a complete paid budget pair")
        if not approval.structurally_binds(authority):
            raise ValueError("paid budget pair does not structurally bind authority")
        if authority.purpose != self.budget.purpose:
            raise ValueError(
                "paid authority purpose does not match view budget purpose"
            )
        observed_calls = {
            "script": self.budget.script,
            "image": self.budget.image,
            "video": self.budget.video,
            "voice": self.budget.voice,
            "render": self.budget.render,
            "retries": self.budget.retries,
            "fallbacks": self.budget.fallbacks,
            "character_lock": self.budget.character_lock,
        }
        if authority.paid_calls.model_dump(mode="python") != observed_calls:
            raise ValueError("paid authority calls do not match view budget")
        if (
            authority.all_beat_count != self.budget.all_beat_count
            or authority.storyboard_scene_count != self.budget.storyboard_scene_count
            or authority.authority_digest != self.budget.paid_budget_authority_digest
        ):
            raise ValueError("paid authority does not bind the current view budget")

        pointer = self.storyboard
        if authority.purpose == "storyboard_regen":
            if pointer is None:
                raise ValueError("regen authority requires current storyboard")
            if self.status == "storyboard_generating" and (
                authority.storyboard_draft_digest != pointer.storyboard_digest
            ):
                raise ValueError("regen authority does not bind current storyboard")
        if authority.purpose == "final_production" and (
            pointer is None
            or authority.storyboard_draft_digest != pointer.storyboard_digest
            or authority.storyboard_approval_receipt_digest
            != pointer.approval_receipt_digest
        ):
            raise ValueError("final authority does not bind approved storyboard")

        factory = self.receipts.factory
        if isinstance(
            factory,
            (ReelsFactoryProgressReceiptV3, ReelsFactoryFailureReceiptV3),
        ):
            if not factory.structurally_binds(authority):
                raise ValueError("factory receipt does not bind paid authority")
            if factory.revision != self.revision:
                raise ValueError("factory receipt revision does not match view")
            expected_manifest_digest = (
                pointer.execution_manifest_digest
                if authority.purpose == "final_production" and pointer is not None
                else None
            )
            if factory.storyboard_execution_manifest_digest != expected_manifest_digest:
                raise ValueError(
                    "factory receipt execution manifest does not match storyboard"
                )
        elif isinstance(factory, ReelsFactoryCompletionSummaryV3):
            if (
                authority.purpose != "final_production"
                or pointer is None
                or factory.workspace_id != authority.workspace_id
                or factory.run_id != authority.run_id
                or factory.factory_revision != authority.factory_revision
                or factory.plan_digest != authority.plan_digest
                or factory.paid_budget_authority_digest != authority.authority_digest
                or factory.storyboard_execution_manifest_digest
                != pointer.execution_manifest_digest
            ):
                raise ValueError("factory success does not bind final paid authority")

    def _bind_phase_a_completion_summary(self) -> None:
        summary = self.receipts.storyboard_phase_a_completion_summary
        if self.section in {
            "LockGate",
            "ScriptReview",
            "PlanReview",
        } or self.status == ("storyboard_generating"):
            if summary is not None:
                raise ValueError(
                    "pre-completion state cannot carry Phase-A completion summary"
                )
            return
        if summary is None:
            raise ValueError("post-Phase-A state requires Phase-A completion summary")
        pointer = self.storyboard
        if pointer is None:
            raise ValueError("Phase-A completion summary requires storyboard pointer")
        if (
            summary.output_image_set_receipt_digest != pointer.image_set_receipt_digest
            or pointer.storyboard_revision < summary.output_storyboard_revision
        ):
            raise ValueError("Phase-A completion does not bind storyboard lineage")
        if pointer.storyboard_revision == summary.output_storyboard_revision and (
            pointer.storyboard_digest != summary.output_storyboard_digest
        ):
            raise ValueError("Phase-A completion does not bind current storyboard")
        if self.section == "StoryboardReview":
            authority = self.receipts.paid_budget_authority
            if (
                summary.purpose != self.budget.purpose
                or authority is None
                or summary.paid_budget_authority_digest != authority.authority_digest
            ):
                raise ValueError("Phase-A completion does not bind image authority")
            if pointer.storyboard_revision == summary.output_storyboard_revision:
                unapproved_pointer = FactoryStoryboardCarrierV1(
                    contract_version="FactoryStoryboardCarrier.v1",
                    storyboard_revision=pointer.storyboard_revision,
                    storyboard_digest=pointer.storyboard_digest,
                    image_set_receipt_digest=pointer.image_set_receipt_digest,
                    approval_receipt_digest=None,
                    execution_manifest_digest=None,
                )
                if summary.output_storyboard_carrier_digest != (
                    derive_factory_storyboard_carrier_digest_v1(unapproved_pointer)
                ):
                    raise ValueError("Phase-A completion carrier digest drifted")

    def _bind_factory_receipt_provider_state(self) -> None:
        factory = self.receipts.factory
        if isinstance(factory, ReelsFactoryFailureReceiptV3):
            expected_provider_call = factory.provider_call
        elif isinstance(factory, ReelsFactoryProgressReceiptV3):
            expected_provider_call = (
                "confirmed"
                if sum(factory.provider_attempts.model_dump().values()) > 0
                else "none"
            )
        elif isinstance(factory, ReelsFactoryCompletionSummaryV3):
            expected_provider_call = "confirmed"
            scene_video_set = self.budget.storyboard_scene_video_set_summary
            pointer = self.storyboard
            if (
                scene_video_set is None
                or pointer is None
                or factory.storyboard_scene_video_set_receipt_digest
                != scene_video_set.scene_video_set_receipt_digest
                or factory.storyboard_scene_video_set_summary_digest
                != scene_video_set.summary_digest
                or factory.paid_budget_authority_digest
                != self.budget.paid_budget_authority_digest
                or factory.storyboard_execution_manifest_digest
                != pointer.execution_manifest_digest
            ):
                raise ValueError(
                    "sealed scene video budget does not match ready summary"
                )
        else:
            expected_provider_call = None
        if (
            expected_provider_call is not None
            and self.provider_call != expected_provider_call
        ):
            raise ValueError("provider_call does not match typed factory receipt")


__all__ = [
    "FactoryStoryboardCarrierV1",
    "StoryboardPhaseACompletionReceiptV1",
    "StoryboardPhaseACompletionSummaryV1",
    "StarReelsBudgetV3",
    "StarReelsViewV1",
    "StarReelsViewV2",
    "StarReelsViewV3",
    "_StarReelsBudgetMultiBeatV1",
    "derive_factory_storyboard_carrier_digest_v1",
    "derive_storyboard_phase_a_completion_receipt_digest_v1",
    "derive_storyboard_phase_a_completion_summary_digest_v1",
    "derive_star_product_lock_review_digest_v1",
]
