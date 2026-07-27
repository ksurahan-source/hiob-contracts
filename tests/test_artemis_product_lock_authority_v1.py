from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from hiob_contracts.artemis_product_lock_v1 import (
    ArtemisApprovalReceiptV1,
    ArtemisCompileRequestV1,
    ArtemisCompileResultV1,
    ArtemisSealRequestV1,
    JanusProductObservationV1,
    JanusProductObservationsV1,
    ProductElementLockDraftV1,
    ProductElementLockV1,
)
from hiob_contracts.factory import sha256_digest


def _observations(**overrides):
    values = {
        "workspace_id": "ws-1",
        "run_id": "run-1",
        "brand_slug": "viewok",
        "listing_slug": "nano-mask",
        "product_id": "product-1",
        "product_name": "Nano Mask",
        "product_image_artifact_id": "asset/product-1",
        "product_image_sha256": sha256_digest("product-image"),
        "observations": [
            {
                "observation_id": "obs-1",
                "kind": "product_fact",
                "text": "한 장씩 개별 포장",
                "evidence_artifact_id": "asset/detail-1",
                "evidence_sha256": sha256_digest("detail-crop"),
                "provenance": {
                    "source_record_id": "record/detail-1",
                    "quote": "한 장씩 개별 포장",
                },
            }
        ],
    }
    values.update(overrides)
    return JanusProductObservationsV1.build(**values)


def _compile_request():
    return ArtemisCompileRequestV1.build(observations=_observations())


def _draft(**overrides):
    request = _compile_request()
    source = request.observations.observations[0]
    values = {
        "workspace_id": "ws-1",
        "run_id": "run-1",
        "brand_slug": "viewok",
        "listing_slug": "nano-mask",
        "product_id": "product-1",
        "product_name": "Nano Mask",
        "product_image_artifact_id": "asset/product-1",
        "product_image_sha256": sha256_digest("product-image"),
        "claims": [
            {
                "claim_id": "claim-1",
                "text": source.text,
                "kind": source.kind,
                "source_observation_ids": [source.observation_id],
                "evidence_artifact_id": source.evidence_artifact_id,
                "evidence_sha256": source.evidence_sha256,
                "provenance": source.provenance.model_dump(mode="json"),
            }
        ],
        "forbidden_claims": ["의학적 치료 효과"],
        "source_observations_digest": request.observations.observations_digest,
        "compile_request_digest": request.request_digest,
    }
    values.update(overrides)
    return ProductElementLockDraftV1.build(**values)


class _Resolver:
    def __init__(self, current: bool) -> None:
        self.current = current

    def is_current_approval(self, **_values) -> bool:
        return self.current


def _receipt(draft=None):
    draft = draft or _draft()
    return ArtemisApprovalReceiptV1.build(
        receipt_id="receipt-1",
        draft=draft,
        approver_account_id="user-1",
        state_revision=1,
    )


@pytest.mark.parametrize(
    "bad_id",
    [
        "https://host/path",
        "s3://bucket/key",
        "ftp://host/path",
        "//host/path",
        "javascript:alert(1)",
    ],
)
def test_all_technical_ids_use_one_opaque_allowlist(bad_id: str) -> None:
    with pytest.raises(ValidationError, match="opaque"):
        JanusProductObservationV1(
            observation_id=bad_id,
            kind="product_fact",
            text="fact",
            evidence_artifact_id="asset-1",
            evidence_sha256=sha256_digest("asset"),
            provenance={
                "source_record_id": "record-1",
                "quote": "fact",
            },
        )


def test_builders_hash_normalized_content() -> None:
    observations = _observations(product_name="  Nano Mask  ")

    assert observations.product_name == "Nano Mask"
    assert JanusProductObservationsV1.model_validate(
        observations.model_dump(mode="json")
    ) == observations


def test_semantic_duplicate_observations_are_rejected() -> None:
    first = _observations().observations[0].model_dump(mode="json")
    duplicate = {**first, "observation_id": "obs-2"}

    with pytest.raises(ValidationError, match="duplicate observation content"):
        _observations(observations=[first, duplicate])


def test_compile_result_binds_request_and_draft() -> None:
    request = _compile_request()
    draft = _draft()
    result = ArtemisCompileResultV1.compiled(request, draft)

    assert result.request_digest == request.request_digest
    assert result.draft is not None
    assert result.draft.compile_request_digest == request.request_digest

    wrong_request = ArtemisCompileRequestV1.build(
        observations=_observations(run_id="run-2")
    )
    with pytest.raises(ValueError, match="grounded|compile_request_digest"):
        ArtemisCompileResultV1.compiled(wrong_request, draft)


def test_compile_result_cross_checks_actual_observation_atoms() -> None:
    request = _compile_request()
    draft = _draft()
    claim = draft.claims[0].model_dump(mode="json")
    claim["source_observation_ids"] = ["never-observed"]
    forged = ProductElementLockDraftV1.build(
        **{
            **draft.model_dump(
                mode="python",
                exclude={"contract_version", "draft_digest", "claims"},
            ),
            "claims": [claim],
        }
    )

    with pytest.raises(ValueError, match="grounded"):
        ArtemisCompileResultV1.compiled(request, forged)


def test_approval_receipt_requires_current_durable_authority() -> None:
    draft = _draft()
    receipt = _receipt(draft)

    assert receipt.structurally_binds(draft)
    assert receipt.authorizes(draft, resolver=_Resolver(True))
    assert not receipt.authorizes(draft, resolver=_Resolver(False))

    forged = receipt.model_copy(update={"approver_account_id": "forged-user"})
    assert not forged.authorizes(draft, resolver=_Resolver(True))


def test_seal_request_carries_receipt_not_self_attested_approver() -> None:
    draft = _draft()
    receipt = _receipt(draft)
    request = ArtemisSealRequestV1.build(
        draft=draft,
        approval_receipt=receipt,
    )
    payload = request.model_dump(mode="json")

    assert "approved_by" not in payload
    assert payload["approval_receipt"]["receipt_id"] == "receipt-1"
    assert request.authorizes(resolver=_Resolver(True))
    assert not request.authorizes(resolver=_Resolver(False))


def test_lock_reconstructs_the_exact_approved_draft() -> None:
    request = ArtemisSealRequestV1.build(
        draft=_draft(),
        approval_receipt=_receipt(),
    )
    lock = ProductElementLockV1.from_verified(
        request,
        resolver=_Resolver(True),
    )
    payload = lock.model_dump(mode="json")
    payload["claims"][0]["text"] = "forged claim"
    payload["lock_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "lock_digest"}
    )

    with pytest.raises(ValidationError, match="draft_digest"):
        ProductElementLockV1.model_validate(payload)


def test_semantic_duplicate_claims_and_forbidden_claims_are_rejected() -> None:
    draft = _draft()
    first_claim = draft.claims[0].model_dump(mode="json")

    with pytest.raises(ValidationError, match="duplicate claim content"):
        ProductElementLockDraftV1.build(
            **{
                **draft.model_dump(
                    mode="python",
                    exclude={"contract_version", "draft_digest"},
                ),
                "claims": [
                    first_claim,
                    {**deepcopy(first_claim), "claim_id": "claim-2"},
                ],
            }
        )

    with pytest.raises(ValidationError, match="duplicate forbidden_claims"):
        ProductElementLockDraftV1.build(
            **{
                **draft.model_dump(
                    mode="python",
                    exclude={"contract_version", "draft_digest"},
                ),
                "forbidden_claims": ["치료 효과", "치료 효과"],
            }
        )
