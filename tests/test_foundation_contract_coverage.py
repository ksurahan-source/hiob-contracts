from __future__ import annotations

from hiob_contracts.audio_clip import AudioClip
from hiob_contracts.beat_plan import Beat, BeatPlan
from hiob_contracts.composition_snapshot import CompositionSnapshot
from hiob_contracts.cut_contract import ClipEdit, RhythmSuggestion
from hiob_contracts.dossier_contract import (
    dossier_brief_block,
    normalize_dossier,
    normalize_evidence_item,
)
from hiob_contracts.gate import assert_render_ready
from hiob_contracts.locale_pack import resolve_locale_pack
from hiob_contracts.media_artifact import MediaArtifact
from hiob_contracts.reel_metric import ReelMetric
from hiob_contracts.script_contract import (
    AnchorVocPost,
    BeatDirection,
    HookLogic,
    TargetGrounding,
    TrustSlots,
    story_function_counts,
)


def test_cut_contract_builds_atomic_patch_and_suggestion() -> None:
    empty = ClipEdit()
    assert empty.to_patch() == {}

    edit = ClipEdit(
        clip_id="clip-1",
        start_ms=10,
        duration_ms=20,
        in_ms=30,
        split_at_ms=40,
    )
    assert edit.to_patch() == {"start_ms": 10, "duration_ms": 20, "in_ms": 30}

    defaulted = RhythmSuggestion.from_dict(None)
    assert defaulted.confidence == 0.5
    suggestion = RhythmSuggestion.from_dict(
        {
            "id": 7,
            "kind": "pace",
            "title": "Tighten hook",
            "reason": "silence",
            "delta_ms": "-20",
            "confidence": "0.8",
            "edits": [
                None,
                {
                    "clip_id": 9,
                    "start_ms": 10,
                    "duration_ms": 20,
                    "in_ms": 30,
                    "split_at_ms": 40,
                },
            ],
        }
    )
    assert suggestion.id == "7"
    assert suggestion.delta_ms == -20
    assert suggestion.confidence == 0.8
    assert suggestion.edits == [
        ClipEdit(
            clip_id="9",
            start_ms=10,
            duration_ms=20,
            in_ms=30,
            split_at_ms=40,
        )
    ]


def test_dossier_normalization_preserves_evidence_and_flags_drift() -> None:
    assert normalize_evidence_item(None) == {}  # type: ignore[arg-type]
    ungrounded = normalize_evidence_item(
        {"claim": "  claim  ", "sources": "invalid", "source_refs": [None, "ref"]}
    )
    assert ungrounded["confirmed_count"] == 0
    assert ungrounded["source_refs"] == ["ref"]

    item = normalize_evidence_item(
        {
            "claim": "  verified claim  ",
            "role": "review",
            "sources": {"intake": 1, "sales_page": True},
            "source_refs": ["r1", "r2"],
            "asset_key": 12,
            "custom": "kept",
        }
    )
    assert item["claim"] == "verified claim"
    assert item["confirmed_count"] == 2
    assert item["contradiction"] is True
    assert item["asset_key"] == "12"
    assert item["custom"] == "kept"

    assert normalize_dossier(None)["evidence"] == []  # type: ignore[arg-type]
    dossier = normalize_dossier(
        {
            "evidence": [{"claim": ""}, item, "ignored"],
            "tone": {"voice": "  calm  ", "basis": " proof ", "pace": "fast"},
            "corpus": {"source": "approved"},
        }
    )
    assert dossier["version"] == 1
    assert dossier["contradiction_count"] == 1
    assert dossier["tone"] == {"voice": "calm", "basis": "proof", "pace": "fast"}
    assert dossier["corpus"] == {"source": "approved"}
    assert normalize_dossier({"tone": "bad", "corpus": "bad"})["corpus"] == {}

    assert dossier_brief_block({}) == ""
    assert dossier_brief_block(None) == ""  # type: ignore[arg-type]
    block = dossier_brief_block(dossier)
    assert "verified claim" in block
    assert "⚠️모순" in block
    assert "calm" in block


def test_script_contract_helpers_cover_grounded_and_empty_inputs() -> None:
    assert AnchorVocPost.from_dict(None).is_grounded is False
    anchor = AnchorVocPost.from_dict({"quote": " real ", "source": 2, "why": 3})
    assert anchor.is_grounded is True
    assert anchor.source == "2"

    empty_target = TargetGrounding.from_dict(None)
    assert empty_target.missing_fields() == ["who", "where", "moment", "failure", "why"]
    target = TargetGrounding.from_dict(
        {"who": "w", "where": "x", "moment": "y", "failure": "z", "why": "q"}
    )
    assert target.missing_fields() == []

    assert HookLogic.from_dict(None).grade == ""
    hook = HookLogic.from_dict(
        {
            "stop_reason": 1,
            "pain_mirror": 2,
            "trauma_grade": " b - sensory",
            "register": "분노 — 방치된 문제",
        }
    )
    assert hook.grade == "B"
    assert hook.register_name == "분노"
    assert HookLogic(trauma_grade="Z", register="neutral").register_name == ""

    assert BeatDirection.from_dict(None) == BeatDirection()
    assert BeatDirection.from_dict(
        {"setting": 1, "shot": 2, "subject": 3, "overlay": 4}
    ) == BeatDirection(setting="1", shot="2", subject="3", overlay="4")
    assert TrustSlots.from_dict(None) == TrustSlots()
    assert TrustSlots.from_dict({"brand_why": 1, "b2b_proof": 2}) == TrustSlots(
        brand_why="1", b2b_proof="2"
    )
    assert story_function_counts(None) == {}
    assert story_function_counts(
        [None, {}, {"story_function": " 훅 "}, {"story_function": "훅"}]
    ) == {"훅": 2}


def test_render_gate_reports_empty_invalid_and_optional_lanes() -> None:
    empty = assert_render_ready(BeatPlan(), [], [])
    assert empty.ok is False
    assert empty.violations == ("BeatPlan에 비트 0개",)

    plan = BeatPlan(
        beats=(
            Beat(beat_index=0, caption="caption"),
            Beat(beat_index=1, caption=" "),
        )
    )
    audio = [
        AudioClip(track="voice", beat_index=0, storage_key="voice"),
        AudioClip(track="invalid", beat_index=None),  # type: ignore[arg-type]
    ]
    media = [
        MediaArtifact(kind="still", beat_index=0, storage_key="still"),
        MediaArtifact(kind="invalid", beat_index=1),  # type: ignore[arg-type]
    ]
    blocked = assert_render_ready(plan, audio, media)
    assert blocked.ok is False
    assert any("P1 보이스 없는 비트 [1]" in item for item in blocked.violations)
    assert any("audio invalid" in item for item in blocked.violations)
    assert any("media @1" in item for item in blocked.violations)
    assert blocked.warnings == (
        "P13 자막 없는 비트 [1] (dead air 위험)",
        "음악 트랙 없음",
    )
    missing_media = assert_render_ready(
        plan,
        [
            AudioClip(track="voice", beat_index=0, storage_key="a"),
            AudioClip(track="voice", beat_index=1, storage_key="b"),
        ],
        [],
    )
    assert "비주얼 없는 비트 [0, 1]" in missing_media.violations

    optional = assert_render_ready(
        plan,
        [AudioClip(track="music", beat_index=None, storage_key="music")],
        [
            MediaArtifact(kind="still", beat_index=0, storage_key="a"),
            MediaArtifact(kind="still", beat_index=1, storage_key="b"),
        ],
        require_voice_per_beat=False,
        require_caption_per_beat=False,
    )
    assert optional.ok is True
    assert optional.warnings == ()


def test_composition_snapshot_validates_and_round_trips() -> None:
    invalid = CompositionSnapshot(run_id="", render_status="unknown")
    assert invalid.validate() == ["run_id 없음", "render_status 미지원: unknown"]
    rendering = CompositionSnapshot(run_id="run", render_status="rendering")
    assert rendering.validate() == ["gate_passed=False인데 렌더 진행 (invariant 미증명)"]
    completed = CompositionSnapshot(run_id="run", render_status="completed")
    assert completed.validate() == [
        "gate_passed=False인데 렌더 진행 (invariant 미증명)",
        "completed인데 output_url 없음 (WS06 배송 다리 끊김)",
    ]

    row = {
        "run": "run",
        "selection": {"slot": "artifact"},
        "render_status": "completed",
        "attributes": {"output_url": "https://cdn.example/video.mp4", "gate_passed": 1},
        "preview_artifact_id": "preview",
        "final_artifact_id": "final",
        "share_token": "share",
        "rendered_at": "2026-08-20T00:00:00Z",
    }
    snapshot = CompositionSnapshot.from_row(row)
    assert snapshot.validate() == []
    assert CompositionSnapshot.from_dict(snapshot.to_dict()) == snapshot
    assert CompositionSnapshot.from_dict(None).run_id == ""


def test_media_artifact_maps_storage_and_validation_paths() -> None:
    invalid = MediaArtifact(kind="unknown", beat_index=None)  # type: ignore[arg-type]
    assert invalid.validate() == [
        "kind 미지원: unknown",
        "beat_index 없음",
        "url/storage_key 없음",
    ]
    artifact = MediaArtifact.from_slot_artifact(
        {"beat_index": 3},
        {
            "mime": "video/mp4",
            "url": "https://cdn.example/video.mp4",
            "storage_key": "video",
            "duration_ms": 1000,
            "width": 1080,
            "height": 1920,
            "attributes": {"kind": "avatar", "persona_visual_style": "real"},
        },
    )
    assert artifact.kind == "avatar"
    assert artifact.style == "real"
    assert artifact.validate() == []
    assert MediaArtifact.from_dict(artifact.to_dict()) == artifact
    assert MediaArtifact.from_slot_artifact({"beat_index": 0}, None).kind == "still"
    assert MediaArtifact.from_dict(None).beat_index == 0


def test_reel_metric_derives_only_grounded_rates_and_round_trips() -> None:
    empty = ReelMetric.from_dict(None)
    assert empty.roas is None
    assert empty.ctr is None
    assert empty.validate() == ["brand_slug 없음", "run_id 없음"]

    metric = ReelMetric.from_row(
        {
            "brand_slug": "viewok",
            "run_id": "run",
            "source": "meta",
            "metric_date": "2026-08-20",
            "utm_content": "hook-a",
            "impressions": "100",
            "clicks": "25",
            "spend_krw": "20",
            "thruplays": "10",
            "leads": "2",
            "purchases": "1",
            "revenue_krw": "50",
        }
    )
    assert metric.roas == 2.5
    assert metric.ctr == 0.25
    assert metric.validate() == []
    assert ReelMetric.from_dict(metric.to_dict()) == metric


def test_locale_resolution_preserves_priority_and_unknown_fallback() -> None:
    assert resolve_locale_pack(None) is None
    assert resolve_locale_pack({"locale": " EN_us "}).code == "en"  # type: ignore[union-attr]
    assert resolve_locale_pack(
        {"locale": "unknown", "language": "ko"},
        {"language": "en"},
    ).code == "ko"  # type: ignore[union-attr]
    assert resolve_locale_pack({}, {"language": "english"}).code == "en"  # type: ignore[union-attr]
    assert resolve_locale_pack({"lang": "kor"}).code == "ko"  # type: ignore[union-attr]
    assert resolve_locale_pack({}, {}, {"language": "eng"}).code == "en"  # type: ignore[union-attr]
    assert resolve_locale_pack({"language": "unknown"}, {}, {"language": "unknown"}) is None
