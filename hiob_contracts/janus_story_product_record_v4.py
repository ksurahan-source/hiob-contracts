"""Immutable, evidence-reference-only Janus product records for Story V4.

The record intentionally carries no raw 13Q answers, product copy, catalog
body, thumbnail URL, or caller-supplied verification bit.  Janus resolves the
four durable evidence references through its injected store before staging a
V4 product-truth candidate; Star remains the accepted-authority owner.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timezone
from typing import Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

from .ares_script_revision_v1 import (
    DigestStr,
    NonBlankStr,
    _FROZEN_STRICT,
    canonical_contract_digest_v1,
)


class JanusStoryProductScopeV4(BaseModel):
    """Exact workspace, run, brand, and listing coordinates for one product."""

    model_config = _FROZEN_STRICT

    workspace_id: NonBlankStr
    run_id: NonBlankStr
    brand_slug: NonBlankStr
    listing_slug: NonBlankStr
    listing_id: NonBlankStr


class _JanusStoryProductEvidenceRefV4(JanusStoryProductScopeV4):
    """One opaque, durable evidence reference; its content stays in the store."""

    evidence_id: NonBlankStr
    evidence_digest: DigestStr


class StudioIntakeReceiptRefV4(_JanusStoryProductEvidenceRefV4):
    contract_version: Literal["StudioIntakeReceiptRef.v4"]
    referenced_contract_version: Literal["StudioIntakeReceipt.v1"]


class CatalogSnapshotRefV4(_JanusStoryProductEvidenceRefV4):
    contract_version: Literal["CatalogSnapshotRef.v4"]
    referenced_contract_version: Literal["CatalogSnapshot.v1"]


class ThumbnailContentBindingRefV4(_JanusStoryProductEvidenceRefV4):
    contract_version: Literal["ThumbnailContentBindingRef.v4"]
    referenced_contract_version: Literal["ThumbnailContentBinding.v1"]


class VerifiedSourceMaterialReceiptRefV4(_JanusStoryProductEvidenceRefV4):
    contract_version: Literal["VerifiedSourceMaterialReceiptRef.v4"]
    referenced_contract_version: Literal["VerifiedSourceMaterialReceipt.v1"]


_RECORD_DIGEST_FIELDS = (
    "contract_version",
    "record_id",
    "version",
    "evidence_status",
    "recorded_at",
    "workspace_id",
    "run_id",
    "brand_slug",
    "listing_slug",
    "listing_id",
    "studio_intake_receipt_ref",
    "catalog_snapshot_ref",
    "thumbnail_content_binding_ref",
    "verified_source_material_receipt_ref",
)
_AWARE_DATETIME = TypeAdapter(AwareDatetime)
_RECORD_REF_MATCH_FIELDS = (
    "record_id",
    "version",
    "record_digest",
    "workspace_id",
    "run_id",
    "brand_slug",
    "listing_slug",
    "listing_id",
)


def _as_json_mapping(value: Mapping[str, Any] | BaseModel) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return dict(value)


def janus_story_product_record_digest_v4(
    value: Mapping[str, Any] | BaseModel,
) -> str:
    """Canonical digest for an immutable V4 record, excluding its self-digest."""

    data = _as_json_mapping(value)
    try:
        payload = {field: data[field] for field in _RECORD_DIGEST_FIELDS}
    except KeyError as exc:
        raise ValueError("V4 product record digest subject is incomplete") from exc
    recorded_at = _AWARE_DATETIME.validate_python(payload["recorded_at"])
    payload["recorded_at"] = recorded_at.astimezone(timezone.utc).isoformat()
    return canonical_contract_digest_v1(payload)


class JanusStoryProductRecordV4(JanusStoryProductScopeV4):
    """Immutable Janus V4 evidence record, never a Star story authority.

    ``evidence_status`` describes Janus's durable source-evidence review only.
    It deliberately is not named ``status`` and this model has no accepted
    authority receipt, issuer, or staged-candidate field.  Star alone resolves
    the later story-authority lifecycle from a producer's staged candidate.
    """

    contract_version: Literal["JanusStoryProductRecord.v4"]
    record_id: NonBlankStr
    version: int = Field(ge=1)
    evidence_status: Literal["approved"]
    recorded_at: AwareDatetime
    studio_intake_receipt_ref: StudioIntakeReceiptRefV4
    catalog_snapshot_ref: CatalogSnapshotRefV4
    thumbnail_content_binding_ref: ThumbnailContentBindingRefV4
    verified_source_material_receipt_ref: VerifiedSourceMaterialReceiptRefV4
    record_digest: DigestStr

    @field_validator("recorded_at", mode="before")
    @classmethod
    def _parse_recorded_at(cls, value: Any) -> AwareDatetime:
        return _AWARE_DATETIME.validate_python(value)

    @model_validator(mode="after")
    def _bind_scope_and_digest(self) -> "JanusStoryProductRecordV4":
        for evidence_ref in (
            self.studio_intake_receipt_ref,
            self.catalog_snapshot_ref,
            self.thumbnail_content_binding_ref,
            self.verified_source_material_receipt_ref,
        ):
            for field in (
                "workspace_id",
                "run_id",
                "brand_slug",
                "listing_slug",
                "listing_id",
            ):
                if getattr(evidence_ref, field) != getattr(self, field):
                    raise ValueError("evidence reference scope must match product record")
        if self.record_digest != janus_story_product_record_digest_v4(self):
            raise ValueError("record_digest must bind the V4 product record")
        return self


class JanusStoryProductRecordRefV4(JanusStoryProductScopeV4):
    """Opaque caller reference to exactly one approved immutable V4 record."""

    contract_version: Literal["JanusStoryProductRecordRef.v4"] = (
        "JanusStoryProductRecordRef.v4"
    )
    record_id: NonBlankStr
    version: int = Field(ge=1)
    record_digest: DigestStr


def assert_janus_story_product_record_ref_matches_v4(
    *,
    record: JanusStoryProductRecordV4,
    record_ref: JanusStoryProductRecordRefV4,
) -> None:
    """Reject a durable record returned for any different V4 reference field."""

    for field in _RECORD_REF_MATCH_FIELDS:
        if getattr(record, field) != getattr(record_ref, field):
            raise ValueError("V4 product record conflicts with its exact record_ref")


__all__ = [
    "CatalogSnapshotRefV4",
    "JanusStoryProductRecordRefV4",
    "JanusStoryProductRecordV4",
    "JanusStoryProductScopeV4",
    "StudioIntakeReceiptRefV4",
    "ThumbnailContentBindingRefV4",
    "VerifiedSourceMaterialReceiptRefV4",
    "assert_janus_story_product_record_ref_matches_v4",
    "janus_story_product_record_digest_v4",
]
