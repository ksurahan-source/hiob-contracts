from __future__ import annotations

import builtins
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from hiob_contracts.beat_personas import BeatPersona, BeatPersonas, _safe_int, _s
from hiob_contracts.beat_plan import Beat, BeatPlan
from hiob_contracts.brand_scope import canonical_brand_slug, normalize_unicode_scalars
from hiob_contracts.character_identity_v1 import character_identity_binding_payload_v1
from hiob_contracts.decision_callable import DecisionContext
from hiob_contracts.execution_backend import (
    CancelResult,
    ExecutionBackend,
    JobEnvelope,
    OperationRef,
    OperationStatus,
    RouteSnapshot,
)
from hiob_contracts.factory import (
    ArtifactRef,
    ContractRef,
    DegradationReceipt,
    EdgeViolation,
    KarmaEdgeReceipt,
    MapperRef,
    StageError,
    StageReceipt,
    TransformLogEntry,
    sha256_digest,
)
from hiob_contracts.feedback_signal import FeedbackSignal
from hiob_contracts.heroine import Heroine
from hiob_contracts.identity_qa_fields import panel_with_identity_qa
from hiob_contracts.janus_brief import Intake13Q, JanusBrief
from hiob_contracts.janus_story_product_record_v4 import (
    janus_story_product_record_digest_v4,
)
from hiob_contracts.overnight_first_customer_v1 import (
    CONTRACT_VERSIONS,
    customer_order_key,
    serialize_equal,
    validate_creative_order,
    validate_verified_render_receipt,
)
from hiob_contracts.planet_io import dsl_ready, io_for, needs_new_contract
from hiob_contracts.provenance import (
    ClaimProvenance,
    ProvenancedClaim,
    claim_with_provenance,
    now_observed_at,
    provenance_from_dict,
    provenance_to_dict,
)
from hiob_contracts.shot_list import ShotList, ShotMetadata
from hiob_contracts.six_realm import get_realm_preset, get_sfx_cue_for_emotion
from hiob_contracts.timeline_v2_payload import (
    build_timeline_v2_payload,
    hephaestus_render_node_input,
    normalize_render_dispatch_url,
    stable_snapshot_id,
)


DIGEST = "sha256:" + "a" * 64


def test_beat_persona_helpers_cover_invalid_and_lookup_paths() -> None:
    assert _s(None) is None
    assert _s("   ") is None
    assert _safe_int(None) is None
    assert _safe_int(True) is None
    assert _safe_int(3) == 3
    assert _safe_int(3.0) == 3
    assert _safe_int("bad") is None

    missing = BeatPersona(beat_index=None)  # type: ignore[arg-type]
    wrong_type = BeatPersona(beat_index="1")  # type: ignore[arg-type]
    assert missing.validate() == ["beat_index 없음 (Athena 정렬 결박 필수)"]
    assert wrong_type.validate() == ["beat_index 정수 아님: '1'"]
    assert missing.normalized_render_mode() is None
    custom = BeatPersona(beat_index=1, render_mode=" Custom ")
    assert custom.normalized_render_mode() == "custom"
    assert BeatPersona(beat_index=1, social_proof_style="review").is_social_proof is True

    personas = BeatPersonas.from_list(
        [BeatPersona(beat_index=1), {"beat_index": "1"}, "ignored"]
    )
    assert len(personas) == 2
    assert list(personas) == list(personas.personas)
    assert personas.by_beat(1) is personas.personas[0]
    assert personas.by_beat(99) is None
    assert personas.validate() == ["beat_index 중복 (persona 정렬 붕괴)"]
    assert personas.to_list()[0]["beat_index"] == 1

    assert BeatPlan((Beat(beat_index=0),)).beat_for(99) is None


def test_brand_and_character_identity_reject_ambiguous_text() -> None:
    with pytest.raises(ValueError, match="valid Unicode scalar"):
        normalize_unicode_scalars("\ud800x")
    with pytest.raises(ValueError, match="valid Unicode scalar"):
        normalize_unicode_scalars("\udc00")
    with pytest.raises(ValueError, match="must be text"):
        canonical_brand_slug(3)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="subject_id is required"):
        character_identity_binding_payload_v1(
            subject_id=" ", face_id="face", voice_id="voice"
        )


def test_decision_context_rejects_non_mapping_context_fields() -> None:
    context = DecisionContext(
        stage="",
        decision="",
        beat_index=0,
        brief=[],  # type: ignore[arg-type]
        upstream=[],  # type: ignore[arg-type]
        persona=[],  # type: ignore[arg-type]
    )
    assert context.validate() == [
        "stage 필수",
        "decision 필수",
        "brief는 dict여야 함",
        "upstream는 dict여야 함",
        "persona는 dict여야 함",
    ]
    ordinary = DecisionContext(
        stage="ares",
        decision="emotion",
        beat_index=2,
        brief={"request_interpretation": "invalid"},
        persona={"id": "persona"},
    )
    assert ordinary.is_reel_global is False
    assert ordinary.to_prompt_context() == (
        "[결정] stage=ares decision=emotion · beat_index=2 · persona=persona"
    )


def _job_envelope(**changes: object) -> JobEnvelope:
    body = {
        "operation_id": "operation",
        "job_id": "job",
        "node_id": "voice",
        "contract_version": "v1",
        "workspace_id": "workspace",
        "input_uri": None,
        "output_uri": None,
        "image_digest": DIGEST,
        "idempotency_key": "idem",
        "trace_id": "trace",
        "deadline_at": None,
        "route_snapshot": RouteSnapshot(
            provider="modal",
            target_kind="function",
            target_resource="app.voice",
            artifact_digest=DIGEST,
            spec_digest=DIGEST,
        ),
    }
    body.update(changes)
    return JobEnvelope(**body)  # type: ignore[arg-type]


class _DelegatingBackend(ExecutionBackend):
    def is_configured(self) -> bool:
        return super().is_configured()

    def submit(self, envelope: JobEnvelope) -> OperationRef:
        return super().submit(envelope)

    def status(self, operation_id: str) -> OperationStatus:
        return super().status(operation_id)

    def cancel(self, operation_id: str) -> CancelResult:
        return super().cancel(operation_id)


def test_execution_contract_validates_fields_and_abstract_fallbacks() -> None:
    _job_envelope().validate()
    for invalid in (None, " "):
        with pytest.raises(ValueError, match="missing required field"):
            _job_envelope(operation_id=invalid).validate()

    backend = _DelegatingBackend()
    with pytest.raises(NotImplementedError):
        backend.is_configured()
    with pytest.raises(NotImplementedError):
        backend.submit(_job_envelope())
    with pytest.raises(NotImplementedError):
        backend.status("operation")
    with pytest.raises(NotImplementedError):
        backend.cancel("operation")


def _degradation_body() -> dict[str, object]:
    return {
        "degradation_id": "degradation",
        "run_id": "run",
        "factory_revision": 1,
        "omitted_stage": "music",
        "omitted_artifact_kind": "audio",
        "source_digests": (DIGEST,),
        "plan_digest": DIGEST,
        "user_impact": "music omitted",
        "authorized_by": "founder",
        "recovery_action": "regenerate music",
        "created_at": "2026-08-20T00:00:00Z",
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("plan_digest", "bad", "plan_digest malformed"),
        ("source_digests", ("bad",), "source digest malformed"),
        ("user_impact", " ", "user-visible impact"),
        ("recovery_action", " ", "recovery action"),
        ("authorized_by", " ", "approver"),
    ],
)
def test_degradation_receipt_rejects_unsealed_waiver(
    field: str, value: object, message: str
) -> None:
    body = _degradation_body()
    body[field] = value
    with pytest.raises(ValidationError, match=message):
        DegradationReceipt.model_validate(body)


def _artifact_body() -> dict[str, object]:
    return {
        "artifact_id": "artifact",
        "kind": "image",
        "uri": "r2://artifact",
        "sha256": DIGEST,
        "mime": "image/png",
        "bytes_len": 1,
        "producer_planet": "athena",
        "producer_node_id": "visual",
        "execution_id": "execution",
        "producer_revision": "revision",
    }


def test_artifact_ref_rejects_optional_and_lineage_digest_drift() -> None:
    assert ArtifactRef.model_validate(_artifact_body()).sha256 == DIGEST
    for field, value in (
        ("image_digest", "bad"),
        ("source_output_digests", ("bad",)),
        ("edge_receipt_digests", ("bad",)),
    ):
        body = _artifact_body()
        body[field] = value
        with pytest.raises(ValidationError):
            ArtifactRef.model_validate(body)


def _stage_body() -> dict[str, object]:
    return {
        "operation_id": "operation",
        "stage_id": "stage",
        "planet": "ares",
        "node_id": "script",
        "producer_revision": "revision",
        "contract_version": "v1",
        "input_digests": (DIGEST,),
        "output_digests": (DIGEST,),
        "status": "succeeded",
        "attempt_no": 1,
        "started_at": "2026-08-20T00:00:00Z",
        "completed_at": "2026-08-20T00:00:01Z",
    }


def test_stage_receipt_rejects_unbound_terminal_state() -> None:
    assert StageReceipt.model_validate(_stage_body()).is_success is True
    for changes in (
        {"input_digests": ("bad",)},
        {"completed_at": None},
        {"error": StageError(code="bad", retryable=False)},
    ):
        body = _stage_body()
        body.update(changes)
        with pytest.raises(ValidationError):
            StageReceipt.model_validate(body)


def _karma_receipt_body() -> dict[str, object]:
    target = {"brief": "sealed"}
    return {
        "receipt_id": "receipt",
        "edge_id": "j2p",
        "run_id": "run",
        "factory_revision": 1,
        "workspace_id": "workspace",
        "source_output_digests": (DIGEST,),
        "target_contract": ContractRef(
            name="Target", version="v1", schema_digest=DIGEST
        ),
        "decision": "accepted",
        "target_input": target,
        "target_input_digest": sha256_digest(target),
        "mapper": MapperRef(node_id="mapper", revision="r1", policy_digest=DIGEST),
        "created_at": "2026-08-20T00:00:00Z",
    }


def test_karma_receipt_and_transform_log_reject_digest_and_scope_drift() -> None:
    log = TransformLogEntry(
        op="copy",
        target_path="brief",
        source_paths=("source",),
        rule_id="rule",
        value_digest=DIGEST,
        origin="source",
    )
    assert log.value_digest == DIGEST
    with pytest.raises(ValidationError):
        TransformLogEntry(
            op="copy",
            target_path="brief",
            rule_id="rule",
            value_digest="bad",
            origin="source",
        )

    assert KarmaEdgeReceipt.model_validate(_karma_receipt_body()).decision == "accepted"
    for field, value in (
        ("source_output_digests", ()),
        ("source_output_digests", ("bad",)),
        ("workspace_id", " "),
    ):
        body = _karma_receipt_body()
        body[field] = value
        with pytest.raises(ValidationError):
            KarmaEdgeReceipt.model_validate(body)


def test_feedback_heroine_identity_and_janus_validation_edges() -> None:
    feedback = FeedbackSignal(
        run_id="",
        metric_date="bad",
        roas=-1,
        ctr=2,
        spend_krw=-1,
    )
    assert len(feedback.validate()) == 5
    assert FeedbackSignal.from_dict(feedback.to_dict()).spend_krw == -1

    heroine = Heroine(
        brief_protagonist="남",
        visual_archetype="bad",  # type: ignore[arg-type]
        voice_concept="bad",
        visual_style="bad",  # type: ignore[arg-type]
        locale="bad",
    )
    assert len(heroine.validate()) == 5
    assert Heroine.from_dict(heroine.to_dict()).locale == "bad"

    assert panel_with_identity_qa({"storage_key": "panel"}, score=0.9) == {
        "storage_key": "panel",
        "ref_storage_keys": ["panel"],
        "identity_qa_score": 0.9,
    }
    assert panel_with_identity_qa({}, score=None)["ref_storage_keys"] == []

    intake = Intake13Q.from_dict({"identity": "brand", "proof": "proof"})
    assert intake.answered_count == 2
    brief = JanusBrief.from_dict(
        {"brand": "viewok", "persona_visual_style": "bad", "identity": "brand"}
    )
    assert brief.validate() == ["style 미지원: bad"]
    assert JanusBrief.from_dict({}).validate() == ["brand_slug 필수"]
    assert brief.to_dict()["brand_slug"] == "viewok"

    with pytest.raises(ValueError, match="digest subject is incomplete"):
        janus_story_product_record_digest_v4({})


def _creative_order() -> dict[str, object]:
    workspace = "workspace"
    external = "order-1"
    digest = "b" * 64
    return {
        "contract_version": CONTRACT_VERSIONS["CreativeOrder"],
        "customer_order_key": customer_order_key(workspace, external, digest),
        "workspace_id": workspace,
        "account_id": "account",
        "brand_id": "brand",
        "product_or_listing_id": "listing",
        "customer_external_order_id": external,
        "canonical_order_payload": {},
        "canonical_order_digest": digest,
        "created_at_utc": "2026-08-20T00:00:00Z",
    }


def _verified_render() -> dict[str, object]:
    return {
        "verified_render_receipt_id": "receipt",
        "customer_order_key": "order",
        "workspace_id": "workspace",
        "run_id": "run",
        "render_job_id": "render",
        "render_effect_key": "effect",
        "editor_approval_digest": "approval",
        "output_url": "https://cdn.example/final.mp4",
        "storage_key": "final.mp4",
        "output_sha256": "a" * 64,
        "output_bytes": 1,
        "duration_ms": 48000,
        "video_codec": "h264",
        "audio_codec": "aac",
        "mechanical_checker_version": "v1",
        "qa_checker_version": "v1",
        "qa_verdict": "PASS",
        "qa_evidence_digest": "evidence",
        "source_revisions": {},
        "deployed_revisions": {},
        "created_at_utc": "2026-08-20T00:00:00Z",
        "transaction_audit_id": "audit",
    }


def test_overnight_v1_rejects_order_and_render_receipt_drift() -> None:
    order = _creative_order()
    validate_creative_order(order)
    assert serialize_equal(order, dict(reversed(list(order.items())))) is True
    for field, value in (
        ("contract_version", "bad"),
        ("workspace_id", ""),
        ("customer_order_key", "bad"),
    ):
        changed = dict(order)
        changed[field] = value
        with pytest.raises(ValueError):
            validate_creative_order(changed)

    receipt = _verified_render()
    validate_verified_render_receipt(receipt)
    receipt["output_sha256"] = "short"
    with pytest.raises(ValueError, match="output_sha256 required"):
        validate_verified_render_receipt(receipt)


def test_planet_registry_and_provenance_helpers_cover_fallbacks() -> None:
    assert io_for("ARES").planet == "ares"
    assert needs_new_contract() == ()
    assert dsl_ready() == ()

    provenance = ClaimProvenance(
        source_url="https://example.com", quote_span="proof", observed_at="now"
    )
    assert provenance_from_dict(provenance) is provenance
    assert provenance_from_dict("invalid") is None
    alias = provenance_from_dict(
        {"url": " https://example.com ", "quote": " proof ", "observed": " now "}
    )
    assert alias == provenance
    direct = claim_with_provenance(
        " claim ", source_url="https://example.com", quote_span="proof"
    )
    assert direct.is_verified() is True
    bare = ProvenancedClaim(claim="claim")
    assert bare.is_verified() is False
    assert provenance_to_dict(None) == {}
    assert provenance_to_dict(bare) == {"claim": "claim"}
    assert provenance_to_dict(direct)["provenance"]["source_url"] == "https://example.com"
    assert provenance_to_dict(provenance)["source_url"] == "https://example.com"
    assert now_observed_at().endswith("Z")


def test_shot_list_reports_camera_and_continuity_conflicts() -> None:
    invalid = ShotList(
        shots=(
            ShotMetadata(beat_index=None),  # type: ignore[arg-type]
            ShotMetadata(beat_index="1"),  # type: ignore[arg-type]
            ShotMetadata(
                beat_index=2,
                duration_ms=0,
                lens="macro",
                shot_size="wide",
                direction="camera_left",
                continuity_cue="same_subject_from_right",
            ),
            ShotMetadata(
                beat_index=3,
                direction="camera_right",
                continuity_cue="same_subject_from_left",
            ),
            ShotMetadata(beat_index=3),
        )
    )
    errors = invalid.validate()
    assert len(errors) == 8
    assert len(invalid) == 5
    assert list(invalid)[0].beat_index is None
    assert invalid.shot_for_beat(2) is invalid.shots[2]
    assert invalid.shot_for_beat(99) is None

    typed = ShotMetadata(beat_index=4, policy_flags=("safe",))
    parsed = ShotList.from_list(
        [typed, {"beat_index": 5, "policy_flags": ["safe"]}, "ignored"]
    )
    assert parsed.shots[0] is typed
    assert parsed.shots[1].policy_flags == ("safe",)
    assert parsed.to_dict()["shots"][1]["beat_index"] == 5


def test_six_realm_and_timeline_helpers_cover_all_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert get_realm_preset("지옥")["transition"] == "cut"  # type: ignore[index]
    assert get_realm_preset("unknown") is None
    assert get_sfx_cue_for_emotion(" 천상 ") == "soft-whoosh"
    assert get_sfx_cue_for_emotion(None) == ""  # type: ignore[arg-type]

    assert normalize_render_dispatch_url(None) is None
    assert normalize_render_dispatch_url("https://render.example/old?q=1#f") == (
        "https://render.example/v1/render?q=1#f"
    )
    assert normalize_render_dispatch_url("https://render.example/v1/render") == (
        "https://render.example/v1/render"
    )
    real_import = builtins.__import__

    def fail_url_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "urllib.parse":
            raise ImportError("simulated")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_url_import)
    assert normalize_render_dispatch_url("renderer/v1/render") == "renderer/v1/render"
    assert normalize_render_dispatch_url("renderer") == "renderer/v1/render"
    monkeypatch.setattr(builtins, "__import__", real_import)

    assert stable_snapshot_id(run_id="run", render_job_id=" job ") == "job"
    assert stable_snapshot_id(run_id="run", snapshot={"snapshot_id": "existing"}) == (
        "existing"
    )
    assert stable_snapshot_id(run_id="run", snapshot="bad").startswith("snap-")  # type: ignore[arg-type]

    payload = build_timeline_v2_payload(
        run_id="run",
        snapshot_id="snapshot",
        input_props={"snapshotId": "preserved"},
        callback_url=" callback ",
    )
    assert payload["input_props"]["snapshotId"] == "preserved"
    assert payload["callback_url"] == "callback"

    preview = hephaestus_render_node_input(
        run_id="run",
        snapshot_id="snapshot",
        input_props={},
        gates_approved=False,
        approved_final_render=False,
        callback_url="https://callback.example",
    )
    assert preview["mode"] == "preview"
    assert preview["callback_url"] == "https://callback.example"
    final = hephaestus_render_node_input(
        run_id="run",
        snapshot_id="snapshot",
        input_props={},
        gates_approved=True,
        approved_final_render=True,
        approval_receipt_ref=" receipt ",
    )
    assert final["mode"] == "final"
    assert final["approval_receipt_ref"] == "receipt"
