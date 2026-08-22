"""Current storyboard lifecycle contracts seal tenant and approved-draft lineage."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

import hiob_contracts
from hiob_contracts import (
    FactoryStoryboardCarrierV1,
    FactoryStoryboardCarrierV2,
    StarReelsViewV3,
)
from tests.test_star_reels_view_v3 import (
    DIGEST_A,
    DIGEST_B,
    DIGEST_C,
    DIGEST_D,
    RUN_ID,
    WORKSPACE_ID,
    _storyboard_review_view,
)
from tests.test_storyboard_two_stage_v1 import (
    DRAFT_ID,
    _phase_a_v2_completion_fixture,
    _valid_final_storyboard_chain,
)


def _scoped_carrier(*, approved: bool = False, executable: bool = False) -> dict:
    return {
        "contract_version": "FactoryStoryboardCarrier.v2",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 7,
        "plan_digest": DIGEST_C,
        "storyboard_draft_id": DRAFT_ID,
        "storyboard_revision": 2,
        "storyboard_digest": DIGEST_B,
        "image_set_receipt_digest": DIGEST_C,
        "approval_receipt_digest": DIGEST_D if approved else None,
        "execution_manifest_digest": DIGEST_A if executable else None,
    }


def test_v1_remains_exact_historical_shape_and_v2_requires_every_scope_field() -> None:
    historical = {
        "contract_version": "FactoryStoryboardCarrier.v1",
        "storyboard_revision": 2,
        "storyboard_digest": DIGEST_B,
        "image_set_receipt_digest": DIGEST_C,
        "approval_receipt_digest": None,
        "execution_manifest_digest": None,
    }
    assert FactoryStoryboardCarrierV1.model_validate(historical).model_dump(
        mode="json"
    ) == historical
    with pytest.raises(ValidationError, match="Extra inputs"):
        FactoryStoryboardCarrierV1.model_validate(
            {**historical, "workspace_id": WORKSPACE_ID}
        )

    scoped = FactoryStoryboardCarrierV2.model_validate(_scoped_carrier())
    assert scoped.storyboard_draft_id == DRAFT_ID
    for field in (
        "workspace_id",
        "run_id",
        "factory_revision",
        "plan_digest",
        "storyboard_draft_id",
    ):
        missing = _scoped_carrier()
        missing.pop(field)
        with pytest.raises(ValidationError, match="Field required"):
            FactoryStoryboardCarrierV2.model_validate(missing)


def test_phase_a_v2_completion_and_summary_seal_scoped_draft_and_voice() -> None:
    completion, resolution, image_proofs, voice_proofs = (
        _phase_a_v2_completion_fixture()
    )

    assert isinstance(completion.output_storyboard_carrier, FactoryStoryboardCarrierV2)
    carrier = completion.output_storyboard_carrier
    assert carrier.workspace_id == completion.workspace_id
    assert carrier.run_id == completion.run_id
    assert carrier.factory_revision == completion.factory_revision
    assert carrier.plan_digest == completion.plan_digest
    assert carrier.storyboard_draft_id == completion.output_storyboard_draft.draft_id

    summary = hiob_contracts.StoryboardPhaseACompletionSummaryV2.from_completion(
        completion,
        authority=resolution,
        image_operation_proofs=image_proofs,
        voice_operation_proofs=voice_proofs,
    )
    assert summary.output_storyboard_draft_id == carrier.storyboard_draft_id
    assert summary.voice_count == 16
    assert summary.voice_evidence_set_digest == completion.voice_evidence_set_digest

    alien = completion.model_dump(mode="json")
    alien["output_storyboard_carrier"]["workspace_id"] = (
        "00000000-0000-4000-8000-000000000099"
    )
    alien["receipt_digest"] = (
        hiob_contracts.derive_storyboard_phase_a_completion_receipt_digest_v2(alien)
    )
    with pytest.raises(ValidationError, match="carrier|scope|storyboard"):
        hiob_contracts.StoryboardPhaseACompletionReceiptV2.model_validate(alien)


def test_current_v3_accepts_v2_carrier_and_rejects_v1_or_alien_scope() -> None:
    payload = _storyboard_review_view()
    assert payload["storyboard"]["contract_version"] == "FactoryStoryboardCarrier.v2"
    value = StarReelsViewV3.model_validate(payload)
    assert isinstance(value.storyboard, FactoryStoryboardCarrierV2)

    historical = {
        "contract_version": "FactoryStoryboardCarrier.v1",
        "storyboard_revision": 2,
        "storyboard_digest": DIGEST_B,
        "image_set_receipt_digest": DIGEST_C,
        "approval_receipt_digest": None,
        "execution_manifest_digest": None,
    }
    legacy_current = deepcopy(payload)
    legacy_current["storyboard"] = historical
    legacy_current["stage_output"] = historical
    with pytest.raises(ValidationError, match="FactoryStoryboardCarrier.v2|storyboard"):
        StarReelsViewV3.model_validate(legacy_current)

    alien = deepcopy(payload)
    alien["storyboard"]["workspace_id"] = (
        "00000000-0000-4000-8000-000000000099"
    )
    alien["stage_output"] = alien["storyboard"]
    with pytest.raises(ValidationError, match="scope|authority"):
        StarReelsViewV3.model_validate(alien)


def test_scene_and_factory_summaries_carry_exact_approved_draft_lineage() -> None:
    chain = _valid_final_storyboard_chain()
    manifest = chain["manifest"]
    scene = chain["scene_summary"]
    factory = chain["completion_summary"]

    for summary in (scene, factory):
        assert summary.storyboard_draft_id == manifest.draft_id
        assert summary.storyboard_draft_revision == manifest.draft_revision
        assert summary.storyboard_draft_digest == manifest.storyboard_draft_digest
        assert summary.image_set_receipt_digest == manifest.image_set_receipt_digest
        assert (
            summary.storyboard_approval_receipt_digest
            == manifest.storyboard_approval_receipt_digest
        )
