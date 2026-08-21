import pytest

from hiob_contracts import (
    CreateElementLockRequestV1,
    ElementArtifactRefV1,
    ElementLockPackageV1,
)
from hiob_contracts.factory import sha256_digest
import hiob_contracts.element_lock_v3 as element_lock_v3


def _source() -> ElementArtifactRefV1:
    return ElementArtifactRefV1(
        artifact_id="asset-source-1",
        sha256=sha256_digest("source"),
        role="source",
    )


def _request() -> CreateElementLockRequestV1:
    return CreateElementLockRequestV1.build(
        operation_id="op-1",
        workspace_id="ws-1",
        run_id="run-1",
        subject_id="hero",
        identity_spec={"name": "Sora", "age_band": "30s", "wardrobe": "blue"},
        source_refs=(_source(),),
        paid_policy_digest=sha256_digest({"max_cost_usd": 2, "provider_retry": 0}),
    )


def test_request_is_url_free_and_digest_bound():
    request = _request()
    payload = request.model_dump(mode="json")
    assert "url" not in str(payload).lower()
    assert CreateElementLockRequestV1.model_validate(payload) == request


def test_request_rejects_digest_or_reference_drift():
    payload = _request().model_dump(mode="json")
    payload["subject_id"] = "other"
    with pytest.raises(ValueError, match="request_digest"):
        CreateElementLockRequestV1.model_validate(payload)

    with pytest.raises(ValueError, match="must not contain URLs"):
        CreateElementLockRequestV1.build(
            operation_id="op-url",
            workspace_id="ws-1",
            run_id="run-1",
            subject_id="hero",
            identity_spec={"portrait_url": "https://example.com/person.png"},
            paid_policy_digest=sha256_digest({"max_cost_usd": 2}),
        )

    for role in ("source", "character_sheet"):
        with pytest.raises(ValueError, match="opaque server id"):
            ElementArtifactRefV1(
                artifact_id="https://example.com/signed?token=secret",
                sha256=sha256_digest(role),
                role=role,
            )


@pytest.mark.parametrize(
    "artifact_id",
    (
        "HTTP://example.com/source.png",
        "https://example.com/source.png",
        "data:image/png;base64,abc",
        "file:/tmp/source.png",
    ),
)
def test_artifact_id_rejects_external_or_embedded_references(artifact_id: str):
    with pytest.raises(ValueError, match="opaque server id"):
        ElementArtifactRefV1(
            artifact_id=artifact_id,
            sha256=sha256_digest(artifact_id),
            role="source",
        )


def test_package_requires_review_artifact_and_human_approval():
    artifact = ElementArtifactRefV1(
        artifact_id="asset-sheet-1",
        sha256=sha256_digest("sheet"),
        role="character_sheet",
    )
    review = ElementLockPackageV1.build(
        lock_id="lock-1",
        version=1,
        operation_id="op-1",
        workspace_id="ws-1",
        run_id="run-1",
        subject_id="hero",
        status="review",
        character_sheet_ref=artifact,
        provider_receipt_digest=sha256_digest({"task_id": "provider-1"}),
    )
    ready = ElementLockPackageV1.build(
        **{
            **review.model_dump(mode="python"),
            "version": review.version + 1,
            "status": "ready",
            "approved_by": "founder",
            "lock_digest": None,
        }
    )
    assert ready.status == "ready"
    assert "url" not in str(ready.model_dump(mode="json")).lower()

    with pytest.raises(ValueError, match="approved_by"):
        ElementLockPackageV1.build(
            **{
                **review.model_dump(mode="python"),
                "version": review.version + 1,
                "status": "ready",
                "lock_digest": None,
            }
        )


def test_request_rejects_duplicate_and_non_source_refs() -> None:
    source = _source()
    with pytest.raises(ValueError, match="duplicate artifact_id"):
        CreateElementLockRequestV1.build(
            operation_id="op-duplicate",
            workspace_id="ws-1",
            run_id="run-1",
            subject_id="hero",
            identity_spec={"name": "Sora"},
            source_refs=(source, source),
            paid_policy_digest=sha256_digest("policy"),
        )
    wrong_role = ElementArtifactRefV1(
        artifact_id="sheet",
        sha256=sha256_digest("sheet"),
        role="character_sheet",
    )
    with pytest.raises(ValueError, match="role=source"):
        CreateElementLockRequestV1.build(
            operation_id="op-role",
            workspace_id="ws-1",
            run_id="run-1",
            subject_id="hero",
            identity_spec={"name": "Sora"},
            source_refs=(wrong_role,),
            paid_policy_digest=sha256_digest("policy"),
        )
    assert element_lock_v3._contains_url([{"portrait": "https://example.com"}])


def test_package_reports_each_required_review_and_ready_binding() -> None:
    source = _source()
    sheet = ElementArtifactRefV1(
        artifact_id="sheet",
        sha256=sha256_digest("sheet"),
        role="character_sheet",
    )
    base = {
        "lock_id": "lock-1",
        "version": 1,
        "operation_id": "op-1",
        "workspace_id": "ws-1",
        "run_id": "run-1",
        "subject_id": "hero",
        "status": "review",
        "provider_receipt_digest": sha256_digest("receipt"),
    }
    with pytest.raises(ValueError, match="character_sheet_ref is required"):
        ElementLockPackageV1.build(**base)
    with pytest.raises(ValueError, match="role=character_sheet"):
        ElementLockPackageV1.build(**base, character_sheet_ref=source)
    with pytest.raises(ValueError, match="provider_receipt_digest is required"):
        ElementLockPackageV1.build(
            **{**base, "provider_receipt_digest": None},
            character_sheet_ref=sheet,
        )
    with pytest.raises(ValueError, match="new version"):
        ElementLockPackageV1.build(
            **{
                **base,
                "status": "ready",
                "approved_by": "founder",
            },
            character_sheet_ref=sheet,
        )

    ready = ElementLockPackageV1.build(
        **{
            **base,
            "version": 2,
            "status": "ready",
            "approved_by": "founder",
        },
        character_sheet_ref=sheet,
    )
    with pytest.raises(ValueError, match="lock_digest"):
        ready.model_copy(
            update={"lock_digest": sha256_digest("wrong")}
        )._check()
