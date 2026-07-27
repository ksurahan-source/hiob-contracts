from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiob_contracts.artemis_product_lock_v1 import (
    ArtemisCompileRequestV1,
    ArtemisCompileResultV1,
    ArtemisSealRequestV1,
    ArtemisSealResultV1,
    JanusProductObservationsV1,
    ProductElementLockDraftV1,
    ProductElementLockV1,
)
from hiob_contracts.factory import sha256_digest


def _observations() -> JanusProductObservationsV1:
    return JanusProductObservationsV1.build(
        workspace_id="ws-1",
        run_id="run-1",
        brand_slug="viewok",
        listing_slug="nano-mask",
        product_id="product-1",
        product_name="Nano Mask",
        product_image_artifact_id="asset-product-1",
        product_image_sha256=sha256_digest("product-image"),
        observations=[
            {
                "observation_id": "obs-1",
                "kind": "product_fact",
                "text": "한 장씩 개별 포장",
                "evidence_artifact_id": "asset-detail-1",
                "evidence_sha256": sha256_digest("detail-crop"),
                "provenance": {
                    "source_record_id": "detail-page-1",
                    "quote": "한 장씩 개별 포장",
                },
            }
        ],
    )


def _draft() -> ProductElementLockDraftV1:
    observations = _observations()
    return ProductElementLockDraftV1.build(
        workspace_id=observations.workspace_id,
        run_id=observations.run_id,
        brand_slug=observations.brand_slug,
        listing_slug=observations.listing_slug,
        product_id=observations.product_id,
        product_name=observations.product_name,
        product_image_artifact_id=observations.product_image_artifact_id,
        product_image_sha256=observations.product_image_sha256,
        claims=[
            {
                "claim_id": "claim-1",
                "text": "한 장씩 개별 포장",
                "kind": "product_fact",
                "source_observation_ids": ["obs-1"],
                "evidence_artifact_id": "asset-detail-1",
                "evidence_sha256": sha256_digest("detail-crop"),
                "provenance": {
                    "source_record_id": "detail-page-1",
                    "quote": "한 장씩 개별 포장",
                },
            }
        ],
        forbidden_claims=["의학적 치료 효과"],
        source_observations_digest=observations.observations_digest,
    )


def _seal_request() -> ArtemisSealRequestV1:
    return ArtemisSealRequestV1.build(
        workspace_id="ws-1",
        run_id="run-1",
        listing_slug="nano-mask",
        draft=_draft(),
        approved_by="user-1",
    )


def test_janus_owns_observations_not_product_claims() -> None:
    observations = _observations()

    assert observations.contract_version == "JanusProductObservations.v1"
    assert observations.observations[0].observation_id == "obs-1"
    assert "claims" not in observations.model_dump(mode="json")

    with pytest.raises(ValidationError, match="claims"):
        JanusProductObservationsV1.build(
            **observations.model_dump(mode="python"),
            claims=[{"text": "Janus must not approve claims"}],
        )


def test_observations_are_url_free_frozen_and_digest_bound() -> None:
    observations = _observations()
    payload = observations.model_dump(mode="json")

    assert "url" not in str(payload).lower()
    assert JanusProductObservationsV1.model_validate(payload) == observations

    payload["product_name"] = "drifted"
    with pytest.raises(ValidationError, match="observations_digest"):
        JanusProductObservationsV1.model_validate(payload)

    with pytest.raises(ValidationError, match="URL"):
        JanusProductObservationsV1.build(
            **{
                **_observations().model_dump(mode="python"),
                "product_image_artifact_id": "https://signed.example/product.png",
                "observations_digest": None,
            }
        )

    with pytest.raises(ValidationError):
        observations.product_name = "mutated"  # type: ignore[misc]


def test_compile_request_binds_exact_observations() -> None:
    request = ArtemisCompileRequestV1.build(observations=_observations())
    payload = request.model_dump(mode="json")

    assert request.contract_version == "ArtemisCompileRequest.v1"
    assert ArtemisCompileRequestV1.model_validate(payload) == request

    payload["observations"]["product_name"] = "drifted"
    with pytest.raises(
        ValidationError,
        match="observations_digest|request_digest",
    ):
        ArtemisCompileRequestV1.model_validate(payload)


def test_draft_requires_grounded_artemis_claim() -> None:
    draft = _draft()

    assert draft.contract_version == "ProductElementLockDraft.v1"
    assert draft.claims[0].source_observation_ids == ("obs-1",)
    assert draft.claims[0].evidence_artifact_id == "asset-detail-1"

    payload = draft.model_dump(mode="python")
    payload["claims"] = []
    payload.pop("draft_digest")
    with pytest.raises(ValidationError, match="at least 1"):
        ProductElementLockDraftV1.build(**payload)

    payload = draft.model_dump(mode="python")
    payload["claims"][0]["source_observation_ids"] = []
    payload.pop("draft_digest")
    with pytest.raises(ValidationError, match="at least 1"):
        ProductElementLockDraftV1.build(**payload)


def test_compile_result_has_exactly_one_terminal_shape() -> None:
    compiled = ArtemisCompileResultV1.compiled(_draft())
    blocked = ArtemisCompileResultV1.blocked("PRODUCT_LOCK_INCOMPLETE")

    assert compiled.status == "compiled"
    assert compiled.draft is not None
    assert compiled.error_code is None
    assert blocked.status == "blocked"
    assert blocked.draft is None
    assert blocked.error_code == "PRODUCT_LOCK_INCOMPLETE"

    with pytest.raises(ValidationError):
        ArtemisCompileResultV1(
            contract_version="ArtemisCompileResult.v1",
            status="blocked",
            draft=_draft(),
            error_code="PRODUCT_LOCK_INCOMPLETE",
        )


def test_seal_request_binds_scope_draft_and_approver() -> None:
    request = _seal_request()
    payload = request.model_dump(mode="json")

    assert request.approval_digest.startswith("sha256:")
    assert ArtemisSealRequestV1.model_validate(payload) == request

    payload["approved_by"] = "other-user"
    with pytest.raises(ValidationError, match="approval_digest"):
        ArtemisSealRequestV1.model_validate(payload)

    with pytest.raises(ValidationError, match="scope"):
        ArtemisSealRequestV1.build(
            workspace_id="other-workspace",
            run_id="run-1",
            listing_slug="nano-mask",
            draft=_draft(),
            approved_by="user-1",
        )


def test_sealed_lock_is_exact_approved_draft() -> None:
    request = _seal_request()
    lock = ProductElementLockV1.from_approved(request)
    payload = lock.model_dump(mode="json")

    assert lock.contract_version == "ProductElementLock.v1"
    assert lock.draft_digest == request.draft.draft_digest
    assert lock.approval_digest == request.approval_digest
    assert "url" not in str(payload).lower()
    assert ProductElementLockV1.model_validate(payload) == lock

    payload["product_name"] = "drifted"
    with pytest.raises(ValidationError, match="lock_digest"):
        ProductElementLockV1.model_validate(payload)


def test_seal_result_has_exactly_one_terminal_shape() -> None:
    lock = ProductElementLockV1.from_approved(_seal_request())
    sealed = ArtemisSealResultV1.sealed(lock)
    blocked = ArtemisSealResultV1.blocked("APPROVAL_INVALID")

    assert sealed.status == "sealed"
    assert sealed.lock is not None
    assert sealed.error_code is None
    assert blocked.status == "blocked"
    assert blocked.lock is None
    assert blocked.error_code == "APPROVAL_INVALID"

    with pytest.raises(ValidationError):
        ArtemisSealResultV1(
            contract_version="ArtemisSealResult.v1",
            status="sealed",
            lock=None,
            error_code=None,
        )
