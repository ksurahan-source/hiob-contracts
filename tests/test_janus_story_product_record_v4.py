"""Janus V4 product records bind only verified, scoped evidence references."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    CatalogSnapshotRefV4,
    JanusStoryProductRecordRefV4,
    JanusStoryProductRecordV4,
    StudioIntakeReceiptRefV4,
    ThumbnailContentBindingRefV4,
    VerifiedSourceMaterialReceiptRefV4,
    assert_janus_story_product_record_ref_matches_v4,
    janus_story_product_record_digest_v4,
    sha256_digest,
)


SCOPE = {
    "workspace_id": "ws-v4-product",
    "run_id": "run-v4-product",
    "brand_slug": "viewok",
    "listing_slug": "anti-fog-cleaner",
    "listing_id": "listing-v4-1",
}


def _evidence_ref(kind: str, evidence_id: str) -> dict[str, str]:
    return {
        "contract_version": f"{kind}Ref.v4",
        "referenced_contract_version": f"{kind}.v1",
        **SCOPE,
        "evidence_id": evidence_id,
        "evidence_digest": sha256_digest({"kind": kind, "id": evidence_id}),
    }


def _record(**updates: object) -> dict:
    unsigned = {
        "contract_version": "JanusStoryProductRecord.v4",
        "record_id": "janus-story-product-v4-1",
        "version": 1,
        "evidence_status": "approved",
        **SCOPE,
        "studio_intake_receipt_ref": _evidence_ref(
            "StudioIntakeReceipt", "studio-intake-v4-1"
        ),
        "catalog_snapshot_ref": _evidence_ref(
            "CatalogSnapshot", "catalog-v4-1"
        ),
        "thumbnail_content_binding_ref": _evidence_ref(
            "ThumbnailContentBinding", "thumbnail-binding-v4-1"
        ),
        "verified_source_material_receipt_ref": _evidence_ref(
            "VerifiedSourceMaterialReceipt", "source-material-v4-1"
        ),
    }
    unsigned.update(updates)
    return {
        **unsigned,
        "record_digest": janus_story_product_record_digest_v4(unsigned),
    }


def test_v4_record_is_frozen_and_contains_only_approved_scoped_evidence_refs() -> None:
    record = JanusStoryProductRecordV4.model_validate(_record())

    assert record.evidence_status == "approved"
    assert record.record_digest == janus_story_product_record_digest_v4(record)
    assert record.studio_intake_receipt_ref.workspace_id == record.workspace_id
    assert record.catalog_snapshot_ref.listing_id == record.listing_id
    assert record.thumbnail_content_binding_ref.brand_slug == record.brand_slug
    assert record.verified_source_material_receipt_ref.run_id == record.run_id
    with pytest.raises(ValidationError):
        record.evidence_status = "unapproved"


def test_v4_record_ref_binds_exact_scope_version_and_record_digest() -> None:
    record = JanusStoryProductRecordV4.model_validate(_record())
    ref = JanusStoryProductRecordRefV4(
        record_id=record.record_id,
        version=record.version,
        record_digest=record.record_digest,
        **SCOPE,
    )

    assert ref.record_digest == record.record_digest
    with pytest.raises(ValidationError):
        ref.record_id = "other-record"
    with pytest.raises(ValueError, match="exact record_ref"):
        assert_janus_story_product_record_ref_matches_v4(
            record=record,
            record_ref=JanusStoryProductRecordRefV4.model_validate(
                {**ref.model_dump(mode="json"), "listing_slug": "other-listing"}
            ),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("raw_13q", {"identity": "raw intake cannot become a V4 record"}),
        ("status", "accepted"),
        ("product_description", "caller supplied description"),
        ("thumbnail_url", "https://unverified.example/image.png"),
        ("thumbnail_content_binding_ref", {
            **_evidence_ref("ThumbnailContentBinding", "thumbnail-binding-v4-1"),
            "thumbnail_url": "https://unverified.example/image.png",
        }),
    ],
)
def test_v4_record_rejects_raw_or_unverified_product_material(
    field: str,
    value: object,
) -> None:
    data = _record()
    data[field] = value
    if field != "thumbnail_content_binding_ref":
        data["record_digest"] = janus_story_product_record_digest_v4(
            {key: item for key, item in data.items() if key != "record_digest"}
        )

    with pytest.raises(ValidationError):
        JanusStoryProductRecordV4.model_validate(data)


@pytest.mark.parametrize(
    "field",
    [
        "studio_intake_receipt_ref",
        "catalog_snapshot_ref",
        "thumbnail_content_binding_ref",
        "verified_source_material_receipt_ref",
    ],
)
def test_v4_record_rejects_evidence_scope_or_digest_mismatch(field: str) -> None:
    data = _record()
    evidence = deepcopy(data[field])
    evidence["listing_id"] = "listing-other"
    data[field] = evidence
    data["record_digest"] = janus_story_product_record_digest_v4(
        {key: item for key, item in data.items() if key != "record_digest"}
    )

    with pytest.raises(ValidationError, match="scope"):
        JanusStoryProductRecordV4.model_validate(data)


def test_evidence_refs_are_typed_and_their_digests_are_not_caller_claims() -> None:
    assert StudioIntakeReceiptRefV4.model_validate(
        _evidence_ref("StudioIntakeReceipt", "studio-intake-v4-1")
    ).evidence_id == "studio-intake-v4-1"
    assert CatalogSnapshotRefV4.model_validate(
        _evidence_ref("CatalogSnapshot", "catalog-v4-1")
    ).evidence_id == "catalog-v4-1"
    assert ThumbnailContentBindingRefV4.model_validate(
        _evidence_ref("ThumbnailContentBinding", "thumbnail-binding-v4-1")
    ).evidence_id == "thumbnail-binding-v4-1"
    assert VerifiedSourceMaterialReceiptRefV4.model_validate(
        _evidence_ref("VerifiedSourceMaterialReceipt", "source-material-v4-1")
    ).evidence_id == "source-material-v4-1"
