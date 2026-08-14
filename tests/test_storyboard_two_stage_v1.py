"""Two-stage storyboard contracts keep paid production behind editor approval."""

from __future__ import annotations

from copy import copy, deepcopy
import json
import pickle
from typing import Any, Callable

import pytest
from pydantic import ValidationError

import hiob_contracts
from hiob_contracts import (
    FactoryPaidBudgetAuthorityV1,
    FactoryPaidBudgetApprovalReceiptV2,
    FactoryPaidBudgetApprovalResolverV2,
    FactoryPaidBudgetAuthorityV2,
    FactoryPaidBudgetResolutionV2,
    VerifiedFactoryPaidBudgetAuthorityV2,
    StoryboardApprovalReceiptV1,
    StoryboardDraftV1,
    StoryboardExecutionManifestV1,
    StoryboardImageArtifactRefV1,
    StoryboardImageSetReceiptV1,
    StoryboardSelectedArtifactV1,
    canonical_contract_digest_v1,
    derive_factory_paid_budget_approval_subject_digest_v2,
    derive_factory_paid_budget_approval_receipt_digest_v2,
    derive_factory_paid_budget_authority_digest_v2,
    derive_factory_paid_budget_idempotency_key_v2,
    derive_storyboard_approval_receipt_digest_v1,
    derive_storyboard_beat_identity_digest_v1,
    derive_storyboard_card_digest_v1,
    derive_storyboard_draft_digest_v1,
    derive_storyboard_execution_manifest_digest_v1,
    derive_storyboard_image_artifact_digest_v1,
    derive_storyboard_image_set_receipt_digest_v1,
    registered_contracts,
    sha256_digest,
    validate_payload,
)


WORKSPACE_ID = "00000000-0000-4000-8000-000000000001"
RUN_ID = "00000000-0000-4000-8000-000000000002"
DRAFT_ID = "00000000-0000-4000-8000-000000000003"
MANIFEST_ID = "00000000-0000-4000-8000-000000000004"
PLAN_DIGEST = sha256_digest({"plan": "sixteen-beat-storyboard"})
DRAFT_AUTHORITY_DIGEST = sha256_digest({"authority": "storyboard-draft"})
FINAL_AUTHORITY_DIGEST = sha256_digest({"authority": "final-production"})
COST_PROFILE_DIGEST = sha256_digest({"pricing": "storyboard-2026-08-14"})


class _ApprovalResolverV2:
    def __init__(self, current: bool = True) -> None:
        self.current = current
        self.last_identity: dict[str, Any] | None = None

    def is_current_approval(self, **identity: Any) -> bool:
        self.last_identity = identity
        return self.current


def _sealed(
    body: dict[str, Any],
    *,
    digest_field: str,
    derive: Callable[[dict[str, Any]], str],
) -> dict[str, Any]:
    value = deepcopy(body)
    value[digest_field] = derive(value)
    return value


def _image(source_beat_index: int, **changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "contract_version": "StoryboardImageArtifactRef.v1",
        "source_beat_index": source_beat_index,
        "artifact_id": f"storyboard-image-{source_beat_index:02d}",
        "storage_key": (
            f"workspaces/{WORKSPACE_ID}/runs/{RUN_ID}/"
            f"storyboard/{source_beat_index:02d}.webp"
        ),
        "sha256": sha256_digest({"image": source_beat_index}),
        "mime": "image/webp",
        "width": 1080,
        "height": 1920,
        "provider_receipt_digest": sha256_digest(
            {"provider_receipt": source_beat_index}
        ),
        "frame_plan_digest": sha256_digest({"frame_plan": source_beat_index}),
        "generation_nonce": (f"00000000-0000-4000-8000-{source_beat_index + 100:012d}"),
    }
    body.update(changes)
    return _sealed(
        body,
        digest_field="artifact_digest",
        derive=derive_storyboard_image_artifact_digest_v1,
    )


def _image_set(*, images: list[dict[str, Any]] | None = None, **changes: Any):
    body: dict[str, Any] = {
        "contract_version": "StoryboardImageSetReceipt.v1",
        "receipt_id": "storyboard-image-set-1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "plan_digest": PLAN_DIGEST,
        "paid_budget_authority_digest": DRAFT_AUTHORITY_DIGEST,
        "expected_image_count": 16,
        "images": images if images is not None else [_image(i) for i in range(16)],
        "completed_at_utc": "2026-08-14T05:00:00Z",
    }
    body.update(changes)
    sealed = _sealed(
        body,
        digest_field="receipt_digest",
        derive=derive_storyboard_image_set_receipt_digest_v1,
    )
    return StoryboardImageSetReceiptV1.model_validate(sealed)


def _card(
    source_beat_index: int,
    sequence_index: int,
    *,
    image: StoryboardImageArtifactRefV1,
    **changes: Any,
) -> dict[str, Any]:
    beat_text = f"immutable beat text {source_beat_index}"
    body: dict[str, Any] = {
        "contract_version": "StoryboardCard.v1",
        "source_beat_index": source_beat_index,
        "sequence_index": sequence_index,
        "scene_id": f"scene-{source_beat_index // 2:02d}",
        "beat_text": beat_text,
        "beat_identity_digest": derive_storyboard_beat_identity_digest_v1(
            PLAN_DIGEST, source_beat_index, beat_text
        ),
        "prompt_override": None,
        "crop_mode": "cover",
        "focal_x_basis_points": 5_000,
        "focal_y_basis_points": 5_000,
        "motion_note": None,
        "selected_artifact": {
            "artifact_id": image.artifact_id,
            "artifact_digest": image.artifact_digest,
        },
    }
    body.update(changes)
    return _sealed(
        body,
        digest_field="card_digest",
        derive=derive_storyboard_card_digest_v1,
    )


def _cards(
    image_set: StoryboardImageSetReceiptV1,
    order: list[int] | None = None,
) -> list[dict[str, Any]]:
    source_order = order if order is not None else list(range(16))
    images = {image.source_beat_index: image for image in image_set.images}
    return [
        _card(source, sequence, image=images[source])
        for sequence, source in enumerate(source_order)
    ]


def _draft(
    image_set: StoryboardImageSetReceiptV1,
    *,
    cards: list[dict[str, Any]] | None = None,
    revision: int = 1,
    parent_draft_digest: str | None = None,
    **changes: Any,
) -> StoryboardDraftV1:
    body: dict[str, Any] = {
        "contract_version": "StoryboardDraft.v1",
        "draft_id": DRAFT_ID,
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "plan_digest": PLAN_DIGEST,
        "image_set_receipt_digest": image_set.receipt_digest,
        "revision": revision,
        "parent_draft_digest": parent_draft_digest,
        "cards": cards if cards is not None else _cards(image_set),
    }
    body.update(changes)
    sealed = _sealed(
        body,
        digest_field="draft_digest",
        derive=derive_storyboard_draft_digest_v1,
    )
    return StoryboardDraftV1.model_validate(sealed)


def _approval(
    draft: StoryboardDraftV1,
    image_set: StoryboardImageSetReceiptV1,
    **changes: Any,
) -> StoryboardApprovalReceiptV1:
    body: dict[str, Any] = {
        "contract_version": "StoryboardApprovalReceipt.v1",
        "receipt_id": "storyboard-approval-1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "plan_digest": PLAN_DIGEST,
        "draft_id": draft.draft_id,
        "draft_revision": draft.revision,
        "storyboard_draft_digest": draft.draft_digest,
        "image_set_receipt_digest": image_set.receipt_digest,
        "approver_account_id": "account-owner",
        "decision": "approved",
        "policy_version": "storyboard-editor-approval-v1",
        "approved_at_utc": "2026-08-14T05:10:00Z",
        "transaction_audit_id": "storyboard-approval-1",
    }
    body.update(changes)
    sealed = _sealed(
        body,
        digest_field="receipt_digest",
        derive=derive_storyboard_approval_receipt_digest_v1,
    )
    return StoryboardApprovalReceiptV1.model_validate(sealed)


def _calls(purpose: str, image_count: int = 16) -> dict[str, int]:
    if purpose == "storyboard_draft":
        return {
            "script": 1,
            "image": 16,
            "video": 0,
            "voice": 0,
            "render": 0,
            "retries": 0,
            "fallbacks": 0,
            "character_lock": 0,
        }
    if purpose == "storyboard_regen":
        return {
            "script": 0,
            "image": image_count,
            "video": 0,
            "voice": 0,
            "render": 0,
            "retries": 0,
            "fallbacks": 0,
            "character_lock": 0,
        }
    return {
        "script": 0,
        "image": 0,
        "video": 16,
        "voice": 16,
        "render": 1,
        "retries": 0,
        "fallbacks": 0,
        "character_lock": 0,
    }


def _authority(
    purpose: str,
    *,
    image_source_beat_indices: list[int] | None = None,
    **changes: Any,
) -> dict[str, Any]:
    if image_source_beat_indices is None:
        image_source_beat_indices = (
            list(range(16)) if purpose == "storyboard_draft" else []
        )
    image_count = len(image_source_beat_indices)
    body: dict[str, Any] = {
        "contract_version": "FactoryPaidBudgetAuthority.v2",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "all_beat_count": 16,
        "purpose": purpose,
        "plan_digest": PLAN_DIGEST,
        "storyboard_draft_digest": (
            None if purpose == "storyboard_draft" else sha256_digest({"draft": 1})
        ),
        "storyboard_approval_receipt_digest": (
            sha256_digest({"storyboard_approval": 1})
            if purpose == "final_production"
            else None
        ),
        "image_source_beat_indices": image_source_beat_indices,
        "paid_calls": _calls(purpose, image_count),
        "max_total_cost_microunits": 20_000_000,
        "currency": "USD",
        "cost_profile_digest": COST_PROFILE_DIGEST,
        "pricing_policy_revision": 4,
        "approval_receipt_id": f"paid-approval-{purpose}",
        "approval_receipt_digest": sha256_digest(
            {"paid_approval": purpose, "beats": image_source_beat_indices}
        ),
    }
    body.update(changes)
    body["approval_subject_digest"] = (
        derive_factory_paid_budget_approval_subject_digest_v2(body)
    )
    body["idempotency_key"] = derive_factory_paid_budget_idempotency_key_v2(body)
    body["authority_digest"] = derive_factory_paid_budget_authority_digest_v2(body)
    return body


def _paid_approval_receipt_v2(
    purpose: str,
    *,
    image_source_beat_indices: list[int] | None = None,
    **changes: Any,
) -> FactoryPaidBudgetApprovalReceiptV2:
    authority = _authority(
        purpose,
        image_source_beat_indices=image_source_beat_indices,
    )
    body: dict[str, Any] = {
        "contract_version": "FactoryPaidBudgetApprovalReceipt.v2",
        "receipt_id": authority["approval_receipt_id"],
        "workspace_id": authority["workspace_id"],
        "run_id": authority["run_id"],
        "factory_revision": authority["factory_revision"],
        "all_beat_count": authority["all_beat_count"],
        "purpose": authority["purpose"],
        "plan_digest": authority["plan_digest"],
        "storyboard_draft_digest": authority["storyboard_draft_digest"],
        "storyboard_approval_receipt_digest": authority[
            "storyboard_approval_receipt_digest"
        ],
        "image_source_beat_indices": authority["image_source_beat_indices"],
        "paid_calls": authority["paid_calls"],
        "max_total_cost_microunits": authority["max_total_cost_microunits"],
        "currency": authority["currency"],
        "cost_profile_digest": authority["cost_profile_digest"],
        "pricing_policy_revision": authority["pricing_policy_revision"],
        "approval_subject_digest": authority["approval_subject_digest"],
        "approver_account_id": "account-owner",
        "decision": "approved",
        "policy_version": "factory-paid-budget.v2",
        "state_revision": 2,
        "approved_at_utc": "2026-08-14T05:00:00Z",
        "expires_at_utc": "2026-08-14T07:00:00Z",
        "revoked_at_utc": None,
        "transaction_audit_id": authority["approval_receipt_id"],
    }
    body.update(changes)
    body["approval_subject_digest"] = (
        derive_factory_paid_budget_approval_subject_digest_v2(body)
    )
    body["receipt_digest"] = derive_factory_paid_budget_approval_receipt_digest_v2(
        body
    )
    return FactoryPaidBudgetApprovalReceiptV2.model_validate(body)


def _authority_bound_to_receipt(
    receipt: FactoryPaidBudgetApprovalReceiptV2,
) -> dict[str, Any]:
    body = _authority(
        receipt.purpose,
        image_source_beat_indices=list(receipt.image_source_beat_indices),
        storyboard_draft_digest=receipt.storyboard_draft_digest,
        storyboard_approval_receipt_digest=(
            receipt.storyboard_approval_receipt_digest
        ),
        max_total_cost_microunits=receipt.max_total_cost_microunits,
        currency=receipt.currency,
        cost_profile_digest=receipt.cost_profile_digest,
        pricing_policy_revision=receipt.pricing_policy_revision,
        approval_receipt_id=receipt.receipt_id,
        approval_receipt_digest=receipt.receipt_digest,
    )
    return body


def _cost_profile() -> dict[str, Any]:
    body: dict[str, Any] = {
        "contract_version": "FactoryCostProfile.v1",
        "profile_id": "storyboard-profile-v1",
        "currency": "USD",
        "pricing_policy_revision": 4,
        "valid_from_utc": "2026-08-14T00:00:00Z",
        "valid_until_utc": "2026-08-15T00:00:00Z",
        "operations": {
            "script": {"rate_microunits": 2_000_000},
            "image": {"rate_microunits": 1_000_000},
            "video": {"rate_microunits": 100_000},
            "voice": {"rate_microunits": 90},
            "render": {"rate_microunits": 2_000_000},
        },
    }
    return {
        **body,
        "profile_digest": canonical_contract_digest_v1(body),
    }


def _manifest(
    draft: StoryboardDraftV1,
    image_set: StoryboardImageSetReceiptV1,
    approval: StoryboardApprovalReceiptV1,
    **changes: Any,
) -> StoryboardExecutionManifestV1:
    body: dict[str, Any] = {
        "contract_version": "StoryboardExecutionManifest.v1",
        "manifest_id": MANIFEST_ID,
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "plan_digest": PLAN_DIGEST,
        "draft_id": draft.draft_id,
        "draft_revision": draft.revision,
        "storyboard_draft_digest": draft.draft_digest,
        "image_set_receipt_digest": image_set.receipt_digest,
        "storyboard_approval_receipt_digest": approval.receipt_digest,
        "final_production_authority_digest": FINAL_AUTHORITY_DIGEST,
        "cards": [card.model_dump(mode="json") for card in draft.cards],
        "images": [image.model_dump(mode="json") for image in image_set.images],
    }
    body.update(changes)
    sealed = _sealed(
        body,
        digest_field="manifest_digest",
        derive=derive_storyboard_execution_manifest_digest_v1,
    )
    return StoryboardExecutionManifestV1.model_validate(sealed)


def test_image_ref_is_url_free_strict_frozen_and_digest_bound() -> None:
    image = StoryboardImageArtifactRefV1.model_validate(_image(0))

    assert image.source_beat_index == 0
    assert image.storage_key.endswith("storyboard/00.webp")
    assert "url" not in StoryboardImageArtifactRefV1.model_fields
    assert image.artifact_digest == derive_storyboard_image_artifact_digest_v1(image)
    with pytest.raises((ValidationError, TypeError)):
        image.storage_key = "other.webp"


@pytest.mark.parametrize(
    "storage_key",
    [
        "https://cdn.example/image.webp",
        "http://cdn.example/image.webp",
        "data:image/png;base64,AAAA",
        "file:///tmp/image.webp",
        "/absolute/image.webp",
        "../escape.webp",
        "storyboard/image.webp?token=secret",
        "storyboard\\image.webp",
    ],
)
def test_image_ref_rejects_url_absolute_or_credential_bearing_storage_keys(
    storage_key: str,
) -> None:
    with pytest.raises(ValidationError, match="storage_key"):
        StoryboardImageArtifactRefV1.model_validate(_image(0, storage_key=storage_key))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_beat_index", 16),
        ("source_beat_index", True),
        ("width", 0),
        ("height", 1.5),
        ("mime", "video/mp4"),
        ("generation_nonce", "not-a-uuid"),
    ],
)
def test_image_ref_rejects_noncanonical_fields(field: str, value: Any) -> None:
    payload = _image(0)
    payload[field] = value
    with pytest.raises(ValidationError):
        StoryboardImageArtifactRefV1.model_validate(payload)


def test_image_set_is_exactly_sixteen_unique_ordered_source_beats() -> None:
    image_set = _image_set()

    assert [image.source_beat_index for image in image_set.images] == list(range(16))
    assert len({image.artifact_id for image in image_set.images}) == 16
    assert image_set.receipt_digest == derive_storyboard_image_set_receipt_digest_v1(
        image_set
    )


@pytest.mark.parametrize("mutation", ["missing", "duplicate_beat", "duplicate_asset"])
def test_image_set_rejects_partial_or_aliased_paid_results(mutation: str) -> None:
    images = [_image(i) for i in range(16)]
    if mutation == "missing":
        images.pop()
    elif mutation == "duplicate_beat":
        images[15] = _image(14, artifact_id="storyboard-image-alias")
    else:
        images[15] = _image(
            15,
            artifact_id=images[0]["artifact_id"],
            storage_key=images[0]["storage_key"],
            sha256=images[0]["sha256"],
            generation_nonce=images[0]["generation_nonce"],
        )

    with pytest.raises(ValidationError):
        _image_set(images=images)


def test_draft_separates_immutable_source_identity_from_editor_sequence() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    reordered_cards = _cards(image_set, list(reversed(range(16))))
    reordered_cards[0] = _card(
        15,
        0,
        image=image_set.images[15],
        prompt_override="closer product framing",
        crop_mode="contain",
        focal_x_basis_points=7_500,
        focal_y_basis_points=3_000,
        motion_note="slow push-in; editorial note only",
    )
    revised = _draft(
        image_set,
        cards=reordered_cards,
        revision=2,
        parent_draft_digest=draft.draft_digest,
    )

    assert [card.sequence_index for card in revised.cards] == list(range(16))
    assert [card.source_beat_index for card in revised.cards] == list(
        reversed(range(16))
    )
    assert revised.is_valid_successor_of(draft)
    assert revised.cards[0].beat_identity_digest == draft.cards[15].beat_identity_digest
    assert revised.cards[0].selected_artifact == draft.cards[15].selected_artifact
    assert revised.cards[0].scene_id == draft.cards[15].scene_id


def test_successor_rejects_immutable_beat_retarget() -> None:
    image_set = _image_set()
    original = _draft(image_set)
    cards = _cards(image_set)
    changed_text = "retargeted beat text"
    changes = {
        "beat_text": changed_text,
        "beat_identity_digest": derive_storyboard_beat_identity_digest_v1(
            PLAN_DIGEST, 0, changed_text
        ),
    }
    cards[0] = _card(0, 0, image=image_set.images[0], **changes)
    candidate = _draft(
        image_set,
        cards=cards,
        revision=2,
        parent_draft_digest=original.draft_digest,
    )

    assert not candidate.is_valid_successor_of(original)


def test_successor_allows_server_verified_selected_artifact_replacement() -> None:
    image_set = _image_set()
    original = _draft(image_set)
    cards = _cards(image_set)
    replacement = _image(
        0,
        artifact_id="storyboard-image-00-replacement",
        storage_key=(
            f"workspaces/{WORKSPACE_ID}/runs/{RUN_ID}/storyboard/00-replacement.webp"
        ),
        sha256=sha256_digest({"replacement": 0}),
        provider_receipt_digest=sha256_digest({"regen_receipt": 0}),
        generation_nonce="00000000-0000-4000-8000-000000000900",
    )
    cards[0] = _card(
        0,
        0,
        image=image_set.images[0],
        selected_artifact={
            "artifact_id": replacement["artifact_id"],
            "artifact_digest": replacement["artifact_digest"],
        },
    )
    candidate = _draft(
        image_set,
        cards=cards,
        revision=2,
        parent_draft_digest=original.draft_digest,
    )

    assert candidate.is_valid_successor_of(original)
    assert candidate.binds_image_set(image_set)
    assert candidate.cards[0].selected_artifact.artifact_id.endswith("replacement")


@pytest.mark.parametrize(
    "mutation",
    ["missing", "duplicate_sequence", "duplicate_source", "identity"],
)
def test_draft_rejects_non_permutation_or_retargeted_card(mutation: str) -> None:
    image_set = _image_set()
    cards = _cards(image_set)
    if mutation == "missing":
        cards.pop()
    elif mutation == "duplicate_sequence":
        cards[15] = _card(15, 14, image=image_set.images[15])
    elif mutation == "duplicate_source":
        cards[15] = _card(14, 15, image=image_set.images[14])
    elif mutation == "identity":
        cards[0] = _card(
            0,
            0,
            image=image_set.images[0],
            beat_identity_digest=sha256_digest({"alien": "beat"}),
        )
    with pytest.raises(ValidationError):
        _draft(image_set, cards=cards)


def test_draft_revision_requires_parent_and_current_image_set_binding() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    assert draft.binds_image_set(image_set)

    with pytest.raises(ValidationError, match="parent_draft_digest"):
        _draft(image_set, revision=2)
    with pytest.raises(ValidationError, match="parent_draft_digest"):
        _draft(
            image_set,
            revision=1,
            parent_draft_digest=sha256_digest({"parent": "unexpected"}),
        )

    alien_set = _image_set(plan_digest=sha256_digest({"plan": "alien"}))
    assert not draft.binds_image_set(alien_set)


def test_approval_binds_exact_current_draft_revision_and_image_set() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)

    assert approval.binds(draft, image_set)
    assert approval.receipt_digest == derive_storyboard_approval_receipt_digest_v1(
        approval
    )

    revised = _draft(
        image_set,
        revision=2,
        parent_draft_digest=draft.draft_digest,
    )
    assert not approval.binds(revised, image_set)


def test_approval_rejects_rehashed_audit_or_scope_substitution() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    with pytest.raises(ValidationError, match="transaction_audit_id"):
        _approval(draft, image_set, transaction_audit_id="other-transaction")

    payload = _approval(draft, image_set).model_dump(mode="json")
    payload["storyboard_draft_digest"] = sha256_digest({"draft": "substitute"})
    with pytest.raises(ValidationError, match="receipt_digest"):
        StoryboardApprovalReceiptV1.model_validate(payload)


@pytest.mark.parametrize(
    ("purpose", "indices"),
    [
        ("storyboard_draft", list(range(16))),
        ("storyboard_regen", [2, 7]),
        ("final_production", []),
    ],
)
def test_paid_approval_receipt_v2_mints_only_a_current_verified_capability(
    purpose: str,
    indices: list[int],
) -> None:
    receipt = _paid_approval_receipt_v2(
        purpose,
        image_source_beat_indices=indices,
    )
    raw = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(receipt)
    )
    resolver = _ApprovalResolverV2()

    assert receipt.structurally_binds(raw)
    assert receipt.authorizes(
        raw,
        at_utc="2026-08-14T06:00:00Z",
        resolver=resolver,
    )
    verified = FactoryPaidBudgetAuthorityV2.from_verified(
        raw,
        approval_receipt=receipt,
        at_utc="2026-08-14T06:00:00Z",
        resolver=resolver,
    )
    assert isinstance(verified, VerifiedFactoryPaidBudgetAuthorityV2)
    assert verified.authority == raw
    assert resolver.last_identity is not None
    assert resolver.last_identity["purpose"] == purpose
    assert resolver.last_identity["image_source_beat_indices"] == tuple(indices)

    with pytest.raises(TypeError):
        json.dumps(verified)
    with pytest.raises((TypeError, pickle.PicklingError)):
        pickle.dumps(verified)
    with pytest.raises(TypeError):
        copy(verified)
    with pytest.raises(TypeError, match="only be minted"):
        VerifiedFactoryPaidBudgetAuthorityV2(raw, _token=object())


@pytest.mark.parametrize(
    ("receipt_changes", "at_utc", "current"),
    [
        ({"revoked_at_utc": "2026-08-14T05:30:00Z"}, "2026-08-14T06:00:00Z", True),
        ({}, "2026-08-14T07:00:00Z", True),
        ({}, "2026-08-14T06:00:00Z", False),
    ],
)
def test_paid_authority_v2_rejects_revoked_expired_or_stale_receipt(
    receipt_changes: dict[str, Any],
    at_utc: str,
    current: bool,
) -> None:
    receipt = _paid_approval_receipt_v2("storyboard_draft", **receipt_changes)
    raw = _authority_bound_to_receipt(receipt)

    with pytest.raises(ValueError, match="current durable approval"):
        FactoryPaidBudgetAuthorityV2.from_verified(
            raw,
            approval_receipt=receipt,
            at_utc=at_utc,
            resolver=_ApprovalResolverV2(current),
        )


def test_paid_approval_receipt_v2_is_exact_phase_and_canonical_digest_bound() -> None:
    receipt = _paid_approval_receipt_v2(
        "storyboard_regen",
        image_source_beat_indices=[1, 5, 11],
    )
    assert receipt.policy_version == "factory-paid-budget.v2"
    assert receipt.receipt_digest == (
        derive_factory_paid_budget_approval_receipt_digest_v2(receipt)
    )

    payload = receipt.model_dump(mode="json")
    payload["paid_calls"]["video"] = 1
    payload["approval_subject_digest"] = (
        derive_factory_paid_budget_approval_subject_digest_v2(payload)
    )
    payload["receipt_digest"] = derive_factory_paid_budget_approval_receipt_digest_v2(
        payload
    )
    with pytest.raises(ValidationError, match="paid_calls"):
        FactoryPaidBudgetApprovalReceiptV2.model_validate(payload)

    wrong_policy = receipt.model_dump(mode="json")
    wrong_policy["policy_version"] = "factory-paid-budget.v1"
    wrong_policy["receipt_digest"] = (
        derive_factory_paid_budget_approval_receipt_digest_v2(wrong_policy)
    )
    with pytest.raises(ValidationError):
        FactoryPaidBudgetApprovalReceiptV2.model_validate(wrong_policy)


def test_v2_resolution_output_is_exact_and_binds_cost_profile_and_capability() -> None:
    profile = _cost_profile()
    receipt = _paid_approval_receipt_v2(
        "final_production",
        cost_profile_digest=profile["profile_digest"],
    )
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(receipt)
    )
    resolution = FactoryPaidBudgetResolutionV2.model_validate(
        {
            "approval_receipt": receipt,
            "cost_profile": profile,
            "paid_budget_authority": authority,
        }
    )

    assert set(resolution.model_dump(mode="json")) == {
        "approval_receipt",
        "cost_profile",
        "paid_budget_authority",
    }
    verified = resolution.from_verified(
        at_utc="2026-08-14T06:00:00Z",
        resolver=_ApprovalResolverV2(),
    )
    assert verified.authority == authority

    bad_profile = deepcopy(profile)
    bad_profile["operations"]["image"]["rate_microunits"] += 1
    with pytest.raises(ValidationError, match="cost_profile"):
        FactoryPaidBudgetResolutionV2.model_validate(
            {
                "approval_receipt": receipt,
                "cost_profile": bad_profile,
                "paid_budget_authority": authority,
            }
        )


@pytest.mark.parametrize(
    ("purpose", "indices", "expected_calls"),
    [
        ("storyboard_draft", list(range(16)), (1, 16, 0, 0, 0)),
        ("storyboard_regen", [1], (0, 1, 0, 0, 0)),
        ("storyboard_regen", [1, 4, 9, 15], (0, 4, 0, 0, 0)),
        ("final_production", [], (0, 0, 16, 16, 1)),
    ],
)
def test_authority_v2_allows_only_exact_two_stage_or_regen_lanes(
    purpose: str,
    indices: list[int],
    expected_calls: tuple[int, int, int, int, int],
) -> None:
    authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority(purpose, image_source_beat_indices=indices)
    )

    calls = authority.paid_calls
    assert (calls.script, calls.image, calls.video, calls.voice, calls.render) == (
        expected_calls
    )
    assert calls.retries == calls.fallbacks == calls.character_lock == 0
    assert authority.approval_subject_digest == (
        derive_factory_paid_budget_approval_subject_digest_v2(authority)
    )
    assert authority.idempotency_key == derive_factory_paid_budget_idempotency_key_v2(
        authority
    )
    assert authority.authority_digest == derive_factory_paid_budget_authority_digest_v2(
        authority
    )


@pytest.mark.parametrize(
    ("purpose", "indices", "field", "value"),
    [
        ("storyboard_draft", list(range(16)), "image", 15),
        ("storyboard_draft", list(range(16)), "video", 1),
        ("storyboard_regen", [1, 4], "script", 1),
        ("storyboard_regen", [1, 4], "image", 1),
        ("storyboard_regen", [1, 4], "render", 1),
        ("final_production", [], "image", 1),
        ("final_production", [], "video", 15),
        ("final_production", [], "voice", 15),
        ("final_production", [], "render", 0),
        ("final_production", [], "retries", 1),
        ("final_production", [], "fallbacks", 1),
    ],
)
def test_authority_v2_rejects_cross_phase_paid_call_smuggling(
    purpose: str,
    indices: list[int],
    field: str,
    value: int,
) -> None:
    payload = _authority(purpose, image_source_beat_indices=indices)
    payload["paid_calls"][field] = value
    payload["approval_subject_digest"] = (
        derive_factory_paid_budget_approval_subject_digest_v2(payload)
    )
    payload["idempotency_key"] = derive_factory_paid_budget_idempotency_key_v2(payload)
    payload["authority_digest"] = derive_factory_paid_budget_authority_digest_v2(
        payload
    )

    with pytest.raises(ValidationError, match="paid_calls"):
        FactoryPaidBudgetAuthorityV2.model_validate(payload)


@pytest.mark.parametrize(
    ("purpose", "indices", "changes"),
    [
        ("storyboard_draft", list(range(15)), {}),
        ("storyboard_draft", list(range(16)), {"storyboard_draft_digest": PLAN_DIGEST}),
        ("storyboard_regen", [], {}),
        ("storyboard_regen", [1, 1], {}),
        ("storyboard_regen", [4, 1], {}),
        ("storyboard_regen", [16], {}),
        ("storyboard_regen", [1], {"storyboard_draft_digest": None}),
        (
            "storyboard_regen",
            [1],
            {"storyboard_approval_receipt_digest": PLAN_DIGEST},
        ),
        ("final_production", [1], {}),
        ("final_production", [], {"storyboard_draft_digest": None}),
        (
            "final_production",
            [],
            {"storyboard_approval_receipt_digest": None},
        ),
    ],
)
def test_authority_v2_rejects_wrong_phase_bindings_or_regen_scope(
    purpose: str,
    indices: list[int],
    changes: dict[str, Any],
) -> None:
    payload = _authority(
        purpose,
        image_source_beat_indices=indices,
        **changes,
    )
    with pytest.raises(ValidationError):
        FactoryPaidBudgetAuthorityV2.model_validate(payload)


@pytest.mark.parametrize("value", [True, 1.0, "0", -1])
def test_zero_capable_paid_lanes_remain_strict_safe_integers(value: Any) -> None:
    payload = _authority("final_production")
    payload["paid_calls"]["image"] = value
    with pytest.raises(ValidationError):
        FactoryPaidBudgetAuthorityV2.model_validate(payload)


def test_execution_manifest_binds_approved_cards_images_and_final_authority() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)
    paid_receipt = _paid_approval_receipt_v2(
        "final_production",
        storyboard_draft_digest=draft.draft_digest,
        storyboard_approval_receipt_digest=approval.receipt_digest,
    )
    final_authority = FactoryPaidBudgetAuthorityV2.model_validate(
        _authority_bound_to_receipt(paid_receipt)
    )
    verified = FactoryPaidBudgetAuthorityV2.from_verified(
        final_authority,
        approval_receipt=paid_receipt,
        at_utc="2026-08-14T06:00:00Z",
        resolver=_ApprovalResolverV2(),
    )
    manifest = _manifest(
        draft,
        image_set,
        approval,
        final_production_authority_digest=final_authority.authority_digest,
    )

    assert not manifest.binds(approval, draft, image_set, final_authority)
    assert manifest.binds(approval, draft, image_set, verified)
    assert manifest.manifest_digest == derive_storyboard_execution_manifest_digest_v1(
        manifest
    )
    assert manifest.cards[0].motion_note is None


def test_execution_manifest_rejects_selected_artifact_or_card_tamper() -> None:
    image_set = _image_set()
    draft = _draft(image_set)
    approval = _approval(draft, image_set)
    cards = [card.model_dump(mode="json") for card in draft.cards]
    cards[0] = _card(0, 0, image=image_set.images[1])

    with pytest.raises(ValidationError):
        _manifest(draft, image_set, approval, cards=cards)


def test_registry_and_root_exports_are_additive_and_v1_remains_unchanged() -> None:
    assert hiob_contracts.FactoryPaidBudgetAuthorityV1 is FactoryPaidBudgetAuthorityV1
    assert hiob_contracts.FactoryPaidBudgetAuthorityV2 is FactoryPaidBudgetAuthorityV2
    assert hiob_contracts.StoryboardDraftV1 is StoryboardDraftV1
    assert {
        "FactoryPaidBudgetAuthority",
        "FactoryPaidBudgetAuthorityV2",
        "FactoryPaidBudgetApprovalReceiptV2",
        "StoryboardImageArtifactRef",
        "StoryboardImageSetReceipt",
        "StoryboardDraft",
        "StoryboardApprovalReceipt",
        "StoryboardExecutionManifest",
    }.issubset(registered_contracts())

    authority_result = validate_payload(
        "FactoryPaidBudgetAuthorityV2", _authority("storyboard_draft")
    )
    assert authority_result.ok is True
    assert isinstance(authority_result.obj, FactoryPaidBudgetAuthorityV2)

    image_set = _image_set()
    draft = _draft(image_set)
    draft_result = validate_payload("StoryboardDraft", draft.model_dump(mode="json"))
    assert draft_result.ok is True
    assert isinstance(draft_result.obj, StoryboardDraftV1)


def test_digest_derivations_use_exact_top_level_exclusion_only() -> None:
    image = _image(0)
    assert image["artifact_digest"] == image["sha256"]
    assert derive_storyboard_image_artifact_digest_v1(image) == image["sha256"]

    authority = _authority("storyboard_regen", image_source_beat_indices=[2, 7])
    assert authority["authority_digest"] == canonical_contract_digest_v1(
        authority, exclude={"authority_digest"}
    )

    changed = deepcopy(authority)
    changed["purpose"] = "final_production"
    assert (
        derive_factory_paid_budget_authority_digest_v2(changed)
        != authority["authority_digest"]
    )


def test_all_new_wire_models_forbid_unknown_preview_or_provider_fields() -> None:
    image = _image(0)
    image["preview_url"] = "https://signed.example/image.webp?token=secret"
    with pytest.raises(ValidationError, match="extra"):
        StoryboardImageArtifactRefV1.model_validate(image)

    selected = {
        "artifact_id": "image-1",
        "artifact_digest": sha256_digest({"image": 1}),
        "storage_key": "must-not-cross-browser-boundary.webp",
    }
    with pytest.raises(ValidationError, match="extra"):
        StoryboardSelectedArtifactV1.model_validate(selected)
