"""Exercise the final fail-open and successful-exit contract branches."""

from __future__ import annotations

from types import SimpleNamespace

import hiob_contracts.ares_create_script_v2 as ares_v2
import hiob_contracts.ares_script_revision_v1 as revision_v1
import hiob_contracts.element_locks as element_locks
import hiob_contracts.janus_story_product_record_v4 as janus_v4
import hiob_contracts.parzifal_master_sheet as master_sheet
import hiob_contracts.star_reels_view_v1 as star_view
import hiob_contracts.storyboard_two_stage_v1 as storyboard
from hiob_contracts.audio_clip import AudioClip
from hiob_contracts.beat_plan import Beat, BeatPlan
from hiob_contracts.decision_callable import DecisionContext
from hiob_contracts.dossier_contract import dossier_brief_block
from hiob_contracts.edge_target_inputs import HephaestusRenderInput
from hiob_contracts.element_lock_v3 import ElementLockPackageV1
from hiob_contracts.factory.planet_output import ArtifactRef
from hiob_contracts.factory.state import FactoryState, assert_transition
from hiob_contracts.gate import assert_render_ready
from hiob_contracts.identity_qa_fields import attach_identity_qa
from hiob_contracts.media_artifact import MediaArtifact
from hiob_contracts.overnight_first_customer_v1 import sha256_hex
from hiob_contracts.planet_envelopes import VisualRequest
from hiob_contracts.provenance import claim_with_provenance
from hiob_contracts.timeline_v2_payload import (
    build_timeline_v2_payload,
    normalize_render_dispatch_url,
)
from hiob_contracts.visual_materialization import VisualMaterializationReceiptV1


DIGEST = "sha256:" + "a" * 64


def test_ares_optional_collections_take_the_empty_success_paths(monkeypatch) -> None:
    evidence = ares_v2.AresEvidenceAndClaimsSealedV2.model_construct(
        claims=(),
        allowed_claim_ids=(),
    )
    assert evidence._claim_ids_consistent() is evidence

    plan = ares_v2.BeatPlanV2.model_construct(
        beats=(SimpleNamespace(beat_index=0),),
        beat_role_intents=(),
        plan_digest=DIGEST,
    )
    monkeypatch.setattr(
        ares_v2,
        "canonical_contract_digest_v1",
        lambda *_args, **_kwargs: DIGEST,
    )
    assert plan._bind_content() is plan

    assert (
        revision_v1.ScriptPackageV1._reject_normalized_pronunciation_key_collisions(
            []
        )
        == []
    )


def test_small_contracts_take_empty_and_bytes_branches() -> None:
    assert Beat(beat_index=0, scene_direction={}).to_dict()["scene_direction"] == {}
    assert DecisionContext(stage="ares", decision="hook").to_prompt_context() == (
        "[결정] stage=ares decision=hook"
    )
    assert "확정 톤앤매너" not in dossier_brief_block(
        {
            "evidence": [{"role": "proof", "claim": "verified", "sources": {}}],
            "tone": {},
        }
    )
    assert HephaestusRenderInput(
        run_id="run-1",
        snapshot="invalid",  # type: ignore[arg-type]
        mode="preview",
    ).validate() == [
        "HephaestusRenderInput.snapshot 필수 (CompositionSnapshot-like)"
    ]
    assert attach_identity_qa({"id": "panel"}) == {"id": "panel"}
    assert sha256_hex(b"bytes") == sha256_hex("bytes")
    assert claim_with_provenance("claim").provenance is None


def test_failed_element_package_skips_review_only_requirements() -> None:
    package = ElementLockPackageV1.build(
        lock_id="lock-1",
        version=1,
        operation_id="operation-1",
        workspace_id="workspace-1",
        run_id="run-1",
        subject_id="subject-1",
        status="failed",
    )
    assert package.status == "failed"


def test_element_lock_empty_components_and_mixed_character_rows() -> None:
    character = element_locks.CharacterLock(persona_id="hero", wardrobe={})
    assert element_locks._character_constraint_parts(character) == []
    assert element_locks._product_constraint_parts(element_locks.ProductLock()) == []

    locks = element_locks.ElementLocks(
        status="approved",
        workspace_id="workspace-1",
        brand_slug="brand-1",
        characters={"raw": object(), "hero": character},
        product=element_locks.ProductLock(),
        background=element_locks.BackgroundLock(),
    )
    assert locks.approved_refs(
        "hero", workspace_id="workspace-1", brand_slug="brand-1"
    ) == []
    assert (
        locks.constraint_prompt(
            "hero", workspace_id="workspace-1", brand_slug="brand-1"
        )
        == ""
    )
    assert any("히어로" in error for error in locks.validate())


def test_factory_successful_lineage_and_transition_paths() -> None:
    artifact = ArtifactRef.model_construct(
        sha256=DIGEST,
        image_digest=None,
        source_output_digests=(DIGEST,),
        edge_receipt_digests=(),
    )
    assert artifact._check_digests() is artifact
    assert_transition(FactoryState.CREATED, FactoryState.FAILED)


def test_render_gate_with_complete_caption_coverage() -> None:
    plan = BeatPlan(beats=(Beat(beat_index=0, caption="caption"),))
    readiness = assert_render_ready(
        plan,
        [
            AudioClip(track="voice", beat_index=0, storage_key="voice"),
            AudioClip(track="music", beat_index=None, storage_key="music"),
        ],
        [MediaArtifact(kind="still", beat_index=0, storage_key="still")],
    )
    assert readiness.ok is True
    assert readiness.warnings == ()


def test_janus_exact_reference_match_completes_the_field_loop() -> None:
    values = {field: f"value-{index}" for index, field in enumerate(janus_v4._RECORD_REF_MATCH_FIELDS)}
    janus_v4.assert_janus_story_product_record_ref_matches_v4(
        record=SimpleNamespace(**values),  # type: ignore[arg-type]
        record_ref=SimpleNamespace(**values),  # type: ignore[arg-type]
    )


def test_parzifal_empty_and_fallback_paths() -> None:
    no_image = master_sheet.SheetPanel(slot="angle", label="side")
    image = master_sheet.SheetPanel(
        slot="angle", label="three-quarter", storage_key="image.png"
    )
    assert len(master_sheet._panels([{"storage_key": "one"}, {"storage_key": "two"}])) == 2
    assert master_sheet._panels([object()]) == []

    character = master_sheet.CharacterMasterSheet(
        persona_id="hero",
        angles=[no_image, image],
    )
    assert character.hero_panel() is image
    product = master_sheet.ProductMasterSheet(angles=[no_image, image])
    assert product.hero_panel() is image

    empty_character = master_sheet.CharacterMasterSheet(persona_id="empty")
    approved = master_sheet.ParzifalMasterSheet(
        status="approved",
        characters={"empty": empty_character},
        product=master_sheet.ProductMasterSheet(),
        background={},
    )
    assert approved.approved_refs("empty") == []
    assert approved.constraint_prompt("empty") == ""

    no_components = master_sheet.ParzifalMasterSheet(
        status="approved",
        characters={},
        product=None,
        background=None,  # type: ignore[arg-type]
    )
    assert no_components.approved_refs("missing") == []
    assert no_components.to_element_locks().background is None

    raw_background = master_sheet.ParzifalMasterSheet(
        status="draft",
        characters={},
        background={"ref": {}},
    )
    assert raw_background.to_element_locks().background is not None

    two_characters = master_sheet.ParzifalMasterSheet(
        status="draft",
        characters={
            "raw": object(),
            "one": master_sheet.CharacterMasterSheet(persona_id="one"),
            "two": master_sheet.CharacterMasterSheet(persona_id="two"),
        },
    )
    assert two_characters.validate() == []


def test_visual_request_without_validator_is_accepted() -> None:
    request = VisualRequest(beat_plan=object())  # type: ignore[arg-type]
    assert request.validate() == []


def test_star_legacy_gate_accepts_a_v3_factory_receipt() -> None:
    view = star_view.StarReelsViewV3.model_construct(
        budget=SimpleNamespace(purpose="storyboard_draft"),
        storyboard=None,
        section="ScriptReview",
        stage_output={"script": "ready"},
        review_digest=DIGEST,
        provider_call="confirmed",
        error=None,
        receipts=SimpleNamespace(
            factory=star_view.ReelsFactoryProgressReceiptV3.model_construct()
        ),
    )
    assert view._bind_legacy_gate() is None


def test_historical_render_scope_accepts_final_production() -> None:
    evidence = storyboard.FactoryPaidOperationHistoricalEvidenceV2.model_construct(
        operation="render",
        source_index=None,
    )
    evidence._bind_historical_operation_scope(
        SimpleNamespace(purpose="final_production")  # type: ignore[arg-type]
    )


def test_timeline_and_materialization_optional_paths() -> None:
    assert normalize_render_dispatch_url("https:renderer") == "https:renderer/v1/render"
    payload = build_timeline_v2_payload(
        snapshot_id="snapshot-1",
        run_id="run-1",
        input_props={},
        callback_url="   ",
    )
    assert "callback_url" not in payload

    receipt = VisualMaterializationReceiptV1(
        idempotency_key=DIGEST,
        plan_digest=DIGEST,
        status="planned",
        requested_provider="provider",
        requested_model="model",
        resolved_provider="provider",
        resolved_model="model",
    )
    assert receipt.validate() == []
