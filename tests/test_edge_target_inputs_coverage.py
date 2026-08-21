"""Behavioral coverage for every residual edge target input."""

from hiob_contracts.edge_target_inputs import (
    ApolloPlanInput,
    ArtemisReviewInput,
    AthenaPlanInput,
    AtroposApplyInput,
    AtroposDraftInput,
    CAPIEvent,
    CAPIPayload,
    HephaestusRenderInput,
    OrpheusPlanInput,
)


def test_athena_input_normalizes_and_rejects_invalid_plans() -> None:
    assert AthenaPlanInput(beat_plan=[]).validate() == [
        "AthenaPlanInput.beat_plan must be a dict"
    ]
    assert "필수" in AthenaPlanInput().validate()[0]
    assert "must be a list" in AthenaPlanInput(
        beat_plan={"beats": "invalid"}
    ).validate()[0]

    listed = AthenaPlanInput.from_dict({"beat_plan": [{"beat_index": 0}]})
    assert listed.to_dict()["beat_plan"] == {"beats": [{"beat_index": 0}]}
    assert AthenaPlanInput.from_dict({"beat_plan": "invalid"}).beat_plan == {}


def test_orpheus_and_apollo_inputs_cover_voice_music_and_cue_errors() -> None:
    errors = OrpheusPlanInput(target_ms=-1, music_bpm=-1).validate()
    assert any("target_ms" in error for error in errors)
    assert any("music_bpm" in error for error in errors)

    orpheus = OrpheusPlanInput.from_dict(
        {
            "music_pool": [{"artifact_id": "music-1"}],
            "beat_index": 2,
            "voice_persona": "warm",
        }
    )
    assert orpheus.to_dict()["music_pool"] == ({"artifact_id": "music-1"},)

    assert ApolloPlanInput(cues="invalid").validate() == [
        "ApolloPlanInput.cues must be a list/tuple"
    ]
    cue_errors = ApolloPlanInput(cues=("invalid", {})).validate()
    assert any("must be a dict" in error for error in cue_errors)
    assert any("중 하나 필요" in error for error in cue_errors)
    apollo = ApolloPlanInput.from_dict(
        {"cues": [{"cue": "splash"}], "asset_pool": [{"id": "sfx-1"}]}
    )
    assert apollo.validate() == []
    assert apollo.to_dict()["shot_list_digest"] == ""


def test_atropos_draft_and_apply_require_identity_and_material() -> None:
    errors = AtroposDraftInput(run_id="").validate()
    assert any("run_id" in error for error in errors)
    assert any("media" in error for error in errors)

    from_tuple = AtroposDraftInput.from_dict(
        {"run_id": "run-1", "media": ({"id": "m1"},)}
    )
    assert from_tuple.to_dict()["media"] == ({"id": "m1"},)
    from_list = AtroposDraftInput.from_dict(
        {"run_id": "run-1", "media": [{"id": "m2"}]}
    )
    assert from_list.media == ({"id": "m2"},)
    from_scalar = AtroposDraftInput.from_dict(
        {"run_id": "run-1", "audio": {"id": "a1"}}
    )
    assert from_scalar.audio == ({"id": "a1"},)
    assert AtroposDraftInput.from_dict({"run_id": "run-1"}).audio == ()

    apply_errors = AtroposApplyInput(run_id="").validate()
    assert any("run_id" in error for error in apply_errors)
    assert any("accepted_proposals" in error for error in apply_errors)
    applied = AtroposApplyInput.from_dict(
        {"run_id": "run-1", "proposals": {"id": "proposal-1"}}
    )
    assert applied.to_dict()["accepted_proposals"] == ({"id": "proposal-1"},)


def test_sunset_artemis_review_reports_each_invalid_state() -> None:
    errors = ArtemisReviewInput(
        run_id="",
        render_status="unsupported",
    ).validate()
    assert any("run_id" in error for error in errors)
    assert any("미지원" in error for error in errors)

    rendering = ArtemisReviewInput(
        run_id="run-1",
        render_status="rendering",
        gate_passed=False,
    )
    assert any("gate_passed" in error for error in rendering.validate())

    completed = ArtemisReviewInput(
        run_id="run-1",
        render_status="completed",
        gate_passed=True,
    )
    assert any("no output_url" in error for error in completed.validate())
    assert ArtemisReviewInput.from_dict(completed.to_dict()) == completed


def test_hephaestus_input_supports_nested_and_flat_snapshots() -> None:
    errors = HephaestusRenderInput().validate()
    assert any("run_id" in error for error in errors)
    assert any("snapshot" in error for error in errors)
    assert any("approval_receipt_ref" in error for error in errors)

    flat = HephaestusRenderInput.from_dict(
        {
            "run_id": "run-1",
            "selection": {"take": 1},
            "render_status": "completed",
            "gate_passed": True,
            "approval_receipt_ref": "receipt-1",
        }
    )
    assert flat.validate() == []
    assert flat.to_dict()["snapshot"]["selection"] == {"take": 1}
    assert HephaestusRenderInput.from_dict({}).snapshot == {}


def test_capi_event_and_payload_require_dispatch_identity_and_consent() -> None:
    event_errors = CAPIEvent(user_data=[]).validate()
    assert any("event_name" in error for error in event_errors)
    assert any("event_id" in error for error in event_errors)
    assert any("user_data" in error for error in event_errors)

    event = CAPIEvent.from_dict(
        {"event_name": "Purchase", "order_id": "order-1", "user_data": {}}
    )
    assert event.validate() == []
    assert event.to_dict()["event_id"] == "order-1"

    payload_errors = CAPIPayload(pipa_consent=False).validate()
    assert any("install_id" in error for error in payload_errors)
    assert any("event_name" in error for error in payload_errors)
    assert any("event_id" in error for error in payload_errors)
    assert any("pipa_consent" in error for error in payload_errors)

    payload = CAPIPayload.from_dict(
        {
            "install_id": "install-1",
            "event_name": "Purchase",
            "event_id": "event-1",
            "params_sent": ["em", "ph"],
        }
    )
    assert payload.validate() == []
    assert payload.to_dict()["params_sent"] == ("em", "ph")
