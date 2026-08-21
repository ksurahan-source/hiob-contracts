"""All-beat video V2/V3 factory contract chain."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import hiob_contracts
import hiob_contracts.all_beat_video as all_beat_video
from hiob_contracts import (
    AtroposFanInManifestV2,
    AtroposFanInManifestV3,
    BeatArtifactSetReceiptV1,
    BeatVideoReceiptV1,
    BeatVideoRequestV1,
    FactoryBeatManifestV1,
    HephaestusFinalRenderReceiptV2,
    ReelsFactoryReceiptV2,
    StarReelsViewV2,
    beat_video_request_binds_manifest_v1,
    factory_beat_manifest_binds_paid_authority_v1,
    reels_factory_receipt_binds_chain_v2,
    derive_factory_beat_manifest_idempotency_key_v1,
    derive_atropos_fan_in_manifest_digest_v2,
    derive_atropos_fan_in_manifest_digest_v3,
    derive_beat_artifact_set_receipt_digest_v1,
    derive_beat_video_receipt_digest_v1,
    derive_beat_video_request_digest_v1,
    derive_factory_beat_manifest_digest_v1,
    derive_hephaestus_final_render_receipt_digest_v2,
    derive_reels_factory_receipt_digest_v2,
    registered_contracts,
    sha256_digest,
    validate_payload,
)


WORKSPACE_ID = "00000000-0000-4000-8000-000000000001"
RUN_ID = "00000000-0000-4000-8000-000000000002"
PLAN_DIGEST = sha256_digest({"plan": "approved-v2"})
TIMELINE_DIGEST = sha256_digest({"timeline": "all-beats"})
AUDIO_MIX_DIGEST = sha256_digest({"audio": "sealed-mix"})
RENDER_POLICY_DIGEST = sha256_digest({"render": "vertical-1080p"})
AUTHORITY_DIGEST = sha256_digest({"authority": "paid-all-beats"})


def _artifact(
    beat_index: int | None,
    *,
    kind: str,
    artifact_id: str,
    sha_seed: str,
    duration_ms: int | None = None,
) -> dict:
    is_video = kind == "video"
    is_audio = kind == "audio"
    return {
        "artifact_id": artifact_id,
        "kind": kind,
        "uri": f"factory-artifacts/{artifact_id}",
        "sha256": sha256_digest({"artifact": sha_seed}),
        "mime": "video/mp4" if is_video else "audio/mpeg" if is_audio else "image/png",
        "bytes_len": 2048,
        "duration_ms": duration_ms,
        "width": None if is_audio else 1080,
        "height": None if is_audio else 1920,
        "beat_index": beat_index,
        "producer_planet": (
            "hephaestus" if is_video else "orpheus" if is_audio else "athena"
        ),
        "producer_node_id": (
            "video.materialize"
            if is_video
            else "voice.materialize"
            if is_audio
            else "image.materialize"
        ),
        "execution_id": f"exec-{artifact_id}",
        "producer_revision": "rev-1",
        "image_digest": None,
        "source_output_digests": [],
        "edge_receipt_digests": [],
        "provenance_refs": [],
        "consent_refs": [],
    }


def _manifest_body() -> dict:
    return {
        "contract_version": "FactoryBeatManifest.v1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": 11,
        "plan_digest": PLAN_DIGEST,
        "paid_budget_authority_digest": AUTHORITY_DIGEST,
        "beats": [
            {
                "beat_index": index,
                "generation_nonce": f"00000000-0000-4000-8000-00000000001{index}",
                "prompt": f"sealed prompt {index}",
                "duration_ms": 5000,
                "fps": 30,
                "width": 1080,
                "height": 1920,
                "reference_artifacts": [
                    _artifact(
                        index,
                        kind="image",
                        artifact_id=f"image-{index}.png",
                        sha_seed=f"image-{index}",
                    )
                ],
                "provider": "fal",
                "model": "kling-video-v2.1-master",
            }
            for index in range(2)
        ],
    }


def _manifest() -> dict:
    body = _manifest_body()
    body["idempotency_key"] = derive_factory_beat_manifest_idempotency_key_v1(body)
    return {
        **body,
        "manifest_digest": derive_factory_beat_manifest_digest_v1(body),
    }


def _request(beat_index: int) -> dict:
    manifest = _manifest()
    beat = manifest["beats"][beat_index]
    body = {
        "contract_version": "BeatVideoRequest.v1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "beat_index": beat_index,
        "factory_revision": manifest["factory_revision"],
        "plan_digest": PLAN_DIGEST,
        "paid_budget_authority_digest": AUTHORITY_DIGEST,
        "factory_manifest_digest": manifest["manifest_digest"],
        "generation_nonce": beat["generation_nonce"],
        "prompt": beat["prompt"],
        "duration_ms": beat["duration_ms"],
        "fps": beat["fps"],
        "width": beat["width"],
        "height": beat["height"],
        "reference_artifacts": beat["reference_artifacts"],
        "provider": beat["provider"],
        "model": beat["model"],
    }
    return {
        **body,
        "request_digest": derive_beat_video_request_digest_v1(body),
    }


def _video_receipt(beat_index: int) -> dict:
    request = _request(beat_index)
    body = {
        "contract_version": "BeatVideoReceipt.v1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "beat_index": beat_index,
        "factory_revision": request["factory_revision"],
        "plan_digest": PLAN_DIGEST,
        "paid_budget_authority_digest": AUTHORITY_DIGEST,
        "factory_manifest_digest": request["factory_manifest_digest"],
        "generation_nonce": request["generation_nonce"],
        "request_digest": request["request_digest"],
        "duration_ms": request["duration_ms"],
        "fps": request["fps"],
        "width": request["width"],
        "height": request["height"],
        "provider": request["provider"],
        "model": request["model"],
        "provider_job_id": f"provider-job-{beat_index}",
        "status": "succeeded",
        "artifact": _artifact(
            beat_index,
            kind="video",
            artifact_id=f"beat-{beat_index}.mp4",
            sha_seed=f"video-{beat_index}",
            duration_ms=request["duration_ms"],
        ),
    }
    return {
        **body,
        "receipt_digest": derive_beat_video_receipt_digest_v1(body),
    }


def _artifact_set() -> dict:
    manifest = _manifest()
    body = {
        "contract_version": "BeatArtifactSetReceipt.v1",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": manifest["factory_revision"],
        "plan_digest": PLAN_DIGEST,
        "paid_budget_authority_digest": AUTHORITY_DIGEST,
        "factory_manifest_digest": manifest["manifest_digest"],
        "expected_beat_count": len(manifest["beats"]),
        "video_receipts": [_video_receipt(0), _video_receipt(1)],
    }
    return {
        **body,
        "receipt_digest": derive_beat_artifact_set_receipt_digest_v1(body),
    }


def _audio_artifacts() -> list[dict]:
    return [
        _artifact(
            beat_index,
            kind="audio",
            artifact_id=f"voice-{beat_index}.mp3",
            sha_seed=f"audio-{beat_index}",
            duration_ms=5000,
        )
        for beat_index in range(2)
    ]


def _fan_in_v2() -> dict:
    artifact_set = _artifact_set()
    body = {
        "contract_version": "AtroposFanInManifest.v2",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": artifact_set["factory_revision"],
        "plan_digest": PLAN_DIGEST,
        "paid_budget_authority_digest": AUTHORITY_DIGEST,
        "factory_manifest_digest": artifact_set["factory_manifest_digest"],
        "beat_artifact_set_receipt": artifact_set,
        "video_artifacts": [
            receipt["artifact"] for receipt in artifact_set["video_receipts"]
        ],
        "timeline_digest": TIMELINE_DIGEST,
        "audio_mix_digest": AUDIO_MIX_DIGEST,
        "render_policy_digest": RENDER_POLICY_DIGEST,
    }
    return {
        **body,
        "manifest_digest": derive_atropos_fan_in_manifest_digest_v2(body),
    }


def _fan_in_v3() -> dict:
    artifact_set = _artifact_set()
    audio_artifacts = _audio_artifacts()
    body = {
        "contract_version": "AtroposFanInManifest.v3",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": artifact_set["factory_revision"],
        "plan_digest": PLAN_DIGEST,
        "paid_budget_authority_digest": AUTHORITY_DIGEST,
        "factory_manifest_digest": artifact_set["factory_manifest_digest"],
        "beat_artifact_set_receipt": artifact_set,
        "video_artifacts": [
            receipt["artifact"] for receipt in artifact_set["video_receipts"]
        ],
        "audio_artifacts": audio_artifacts,
        "timeline_digest": TIMELINE_DIGEST,
        "audio_mix_digest": sha256_digest({"audio_artifacts": audio_artifacts}),
        "render_policy_digest": RENDER_POLICY_DIGEST,
    }
    return {
        **body,
        "manifest_digest": derive_atropos_fan_in_manifest_digest_v3(body),
    }


def _final_render(fan_in: dict | None = None) -> dict:
    fan_in = _fan_in_v3() if fan_in is None else fan_in
    body = {
        "contract_version": "HephaestusFinalRenderReceipt.v2",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": fan_in["factory_revision"],
        "fan_in_manifest_digest": fan_in["manifest_digest"],
        "status": "ready",
        "output_artifact": _artifact(
            None,
            kind="video",
            artifact_id="final-reel.mp4",
            sha_seed="final-reel",
            duration_ms=10000,
        ),
        "output_url": "https://cdn.example/final-reel.mp4",
        "mechanical_qa_passed": True,
        "rendered_at_utc": "2026-08-01T08:00:00Z",
    }
    return {
        **body,
        "receipt_digest": derive_hephaestus_final_render_receipt_digest_v2(body),
    }


def _factory_receipt(fan_in: dict | None = None) -> dict:
    manifest = _manifest()
    artifact_set = _artifact_set()
    fan_in = _fan_in_v3() if fan_in is None else fan_in
    final_render = _final_render(fan_in)
    body = {
        "contract_version": "ReelsFactoryReceipt.v2",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": manifest["factory_revision"],
        "plan_digest": PLAN_DIGEST,
        "paid_budget_authority_digest": AUTHORITY_DIGEST,
        "factory_manifest_digest": manifest["manifest_digest"],
        "beat_artifact_set_receipt_digest": artifact_set["receipt_digest"],
        "fan_in_manifest_digest": fan_in["manifest_digest"],
        "final_render_receipt": final_render,
        "status": "succeeded",
        "output_url": final_render["output_url"],
        "output_sha256": final_render["output_artifact"]["sha256"],
    }
    return {
        **body,
        "receipt_digest": derive_reels_factory_receipt_digest_v2(body),
    }


def test_valid_all_beat_chain_is_canonical_frozen_and_public() -> None:
    manifest = FactoryBeatManifestV1.model_validate(_manifest())
    requests = [BeatVideoRequestV1.model_validate(_request(i)) for i in range(2)]
    receipts = [BeatVideoReceiptV1.model_validate(_video_receipt(i)) for i in range(2)]
    artifact_set = BeatArtifactSetReceiptV1.model_validate(_artifact_set())
    fan_in = AtroposFanInManifestV3.model_validate(_fan_in_v3())
    final_render = HephaestusFinalRenderReceiptV2.model_validate(_final_render())
    factory = ReelsFactoryReceiptV2.model_validate(_factory_receipt())

    assert [beat.beat_index for beat in manifest.beats] == [0, 1]
    assert [request.request_digest for request in requests] == [
        receipt.request_digest for receipt in receipts
    ]
    assert artifact_set.expected_beat_count == 2
    assert [artifact.beat_index for artifact in fan_in.video_artifacts] == [0, 1]
    assert [artifact.beat_index for artifact in fan_in.audio_artifacts] == [0, 1]
    assert final_render.output_url == factory.output_url
    assert hiob_contracts.ReelsFactoryReceiptV2 is ReelsFactoryReceiptV2
    with pytest.raises(ValidationError):
        manifest.beats[0].prompt = "mutated"


def test_star_customer_view_accepts_ready_all_beat_factory_receipt() -> None:
    view = StarReelsViewV2.model_validate(
        {
            "contract_version": "StarReelsView.v2",
            "section": "RunStatus",
            "status": "ready",
            "revision": 1,
            "stage_output": None,
            "budget": {
                "script": 1,
                "image": 2,
                "video": 2,
                "voice": 2,
                "render": 1,
                "retries": 0,
                "fallbacks": 0,
                "character_lock": 0,
                "all_beat_count": 2,
                "paid_budget_authority_digest": AUTHORITY_DIGEST,
                "beat_artifact_set_receipt": _artifact_set(),
            },
            "review_digest": None,
            "receipts": {
                "factory": _factory_receipt(),
                "script_approval": None,
                "plan_approval": None,
            },
            "provider_call": "confirmed",
            "error": None,
        }
    )

    assert view.status == "ready"
    assert view.receipts.factory.contract_version == "ReelsFactoryReceipt.v2"

    mismatched = view.model_dump(mode="json")
    mismatched["budget"]["all_beat_count"] = 1
    mismatched["budget"]["image"] = 1
    mismatched["budget"]["video"] = 1
    mismatched["budget"]["voice"] = 1
    with pytest.raises(ValidationError, match="artifact count"):
        StarReelsViewV2.model_validate(mismatched)


def test_stored_v2_fan_in_and_factory_receipt_remain_byte_compatible() -> None:
    fan_in_payload = _fan_in_v2()
    fan_in = AtroposFanInManifestV2.model_validate(fan_in_payload)
    factory = ReelsFactoryReceiptV2.model_validate(_factory_receipt(fan_in_payload))

    assert fan_in.manifest_digest == (
        "sha256:5898d7f56f6cf323fc099e3a3bc1181caf4adf203927541a0ec0a2784417b268"
    )
    assert factory.receipt_digest == (
        "sha256:8aaa8f391e121cffe978c0c2026ef3b10b0ebd06fefd520da440c437447bbd6f"
    )
    assert reels_factory_receipt_binds_chain_v2(
        factory,
        FactoryBeatManifestV1.model_validate(_manifest()),
        BeatArtifactSetReceiptV1.model_validate(_artifact_set()),
        fan_in,
    )

    v3_only_field = {**fan_in_payload, "audio_artifacts": _audio_artifacts()}
    with pytest.raises(ValidationError, match="audio_artifacts"):
        AtroposFanInManifestV2.model_validate(v3_only_field)


@pytest.mark.parametrize("indices", [[1, 0], [0, 2], [0, 0]])
def test_manifest_requires_exact_zero_based_all_beat_order(indices: list[int]) -> None:
    body = _manifest_body()
    for beat, index in zip(body["beats"], indices, strict=True):
        beat["beat_index"] = index
        beat["reference_artifacts"][0]["beat_index"] = index
    body["idempotency_key"] = derive_factory_beat_manifest_idempotency_key_v1(body)
    body["manifest_digest"] = derive_factory_beat_manifest_digest_v1(body)

    with pytest.raises(ValidationError, match="0..N-1"):
        FactoryBeatManifestV1.model_validate(body)


def test_request_rejects_digest_and_reference_beat_drift() -> None:
    request = _request(0)
    request["prompt"] = "tampered"
    with pytest.raises(ValidationError, match="request_digest"):
        BeatVideoRequestV1.model_validate(request)

    request = _request(0)
    request["reference_artifacts"][0]["beat_index"] = 1
    request["request_digest"] = derive_beat_video_request_digest_v1(request)
    with pytest.raises(ValidationError, match="reference artifact beat_index"):
        BeatVideoRequestV1.model_validate(request)

    request = _request(0)
    request["reference_artifacts"][0]["uri"] = "https://cdn.example/image.png"
    request["request_digest"] = derive_beat_video_request_digest_v1(request)
    with pytest.raises(ValidationError, match="relative storage key"):
        BeatVideoRequestV1.model_validate(request)


def test_rehashed_request_still_must_bind_exact_manifest_beat() -> None:
    manifest = FactoryBeatManifestV1.model_validate(_manifest())
    request = _request(0)
    request["prompt"] = "independently valid but unauthorized prompt"
    request["request_digest"] = derive_beat_video_request_digest_v1(request)
    parsed = BeatVideoRequestV1.model_validate(request)
    assert not beat_video_request_binds_manifest_v1(parsed, manifest)


def test_manifest_caps_beats_binds_authority_and_accepts_revision_zero() -> None:
    body = _manifest_body()
    body["factory_revision"] = 0
    body["beats"] = [deepcopy(body["beats"][0]) for _ in range(17)]
    for index, beat in enumerate(body["beats"]):
        beat["beat_index"] = index
        beat["generation_nonce"] = f"00000000-0000-4000-8000-{index:012d}"
        beat["reference_artifacts"][0]["beat_index"] = index
    body["idempotency_key"] = derive_factory_beat_manifest_idempotency_key_v1(body)
    body["manifest_digest"] = derive_factory_beat_manifest_digest_v1(body)
    with pytest.raises(ValidationError):
        FactoryBeatManifestV1.model_validate(body)

    body = _manifest_body()
    body["factory_revision"] = 0
    body["idempotency_key"] = derive_factory_beat_manifest_idempotency_key_v1(body)
    body["manifest_digest"] = derive_factory_beat_manifest_digest_v1(body)
    manifest = FactoryBeatManifestV1.model_validate(body)
    assert manifest.factory_revision == 0
    authority = SimpleNamespace(
        workspace_id=manifest.workspace_id,
        run_id=manifest.run_id,
        factory_revision=0,
        all_beat_count=len(manifest.beats),
        authority_digest=AUTHORITY_DIGEST,
    )
    assert not factory_beat_manifest_binds_paid_authority_v1(manifest, authority)


def test_terminal_verifier_rejects_rehashed_cross_chain_substitution() -> None:
    factory = ReelsFactoryReceiptV2.model_validate(_factory_receipt())
    manifest = FactoryBeatManifestV1.model_validate(_manifest())
    artifact_set = BeatArtifactSetReceiptV1.model_validate(_artifact_set())
    fan_in = AtroposFanInManifestV3.model_validate(_fan_in_v3())
    assert reels_factory_receipt_binds_chain_v2(
        factory, manifest, artifact_set, fan_in
    )
    alien = _manifest()
    alien["plan_digest"] = sha256_digest({"plan": "alien"})
    alien["idempotency_key"] = derive_factory_beat_manifest_idempotency_key_v1(alien)
    alien["manifest_digest"] = derive_factory_beat_manifest_digest_v1(alien)
    assert not reels_factory_receipt_binds_chain_v2(
        factory,
        FactoryBeatManifestV1.model_validate(alien),
        artifact_set,
        fan_in,
    )


@pytest.mark.parametrize(
    "url",
    ["https:///missing-host.mp4", "https://user:pass@cdn.example/out.mp4"],
)
def test_output_url_requires_valid_credential_free_https_host(url: str) -> None:
    render = _final_render()
    render["output_url"] = url
    render["receipt_digest"] = derive_hephaestus_final_render_receipt_digest_v2(render)
    with pytest.raises(ValidationError):
        HephaestusFinalRenderReceiptV2.model_validate(render)


@pytest.mark.parametrize("value", [True, 1.0, "2048", 9_007_199_254_740_992])
def test_all_beat_artifact_integer_fields_are_strict_json_safe(value) -> None:
    request = _request(0)
    request["reference_artifacts"][0]["bytes_len"] = value
    with pytest.raises((ValidationError, ValueError)):
        request["request_digest"] = derive_beat_video_request_digest_v1(request)
        BeatVideoRequestV1.model_validate(request)

def test_video_receipt_rejects_non_video_or_wrong_beat_artifact() -> None:
    receipt = _video_receipt(0)
    receipt["artifact"]["beat_index"] = 1
    receipt["receipt_digest"] = derive_beat_video_receipt_digest_v1(receipt)
    with pytest.raises(ValidationError, match="artifact beat_index"):
        BeatVideoReceiptV1.model_validate(receipt)

    receipt = _video_receipt(0)
    receipt["artifact"]["uri"] = "/absolute/beat-0.mp4"
    receipt["receipt_digest"] = derive_beat_video_receipt_digest_v1(receipt)
    with pytest.raises(ValidationError, match="relative storage key"):
        BeatVideoReceiptV1.model_validate(receipt)


def test_artifact_set_rejects_partial_or_cross_scope_fan_in() -> None:
    partial = _artifact_set()
    partial["video_receipts"] = partial["video_receipts"][:1]
    partial["receipt_digest"] = derive_beat_artifact_set_receipt_digest_v1(partial)
    with pytest.raises(ValidationError, match="exactly 0..N-1"):
        BeatArtifactSetReceiptV1.model_validate(partial)

    drift = _artifact_set()
    drift["video_receipts"][1]["plan_digest"] = sha256_digest({"other": "plan"})
    drift["video_receipts"][1]["receipt_digest"] = (
        derive_beat_video_receipt_digest_v1(drift["video_receipts"][1])
    )
    drift["receipt_digest"] = derive_beat_artifact_set_receipt_digest_v1(drift)
    with pytest.raises(ValidationError, match="scope or digest"):
        BeatArtifactSetReceiptV1.model_validate(drift)


def test_atropos_fan_in_rejects_artifact_substitution() -> None:
    fan_in = _fan_in_v2()
    fan_in["video_artifacts"][1] = deepcopy(fan_in["video_artifacts"][0])
    fan_in["manifest_digest"] = derive_atropos_fan_in_manifest_digest_v2(fan_in)

    with pytest.raises(ValidationError, match="video_artifacts"):
        AtroposFanInManifestV2.model_validate(fan_in)


def test_atropos_fan_in_requires_audio_artifacts() -> None:
    fan_in = _fan_in_v3()
    del fan_in["audio_artifacts"]
    fan_in["manifest_digest"] = derive_atropos_fan_in_manifest_digest_v3(fan_in)

    with pytest.raises(ValidationError, match="audio_artifacts"):
        AtroposFanInManifestV3.model_validate(fan_in)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("kind", "video"),
        ("mime", "application/octet-stream"),
        ("mime", "audio/"),
        ("mime", "audio/ "),
        ("bytes_len", 0),
        ("duration_ms", 0),
        ("width", 1),
        ("height", 1),
    ],
)
def test_atropos_fan_in_rejects_invalid_audio_artifact_shape(
    field: str,
    value: object,
) -> None:
    fan_in = _fan_in_v3()
    fan_in["audio_artifacts"][0][field] = value
    fan_in["manifest_digest"] = derive_atropos_fan_in_manifest_digest_v3(fan_in)

    with pytest.raises(ValidationError, match="audio artifact"):
        AtroposFanInManifestV3.model_validate(fan_in)


@pytest.mark.parametrize(
    "mutation",
    [
        "reordered", "duplicate", "duplicate_id", "duplicate_sha",
        "duplicate_uri", "wrong_beat",
    ],
)
def test_atropos_fan_in_audio_beats_exactly_match_video_beats(mutation: str) -> None:
    fan_in = _fan_in_v3()
    if mutation == "reordered":
        fan_in["audio_artifacts"].reverse()
    elif mutation == "duplicate":
        fan_in["audio_artifacts"][1] = deepcopy(fan_in["audio_artifacts"][0])
    elif mutation == "duplicate_id":
        fan_in["audio_artifacts"][1]["artifact_id"] = (
            fan_in["audio_artifacts"][0]["artifact_id"]
        )
    elif mutation == "duplicate_sha":
        fan_in["audio_artifacts"][1]["sha256"] = (
            fan_in["audio_artifacts"][0]["sha256"]
        )
    elif mutation == "duplicate_uri":
        fan_in["audio_artifacts"][1]["uri"] = (
            fan_in["audio_artifacts"][0]["uri"]
        )
    else:
        fan_in["audio_artifacts"][1]["beat_index"] = 2
    fan_in["manifest_digest"] = derive_atropos_fan_in_manifest_digest_v3(fan_in)

    with pytest.raises(ValidationError, match="audio_artifacts"):
        AtroposFanInManifestV3.model_validate(fan_in)


def test_atropos_fan_in_audio_mix_digest_binds_ordered_artifacts() -> None:
    fan_in = _fan_in_v3()
    fan_in["audio_mix_digest"] = sha256_digest({"audio_artifacts": []})
    fan_in["manifest_digest"] = derive_atropos_fan_in_manifest_digest_v3(fan_in)

    with pytest.raises(ValidationError, match="audio_mix_digest"):
        AtroposFanInManifestV3.model_validate(fan_in)


@pytest.mark.parametrize(
    "change",
    [
        {"mechanical_qa_passed": False},
        {"status": "failed"},
        {"rendered_at_utc": "2026-08-01T08:00:00+00:00"},
    ],
)
def test_final_render_receipt_is_success_only(change: dict) -> None:
    render = {**_final_render(), **change}
    render["receipt_digest"] = derive_hephaestus_final_render_receipt_digest_v2(
        render
    )
    with pytest.raises(ValidationError):
        HephaestusFinalRenderReceiptV2.model_validate(render)


def test_factory_receipt_binds_final_url_bytes_and_every_upstream_digest() -> None:
    receipt = _factory_receipt()
    receipt["output_url"] = "https://cdn.example/substituted.mp4"
    receipt["receipt_digest"] = derive_reels_factory_receipt_digest_v2(receipt)
    with pytest.raises(ValidationError, match="output_url"):
        ReelsFactoryReceiptV2.model_validate(receipt)

    receipt = _factory_receipt()
    receipt["fan_in_manifest_digest"] = sha256_digest({"fan_in": "other"})
    receipt["receipt_digest"] = derive_reels_factory_receipt_digest_v2(receipt)
    with pytest.raises(ValidationError, match="fan_in_manifest_digest"):
        ReelsFactoryReceiptV2.model_validate(receipt)


def test_contract_registry_and_fail_loud_validation_expose_consumers() -> None:
    expected = {
        "FactoryBeatManifest",
        "BeatVideoRequest",
        "BeatVideoReceipt",
        "BeatArtifactSetReceipt",
        "AtroposFanInManifest",
        "AtroposFanInManifestV2",
        "AtroposFanInManifestV3",
        "HephaestusFinalRenderReceipt",
        "ReelsFactoryReceiptV2",
    }
    assert expected <= set(registered_contracts())
    result = validate_payload("ReelsFactoryReceiptV2", _factory_receipt())
    assert result.ok is True
    assert isinstance(result.obj, ReelsFactoryReceiptV2)
    assert validate_payload("AtroposFanInManifestV2", _fan_in_v2()).ok is True
    assert validate_payload("AtroposFanInManifestV3", _fan_in_v3()).ok is True


def test_digest_vector_is_stable_for_python_typescript_parity() -> None:
    assert _manifest()["manifest_digest"] == (
        "sha256:9afbef2bb2fe6ef1ecb8d168e0a5c3441c90ad73f9a69cc5f4bee74d2c3b1acd"
    )
    assert _factory_receipt()["receipt_digest"] == (
        "sha256:02811fe85bebbef85965088d8361527579c8d0eb6b8100c1601be3f6c142db6d"
    )
    assert _factory_receipt(_fan_in_v2())["receipt_digest"] == (
        "sha256:8aaa8f391e121cffe978c0c2026ef3b10b0ebd06fefd520da440c437447bbd6f"
    )


def test_private_artifact_guards_fail_closed_after_model_construction() -> None:
    image = all_beat_video.StrictAllBeatArtifactRefV1.model_validate(
        _artifact(
            0,
            kind="image",
            artifact_id="reference.png",
            sha_seed="reference",
        )
    )
    with pytest.raises(ValueError, match="relative storage key"):
        all_beat_video._assert_relative_storage_key("folder//file", "artifact")
    with pytest.raises(ValueError, match="sha256 values must be unique"):
        all_beat_video._assert_reference_artifacts((image, image), 0)

    video = BeatVideoReceiptV1.model_validate(_video_receipt(0)).artifact
    invalid_video_fields = [
        ({"kind": "image"}, "video/mp4"),
        ({"bytes_len": 0}, "bytes_len"),
        ({"duration_ms": 0}, "duration_ms"),
        ({"width": 0}, "width"),
        ({"height": 0}, "height"),
    ]
    for update, message in invalid_video_fields:
        with pytest.raises(ValueError, match=message):
            all_beat_video._assert_video_artifact(
                video.model_copy(update=update), beat_index=0
            )
    with pytest.raises(ValueError, match="final artifact"):
        all_beat_video._assert_video_artifact(
            video, beat_index=None, final=True
        )

    audio = all_beat_video.StrictAllBeatArtifactRefV1.model_validate(
        _audio_artifacts()[0]
    )
    with pytest.raises(ValueError, match="beat_index is required"):
        all_beat_video._assert_audio_artifact(
            audio.model_copy(update={"beat_index": None})
        )


def test_https_url_guard_covers_whitespace_invalid_port_and_ip_host() -> None:
    with pytest.raises(ValueError, match="credential-free HTTPS"):
        all_beat_video._assert_https_url("https://cdn.example/out file.mp4")
    with pytest.raises(ValueError, match="credential-free HTTPS"):
        all_beat_video._assert_https_url("https://cdn.example:99999/out.mp4")
    all_beat_video._assert_https_url("https://127.0.0.1/out.mp4")


def test_manifest_reports_each_sealed_digest_failure_after_valid_shape() -> None:
    manifest = FactoryBeatManifestV1.model_validate(_manifest())
    duplicate_nonce = manifest.beats[1].model_copy(
        update={"generation_nonce": manifest.beats[0].generation_nonce}
    )
    with pytest.raises(ValueError, match="generation_nonce"):
        manifest.model_copy(
            update={"beats": (manifest.beats[0], duplicate_nonce)}
        )._bind_all_beats()
    with pytest.raises(ValueError, match="idempotency_key"):
        manifest.model_copy(
            update={"idempotency_key": sha256_digest({"wrong": "idempotency"})}
        )._bind_all_beats()
    with pytest.raises(ValueError, match="manifest_digest"):
        manifest.model_copy(
            update={"manifest_digest": sha256_digest({"wrong": "manifest"})}
        )._bind_all_beats()


def test_video_receipt_reports_artifact_shape_and_receipt_digest_drift() -> None:
    receipt = BeatVideoReceiptV1.model_validate(_video_receipt(0))
    with pytest.raises(ValueError, match="dimensions or duration"):
        receipt.model_copy(
            update={
                "artifact": receipt.artifact.model_copy(update={"width": 720})
            }
        )._bind_success_artifact()
    with pytest.raises(ValueError, match="receipt_digest"):
        receipt.model_copy(
            update={"receipt_digest": sha256_digest({"wrong": "receipt"})}
        )._bind_success_artifact()


def test_artifact_set_reports_duplicate_and_terminal_digest_failures() -> None:
    artifact_set = BeatArtifactSetReceiptV1.model_validate(_artifact_set())
    first, second = artifact_set.video_receipts
    with pytest.raises(ValueError, match="receipt digests must be unique"):
        artifact_set.model_copy(
            update={
                "video_receipts": (
                    first,
                    second.model_copy(
                        update={"receipt_digest": first.receipt_digest}
                    ),
                )
            }
        )._bind_complete_set()
    with pytest.raises(ValueError, match="artifact digests must be unique"):
        artifact_set.model_copy(
            update={
                "video_receipts": (
                    first,
                    second.model_copy(
                        update={
                            "artifact": second.artifact.model_copy(
                                update={"sha256": first.artifact.sha256}
                            )
                        }
                    ),
                )
            }
        )._bind_complete_set()
    with pytest.raises(ValueError, match="receipt_digest"):
        artifact_set.model_copy(
            update={"receipt_digest": sha256_digest({"wrong": "set"})}
        )._bind_complete_set()


def test_fan_in_reports_scope_and_manifest_digest_failures() -> None:
    fan_in = AtroposFanInManifestV2.model_validate(_fan_in_v2())
    alien_set = fan_in.beat_artifact_set_receipt.model_copy(
        update={"workspace_id": "00000000-0000-4000-8000-000000000099"}
    )
    with pytest.raises(ValueError, match="scope or digest"):
        fan_in.model_copy(
            update={"beat_artifact_set_receipt": alien_set}
        )._bind_fan_in()
    with pytest.raises(ValueError, match="manifest_digest"):
        fan_in.model_copy(
            update={"manifest_digest": sha256_digest({"wrong": "fan-in"})}
        )._bind_fan_in()


def test_terminal_receipts_report_each_late_binding_failure() -> None:
    render = HephaestusFinalRenderReceiptV2.model_validate(_final_render())
    with pytest.raises(ValueError, match="receipt_digest"):
        render.model_copy(
            update={"receipt_digest": sha256_digest({"wrong": "render"})}
        )._bind_final_render()

    factory = ReelsFactoryReceiptV2.model_validate(_factory_receipt())
    alien_render = factory.final_render_receipt.model_copy(
        update={"workspace_id": "00000000-0000-4000-8000-000000000099"}
    )
    with pytest.raises(ValueError, match="scope"):
        factory.model_copy(
            update={"final_render_receipt": alien_render}
        )._bind_terminal_success()
    with pytest.raises(ValueError, match="output_sha256"):
        factory.model_copy(
            update={"output_sha256": sha256_digest({"wrong": "output"})}
        )._bind_terminal_success()
    with pytest.raises(ValueError, match="receipt_digest"):
        factory.model_copy(
            update={"receipt_digest": sha256_digest({"wrong": "factory"})}
        )._bind_terminal_success()


def test_manifest_binding_rejects_out_of_range_beat() -> None:
    manifest = FactoryBeatManifestV1.model_validate(_manifest())
    valid_request = BeatVideoRequestV1.model_validate(_request(0))
    receipt = BeatVideoReceiptV1.model_validate(_video_receipt(0))
    assert receipt.binds_request(valid_request)
    assert not receipt.binds_request(
        valid_request.model_copy(
            update={"request_digest": sha256_digest({"request": "different"})}
        )
    )
    request = valid_request.model_copy(
        update={"beat_index": len(manifest.beats)}
    )
    assert not beat_video_request_binds_manifest_v1(request, manifest)
