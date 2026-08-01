"""All-beat video V2 factory contract chain."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

import hiob_contracts
from hiob_contracts import (
    AtroposFanInManifestV2,
    BeatArtifactSetReceiptV1,
    BeatVideoReceiptV1,
    BeatVideoRequestV1,
    FactoryBeatManifestV1,
    HephaestusFinalRenderReceiptV2,
    ReelsFactoryReceiptV2,
    derive_atropos_fan_in_manifest_digest_v2,
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


def _artifact(
    beat_index: int | None,
    *,
    kind: str,
    artifact_id: str,
    sha_seed: str,
    duration_ms: int | None = None,
) -> dict:
    return {
        "artifact_id": artifact_id,
        "kind": kind,
        "uri": f"factory-artifacts/{artifact_id}",
        "sha256": sha256_digest({"artifact": sha_seed}),
        "mime": "video/mp4" if kind == "video" else "image/png",
        "bytes_len": 2048,
        "duration_ms": duration_ms,
        "width": 1080,
        "height": 1920,
        "beat_index": beat_index,
        "producer_planet": "hephaestus" if kind == "video" else "athena",
        "producer_node_id": "video.materialize" if kind == "video" else "image.materialize",
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
        "factory_manifest_digest": manifest["manifest_digest"],
        "expected_beat_count": len(manifest["beats"]),
        "video_receipts": [_video_receipt(0), _video_receipt(1)],
    }
    return {
        **body,
        "receipt_digest": derive_beat_artifact_set_receipt_digest_v1(body),
    }


def _fan_in() -> dict:
    artifact_set = _artifact_set()
    body = {
        "contract_version": "AtroposFanInManifest.v2",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": artifact_set["factory_revision"],
        "plan_digest": PLAN_DIGEST,
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


def _final_render() -> dict:
    fan_in = _fan_in()
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


def _factory_receipt() -> dict:
    manifest = _manifest()
    artifact_set = _artifact_set()
    fan_in = _fan_in()
    final_render = _final_render()
    body = {
        "contract_version": "ReelsFactoryReceipt.v2",
        "workspace_id": WORKSPACE_ID,
        "run_id": RUN_ID,
        "factory_revision": manifest["factory_revision"],
        "plan_digest": PLAN_DIGEST,
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
    fan_in = AtroposFanInManifestV2.model_validate(_fan_in())
    final_render = HephaestusFinalRenderReceiptV2.model_validate(_final_render())
    factory = ReelsFactoryReceiptV2.model_validate(_factory_receipt())

    assert [beat.beat_index for beat in manifest.beats] == [0, 1]
    assert [request.request_digest for request in requests] == [
        receipt.request_digest for receipt in receipts
    ]
    assert artifact_set.expected_beat_count == 2
    assert [artifact.beat_index for artifact in fan_in.video_artifacts] == [0, 1]
    assert final_render.output_url == factory.output_url
    assert hiob_contracts.ReelsFactoryReceiptV2 is ReelsFactoryReceiptV2
    with pytest.raises(ValidationError):
        manifest.beats[0].prompt = "mutated"


@pytest.mark.parametrize("indices", [[1, 0], [0, 2], [0, 0]])
def test_manifest_requires_exact_zero_based_all_beat_order(indices: list[int]) -> None:
    body = _manifest_body()
    for beat, index in zip(body["beats"], indices, strict=True):
        beat["beat_index"] = index
        beat["reference_artifacts"][0]["beat_index"] = index
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
    fan_in = _fan_in()
    fan_in["video_artifacts"][1] = deepcopy(fan_in["video_artifacts"][0])
    fan_in["manifest_digest"] = derive_atropos_fan_in_manifest_digest_v2(fan_in)

    with pytest.raises(ValidationError, match="video_artifacts"):
        AtroposFanInManifestV2.model_validate(fan_in)


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
        "HephaestusFinalRenderReceipt",
        "ReelsFactoryReceiptV2",
    }
    assert expected <= set(registered_contracts())
    result = validate_payload("ReelsFactoryReceiptV2", _factory_receipt())
    assert result.ok is True
    assert isinstance(result.obj, ReelsFactoryReceiptV2)


def test_digest_vector_is_stable_for_python_typescript_parity() -> None:
    assert _manifest()["manifest_digest"] == (
        "sha256:7946182c7515f98c374bfe326e88ebfb33aa4d59fa0f6fdb18e637cd4d32a126"
    )
    assert _factory_receipt()["receipt_digest"] == (
        "sha256:408bc3bc4d72ed8b1ef351088c377b63d373a7a6f345fe8c118d4d111390b9c8"
    )
