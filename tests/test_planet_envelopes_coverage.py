from __future__ import annotations

from hiob_contracts.beat_personas import BeatPersona, BeatPersonas
from hiob_contracts.beat_plan import BeatPlan
from hiob_contracts.planet_envelopes import (
    AudioRequest,
    ProcessInsightsRequest,
    RenderJobRequest,
    RenderJobResponse,
    SFXRequest,
    VisualContext,
    VisualRequest,
    _visual_beat_personas,
    _visual_beat_plan,
    _visual_context,
)


def test_visual_envelope_helpers_accept_typed_and_wire_shapes() -> None:
    context = VisualContext(
        visual_style="real",
        ethnicity="Korean",
        listing_environment_lock="pool",
        vertical_style_lock="9:16",
        axis_gaze_lock="neutral",
        product_present=True,
    )
    assert context.validate() == []
    assert VisualContext.from_dict(context.to_dict()) == context
    assert VisualContext.from_dict(None) == VisualContext()

    plan = BeatPlan.from_list([{"beat_index": 0, "text": "hook"}])
    assert _visual_beat_plan(plan) is plan
    assert _visual_beat_plan([{"beat_index": 1}]).beats[0].beat_index == 1
    assert _visual_beat_plan({"spine": "one", "beats": [{"beat_index": 2}]}).spine == "one"
    assert _visual_beat_plan("invalid").beats == ()
    assert _visual_context(context) is context
    assert _visual_context({"visual_style": "art"}).visual_style == "art"
    assert _visual_context("invalid") == VisualContext()

    personas = BeatPersonas.from_list([{"beat_index": 0, "role": "hero"}])
    assert _visual_beat_personas(personas) is personas
    assert _visual_beat_personas([{"beat_index": 1}]).personas[0].beat_index == 1
    assert _visual_beat_personas({"items": [{"beat_index": 2}]}).personas[0].beat_index == 2
    assert _visual_beat_personas({"unknown": []}) == BeatPersonas()


def test_visual_request_validates_required_and_nested_plan() -> None:
    missing = VisualRequest(beat_plan=None)  # type: ignore[arg-type]
    assert missing.validate() == ["VisualRequest.beat_plan 필수"]

    duplicate = VisualRequest(
        beat_plan=BeatPlan.from_list([{"beat_index": 0}, {"beat_index": 0}])
    )
    assert duplicate.validate() == ["beat_index 중복", "beat_index 연속성 깨짐(구멍)"]
    request = VisualRequest.from_dict(
        {
            "beat_plan": {"spine": "spine", "beats": [{"beat_index": 0}]},
            "context": {"product_present": True},
            "beat_personas": {"items": [{"beat_index": 0, "role": "hero"}]},
            "element_locks": {"status": "approved"},
        }
    )
    assert request.validate() == []
    assert request.context.product_present is True
    assert request.beat_personas.personas == (BeatPersona(beat_index=0, role="hero"),)
    assert request.element_locks == {"status": "approved"}
    assert VisualRequest.from_dict(None).beat_plan.beats == ()


def test_audio_and_sfx_envelopes_validate_and_round_trip() -> None:
    assert AudioRequest().validate() == [
        "AudioRequest: voice 또는 music 필드 최소 1개 필요"
    ]
    audio = AudioRequest.from_dict(
        {
            "voice_persona": "female1",
            "voice_concept": "calm",
            "source_text": "line",
            "beat_index": "2",
            "music_vibe": "warm",
            "music_bpm": "90",
            "music_pool": [{"storage_key": "music"}],
            "target_ms": "12000",
        }
    )
    assert audio.validate() == []
    assert AudioRequest.from_dict(audio.to_dict()) == audio
    assert AudioRequest.from_dict({"music_pool": "invalid"}).music_pool == ()

    malformed = SFXRequest(cues="invalid")  # type: ignore[arg-type]
    assert malformed.validate() == ["SFXRequest.cues must be a list/tuple"]
    sfx = SFXRequest(
        cues=(None, {}, {"text": "splash"}),  # type: ignore[arg-type]
        asset_pool=({"storage_key": "sfx"},),
        shot_list_digest="sha256:digest",
    )
    assert sfx.validate() == [
        "SFXRequest.cues[0] must be a dict",
        "SFXRequest.cues[1]: beat_index 또는 text/cue 필요",
    ]
    assert SFXRequest.from_dict(sfx.to_dict()) == sfx
    assert SFXRequest.from_dict({"cues": "bad", "asset_pool": "bad"}) == SFXRequest()


def test_render_job_envelopes_fail_closed_and_preserve_zero_duration() -> None:
    blocked = RenderJobRequest(render_job_id="", run_id="")
    assert blocked.validate() == [
        "RenderJobRequest.render_job_id 필수",
        "RenderJobRequest.run_id 필수",
        "RenderJobRequest: mode=final 이면 approved_final_render 필수",
    ]
    assert blocked.to_dispatch()["gated"] is True

    approved = RenderJobRequest.from_dict(
        {
            "renderJobId": "job",
            "runId": "run",
            "composition": "timelineV2",
            "mode": "final",
            "approvedFinalRender": True,
            "modifications": {"caption": "larger"},
        }
    )
    assert approved.validate() == []
    assert approved.to_dispatch()["approvedFinalRender"] is True
    assert RenderJobRequest.from_dict(approved.to_dict()) == approved

    invalid_response = RenderJobResponse(
        render_job_id="", snapshot_id="", render_status="completed"
    )
    assert invalid_response.validate() == [
        "RenderJobResponse.render_job_id 필수",
        "RenderJobResponse: completed인데 output_url 없음",
    ]
    success = RenderJobResponse.from_render_result(
        "job",
        {
            "snapshotId": "snapshot",
            "outputUrl": "https://cdn.example/final.mp4",
            "duration_s": 0.0,
        },
    )
    assert success.render_status == "completed"
    assert success.duration_s == 0.0
    assert success.validate() == []
    assert RenderJobResponse.from_dict(success.to_dict()) == success

    failure = RenderJobResponse.from_render_result(
        "job", {"snapshot_id": "snapshot", "error": "renderer failed", "durationS": 2}
    )
    assert failure.render_status == "failed"
    assert failure.error == {"reason": "renderer failed"}
    assert failure.duration_s == 2
    assert RenderJobResponse.from_dict(None).render_job_id == ""


def test_process_insights_request_validates_direct_and_wire_inputs() -> None:
    invalid = ProcessInsightsRequest(
        raw_insights="bad",  # type: ignore[arg-type]
        run_brand_map="bad",  # type: ignore[arg-type]
        window_days=0,
    )
    assert invalid.validate() == [
        "ProcessInsightsRequest.window_days must be > 0",
        "ProcessInsightsRequest.raw_insights must be a list/tuple",
        "ProcessInsightsRequest.run_brand_map must be a dict",
    ]
    request = ProcessInsightsRequest.from_dict(
        {
            "raw_insights": [{"run_id": "run"}],
            "run_brand_map": {"run": "viewok"},
            "window_days": "14",
        }
    )
    assert request.validate() == []
    assert ProcessInsightsRequest.from_dict(request.to_dict()) == request
    assert ProcessInsightsRequest.from_dict({"raw_insights": "bad"}).raw_insights == ()
    assert ProcessInsightsRequest.from_dict(None).window_days == 30
