"""Strict digest-linked contracts for one approved all-beat video factory run.

The chain is intentionally success-only at receipt boundaries:

    FactoryBeatManifest.v1
      -> BeatVideoRequest.v1 / BeatVideoReceipt.v1 (one per beat)
      -> BeatArtifactSetReceipt.v1
      -> AtroposFanInManifest.v2
      -> HephaestusFinalRenderReceipt.v2
      -> ReelsFactoryReceipt.v2

Failures and uncertain provider outcomes belong in the existing progress/failure
receipts.  They cannot be represented as a successful artifact receipt.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Mapping

from pydantic import BaseModel, Field, field_validator, model_validator

from .ares_script_revision_v1 import (
    DigestStr,
    NonBlankStr,
    UtcTimestamp,
    UuidStr,
    _FROZEN_STRICT,
    canonical_contract_digest_v1,
)
from .factory import ArtifactRef


PositiveInt = Annotated[int, Field(gt=0, le=9_007_199_254_740_991)]
NonNegativeInt = Annotated[int, Field(ge=0, le=9_007_199_254_740_991)]

ALL_BEAT_VIDEO_CONTRACT_VERSIONS = {
    "FactoryBeatManifest": "FactoryBeatManifest.v1",
    "BeatVideoRequest": "BeatVideoRequest.v1",
    "BeatVideoReceipt": "BeatVideoReceipt.v1",
    "BeatArtifactSetReceipt": "BeatArtifactSetReceipt.v1",
    "AtroposFanInManifest": "AtroposFanInManifest.v2",
    "HephaestusFinalRenderReceipt": "HephaestusFinalRenderReceipt.v2",
    "ReelsFactoryReceipt": "ReelsFactoryReceipt.v2",
}


def _derive_digest(
    value: Mapping[str, Any] | BaseModel,
    digest_field: str,
) -> str:
    return canonical_contract_digest_v1(value, exclude={digest_field})


def _as_tuple(value: Any) -> Any:
    return tuple(value) if isinstance(value, list) else value


def _assert_relative_storage_key(value: str, field: str) -> None:
    if (
        not value
        or value.startswith(("/", "\\"))
        or "://" in value
        or "?" in value
        or "#" in value
        or "\\" in value
    ):
        raise ValueError(f"{field} must be a durable relative storage key")
    segments = value.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise ValueError(f"{field} must be a durable relative storage key")


def _assert_reference_artifacts(
    artifacts: tuple[ArtifactRef, ...],
    beat_index: int,
) -> None:
    digests: set[str] = set()
    for artifact in artifacts:
        _assert_relative_storage_key(artifact.uri, "reference artifact uri")
        if artifact.beat_index not in {None, beat_index}:
            raise ValueError(
                "reference artifact beat_index must be absent or match request beat"
            )
        if artifact.sha256 in digests:
            raise ValueError("reference artifact sha256 values must be unique")
        digests.add(artifact.sha256)


def _assert_video_artifact(
    artifact: ArtifactRef,
    *,
    beat_index: int | None,
    final: bool = False,
) -> None:
    _assert_relative_storage_key(artifact.uri, "artifact uri")
    if artifact.kind != "video" or artifact.mime != "video/mp4":
        raise ValueError("artifact must be a video/mp4 video")
    if artifact.beat_index != beat_index:
        raise ValueError("artifact beat_index does not match receipt")
    if artifact.bytes_len <= 0:
        raise ValueError("artifact bytes_len must be positive")
    if artifact.duration_ms is None or artifact.duration_ms <= 0:
        raise ValueError("artifact duration_ms must be positive")
    if artifact.width is None or artifact.width <= 0:
        raise ValueError("artifact width must be positive")
    if artifact.height is None or artifact.height <= 0:
        raise ValueError("artifact height must be positive")
    if final and artifact.beat_index is not None:
        raise ValueError("final artifact must not be bound to one beat")


def derive_factory_beat_manifest_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "manifest_digest")


def derive_beat_video_request_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "request_digest")


def derive_beat_video_receipt_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "receipt_digest")


def derive_beat_artifact_set_receipt_digest_v1(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "receipt_digest")


def derive_atropos_fan_in_manifest_digest_v2(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "manifest_digest")


def derive_hephaestus_final_render_receipt_digest_v2(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "receipt_digest")


def derive_reels_factory_receipt_digest_v2(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    return _derive_digest(value, "receipt_digest")


class FactoryBeatSpecV1(BaseModel):
    """One exact paid video input inside the approved factory manifest."""

    model_config = _FROZEN_STRICT

    beat_index: NonNegativeInt
    generation_nonce: UuidStr
    prompt: NonBlankStr
    duration_ms: PositiveInt
    fps: PositiveInt
    width: PositiveInt
    height: PositiveInt
    reference_artifacts: tuple[ArtifactRef, ...] = Field(min_length=1)
    provider: NonBlankStr
    model: NonBlankStr

    @field_validator("reference_artifacts", mode="before")
    @classmethod
    def _reference_tuple(cls, value: Any) -> Any:
        return _as_tuple(value)

    @model_validator(mode="after")
    def _bind_references_to_beat(self) -> "FactoryBeatSpecV1":
        _assert_reference_artifacts(self.reference_artifacts, self.beat_index)
        return self


class FactoryBeatManifestV1(BaseModel):
    """Exact ordered all-beat scope approved for one factory revision."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["FactoryBeatManifest.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: PositiveInt
    plan_digest: DigestStr
    beats: tuple[FactoryBeatSpecV1, ...] = Field(min_length=1, max_length=64)
    manifest_digest: DigestStr

    @field_validator("beats", mode="before")
    @classmethod
    def _beats_tuple(cls, value: Any) -> Any:
        return _as_tuple(value)

    @model_validator(mode="after")
    def _bind_all_beats(self) -> "FactoryBeatManifestV1":
        indices = [beat.beat_index for beat in self.beats]
        if indices != list(range(len(self.beats))):
            raise ValueError("manifest beat indices must be exactly 0..N-1")
        nonces = [beat.generation_nonce for beat in self.beats]
        if len(nonces) != len(set(nonces)):
            raise ValueError("generation_nonce must be unique per beat")
        if self.manifest_digest != derive_factory_beat_manifest_digest_v1(self):
            raise ValueError("manifest_digest does not match factory beat manifest")
        return self


class BeatVideoRequestV1(BaseModel):
    """One signed provider input; its request digest is the idempotent identity."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["BeatVideoRequest.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    beat_index: NonNegativeInt
    factory_revision: PositiveInt
    plan_digest: DigestStr
    factory_manifest_digest: DigestStr
    generation_nonce: UuidStr
    prompt: NonBlankStr
    duration_ms: PositiveInt
    fps: PositiveInt
    width: PositiveInt
    height: PositiveInt
    reference_artifacts: tuple[ArtifactRef, ...] = Field(min_length=1)
    provider: NonBlankStr
    model: NonBlankStr
    request_digest: DigestStr

    @field_validator("reference_artifacts", mode="before")
    @classmethod
    def _reference_tuple(cls, value: Any) -> Any:
        return _as_tuple(value)

    @model_validator(mode="after")
    def _bind_request(self) -> "BeatVideoRequestV1":
        _assert_reference_artifacts(self.reference_artifacts, self.beat_index)
        if self.request_digest != derive_beat_video_request_digest_v1(self):
            raise ValueError("request_digest does not match beat video request")
        return self


class BeatVideoReceiptV1(BaseModel):
    """Success proof for exactly one BeatVideoRequest.v1."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["BeatVideoReceipt.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    beat_index: NonNegativeInt
    factory_revision: PositiveInt
    plan_digest: DigestStr
    factory_manifest_digest: DigestStr
    generation_nonce: UuidStr
    request_digest: DigestStr
    duration_ms: PositiveInt
    fps: PositiveInt
    width: PositiveInt
    height: PositiveInt
    provider: NonBlankStr
    model: NonBlankStr
    provider_job_id: NonBlankStr
    status: Literal["succeeded"]
    artifact: ArtifactRef
    receipt_digest: DigestStr

    @model_validator(mode="after")
    def _bind_success_artifact(self) -> "BeatVideoReceiptV1":
        _assert_video_artifact(self.artifact, beat_index=self.beat_index)
        if (
            self.artifact.duration_ms != self.duration_ms
            or self.artifact.width != self.width
            or self.artifact.height != self.height
        ):
            raise ValueError("artifact dimensions or duration do not match request")
        if self.receipt_digest != derive_beat_video_receipt_digest_v1(self):
            raise ValueError("receipt_digest does not match beat video receipt")
        return self

    def binds_request(self, request: BeatVideoRequestV1) -> bool:
        return (
            self.workspace_id == request.workspace_id
            and self.run_id == request.run_id
            and self.beat_index == request.beat_index
            and self.factory_revision == request.factory_revision
            and self.plan_digest == request.plan_digest
            and self.factory_manifest_digest == request.factory_manifest_digest
            and self.generation_nonce == request.generation_nonce
            and self.request_digest == request.request_digest
            and self.duration_ms == request.duration_ms
            and self.fps == request.fps
            and self.width == request.width
            and self.height == request.height
            and self.provider == request.provider
            and self.model == request.model
        )


class BeatArtifactSetReceiptV1(BaseModel):
    """Complete ordered set of successful beat-video receipts."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["BeatArtifactSetReceipt.v1"]
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: PositiveInt
    plan_digest: DigestStr
    factory_manifest_digest: DigestStr
    expected_beat_count: PositiveInt
    video_receipts: tuple[BeatVideoReceiptV1, ...] = Field(min_length=1)
    receipt_digest: DigestStr

    @field_validator("video_receipts", mode="before")
    @classmethod
    def _receipts_tuple(cls, value: Any) -> Any:
        return _as_tuple(value)

    @model_validator(mode="after")
    def _bind_complete_set(self) -> "BeatArtifactSetReceiptV1":
        indices = [receipt.beat_index for receipt in self.video_receipts]
        if (
            len(self.video_receipts) != self.expected_beat_count
            or indices != list(range(self.expected_beat_count))
        ):
            raise ValueError("video receipts must cover exactly 0..N-1")
        receipt_digests: set[str] = set()
        artifact_digests: set[str] = set()
        for receipt in self.video_receipts:
            if (
                receipt.workspace_id != self.workspace_id
                or receipt.run_id != self.run_id
                or receipt.factory_revision != self.factory_revision
                or receipt.plan_digest != self.plan_digest
                or receipt.factory_manifest_digest != self.factory_manifest_digest
            ):
                raise ValueError("video receipt scope or digest does not match set")
            if receipt.receipt_digest in receipt_digests:
                raise ValueError("video receipt digests must be unique")
            if receipt.artifact.sha256 in artifact_digests:
                raise ValueError("video artifact digests must be unique")
            receipt_digests.add(receipt.receipt_digest)
            artifact_digests.add(receipt.artifact.sha256)
        if self.receipt_digest != derive_beat_artifact_set_receipt_digest_v1(self):
            raise ValueError("receipt_digest does not match beat artifact set")
        return self


class AtroposFanInManifestV2(BaseModel):
    """Exact all-beat video, timeline, audio, and render-policy fan-in."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["AtroposFanInManifest.v2"]
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: PositiveInt
    plan_digest: DigestStr
    factory_manifest_digest: DigestStr
    beat_artifact_set_receipt: BeatArtifactSetReceiptV1
    video_artifacts: tuple[ArtifactRef, ...] = Field(min_length=1)
    timeline_digest: DigestStr
    audio_mix_digest: DigestStr
    render_policy_digest: DigestStr
    manifest_digest: DigestStr

    @field_validator("video_artifacts", mode="before")
    @classmethod
    def _artifacts_tuple(cls, value: Any) -> Any:
        return _as_tuple(value)

    @model_validator(mode="after")
    def _bind_fan_in(self) -> "AtroposFanInManifestV2":
        receipt = self.beat_artifact_set_receipt
        if (
            receipt.workspace_id != self.workspace_id
            or receipt.run_id != self.run_id
            or receipt.factory_revision != self.factory_revision
            or receipt.plan_digest != self.plan_digest
            or receipt.factory_manifest_digest != self.factory_manifest_digest
        ):
            raise ValueError("beat artifact set scope or digest does not match fan-in")
        expected = tuple(item.artifact for item in receipt.video_receipts)
        if self.video_artifacts != expected:
            raise ValueError("video_artifacts must exactly match ordered video receipts")
        if self.manifest_digest != derive_atropos_fan_in_manifest_digest_v2(self):
            raise ValueError("manifest_digest does not match Atropos fan-in")
        return self


class HephaestusFinalRenderReceiptV2(BaseModel):
    """Playable final render proof after mechanical QA."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["HephaestusFinalRenderReceipt.v2"]
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: PositiveInt
    fan_in_manifest_digest: DigestStr
    status: Literal["ready"]
    output_artifact: ArtifactRef
    output_url: NonBlankStr
    mechanical_qa_passed: Literal[True]
    rendered_at_utc: UtcTimestamp
    receipt_digest: DigestStr

    @field_validator("output_url")
    @classmethod
    def _durable_output_url(cls, value: str) -> str:
        if not value.startswith("https://") or any(char.isspace() for char in value):
            raise ValueError("output_url must be durable HTTPS")
        return value

    @model_validator(mode="after")
    def _bind_final_render(self) -> "HephaestusFinalRenderReceiptV2":
        _assert_video_artifact(self.output_artifact, beat_index=None, final=True)
        if (
            self.receipt_digest
            != derive_hephaestus_final_render_receipt_digest_v2(self)
        ):
            raise ValueError("receipt_digest does not match final render receipt")
        return self


class ReelsFactoryReceiptV2(BaseModel):
    """Terminal success receipt for the complete all-beat customer artifact."""

    model_config = _FROZEN_STRICT

    contract_version: Literal["ReelsFactoryReceipt.v2"]
    workspace_id: UuidStr
    run_id: UuidStr
    factory_revision: PositiveInt
    plan_digest: DigestStr
    factory_manifest_digest: DigestStr
    beat_artifact_set_receipt_digest: DigestStr
    fan_in_manifest_digest: DigestStr
    final_render_receipt: HephaestusFinalRenderReceiptV2
    status: Literal["succeeded"]
    output_url: NonBlankStr
    output_sha256: DigestStr
    receipt_digest: DigestStr

    @model_validator(mode="after")
    def _bind_terminal_success(self) -> "ReelsFactoryReceiptV2":
        render = self.final_render_receipt
        if (
            render.workspace_id != self.workspace_id
            or render.run_id != self.run_id
            or render.factory_revision != self.factory_revision
        ):
            raise ValueError("final render receipt scope does not match factory")
        if render.fan_in_manifest_digest != self.fan_in_manifest_digest:
            raise ValueError("fan_in_manifest_digest does not match final render receipt")
        if render.output_url != self.output_url:
            raise ValueError("output_url does not match final render receipt")
        if render.output_artifact.sha256 != self.output_sha256:
            raise ValueError("output_sha256 does not match final render artifact")
        if self.receipt_digest != derive_reels_factory_receipt_digest_v2(self):
            raise ValueError("receipt_digest does not match reels factory receipt")
        return self


__all__ = [
    "ALL_BEAT_VIDEO_CONTRACT_VERSIONS",
    "FactoryBeatSpecV1",
    "FactoryBeatManifestV1",
    "BeatVideoRequestV1",
    "BeatVideoReceiptV1",
    "BeatArtifactSetReceiptV1",
    "AtroposFanInManifestV2",
    "HephaestusFinalRenderReceiptV2",
    "ReelsFactoryReceiptV2",
    "derive_factory_beat_manifest_digest_v1",
    "derive_beat_video_request_digest_v1",
    "derive_beat_video_receipt_digest_v1",
    "derive_beat_artifact_set_receipt_digest_v1",
    "derive_atropos_fan_in_manifest_digest_v2",
    "derive_hephaestus_final_render_receipt_digest_v2",
    "derive_reels_factory_receipt_digest_v2",
]
