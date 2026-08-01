from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    ProductElementLockDraftV1,
    StarReelsViewV1,
    StarReelsViewV2,
    canonical_contract_digest_v1,
    derive_star_product_lock_review_digest_v1,
    derive_reels_factory_failure_receipt_digest_v1,
    derive_reels_factory_progress_receipt_digest_v1,
)
from hiob_contracts.factory import sha256_digest


DIGEST = "sha256:" + "a" * 64


def _budget() -> dict[str, int]:
    return {
        "script": 1,
        "image": 1,
        "voice": 1,
        "render": 1,
        "retries": 0,
        "fallbacks": 0,
        "character_lock": 0,
    }


def _product_draft() -> dict:
    return ProductElementLockDraftV1.build(
        workspace_id="00000000-0000-4000-8000-000000000001",
        run_id="00000000-0000-4000-8000-000000000002",
        brand_slug="viewok",
        listing_slug="02-vok-original-40-2p",
        product_id="02-vok-original-40-2p",
        product_name="뷰오케이 아이세이프 김서림방지 물안경",
        product_image_artifact_id="asset-product-1",
        product_image_storage_key="products/viewok/hero.png",
        product_image_sha256=sha256_digest("product-image"),
        claims=[
            {
                "claim_id": "claim-1",
                "text": "김서림 방지 물안경",
                "kind": "product_fact",
                "source_observation_ids": ["observation-1"],
                "evidence_artifact_id": "run/catalog-facts/name",
                "evidence_sha256": sha256_digest("catalog-name"),
                "provenance": {
                    "source_record_id": "run/catalog-facts/name",
                    "quote": "김서림 방지 물안경",
                },
            }
        ],
        forbidden_claims=["치료 효과"],
        source_observations_digest=sha256_digest("observations"),
        compile_request_digest=sha256_digest("compile-request"),
    ).model_dump(mode="json")


def _product_review_digest() -> str:
    return derive_star_product_lock_review_digest_v1(
        ProductElementLockDraftV1.model_validate(_product_draft())
    )


def _progress() -> dict:
    body = {
        "contract_version": "ReelsFactoryProgressReceipt.v1",
        "run_id": "00000000-0000-4000-8000-000000000002",
        "idempotency_key": "star.reels.factory:one",
        "revision": 1,
        "stage": "render",
        "provider_attempts": {
            "script": 1,
            "image": 0,
            "voice": 0,
            "render": 0,
        },
    }
    return {
        **body,
        "receipt_digest": derive_reels_factory_progress_receipt_digest_v1(
            body
        ),
    }


def _failure() -> dict:
    body = {
        "contract_version": "ReelsFactoryFailureReceipt.v1",
        "run_id": "00000000-0000-4000-8000-000000000002",
        "idempotency_key": "star.reels.factory:one",
        "revision": 1,
        "stage": "authority",
        "code": "CHARACTER_LOCK_REQUIRED",
        "provider_call": "unknown",
        "provider_attempts": {
            "script": 0,
            "image": 0,
            "voice": 0,
            "render": 0,
        },
    }
    return {
        **body,
        "receipt_digest": derive_reels_factory_failure_receipt_digest_v1(
            body
        ),
    }


def _v2_budget() -> dict:
    return {
        "script": 1,
        "image": 2,
        "video": 2,
        "voice": 2,
        "render": 1,
        "retries": 0,
        "fallbacks": 0,
        "character_lock": 0,
        "all_beat_count": 2,
        "paid_budget_authority_digest": DIGEST,
        "beat_artifact_set_receipt": None,
    }


def _v2_factory_receipt(kind: str) -> dict:
    attempts = {
        "script": 1,
        "image": 1,
        "video": 1,
        "voice": 0,
        "render": 0,
    }
    if kind == "progress":
        body = {
            "contract_version": "ReelsFactoryProgressReceipt.v2",
            "run_id": "00000000-0000-4000-8000-000000000002",
            "idempotency_key": "star.reels.factory:one",
            "revision": 2,
            "stage": "video",
            "provider_attempts": attempts,
        }
        return {
            **body,
            "receipt_digest": derive_reels_factory_progress_receipt_digest_v1(
                body
            ),
        }
    body = {
        "contract_version": "ReelsFactoryFailureReceipt.v2",
        "run_id": "00000000-0000-4000-8000-000000000002",
        "idempotency_key": "star.reels.factory:one",
        "revision": 2,
        "stage": "video",
        "code": "VIDEO_PROVIDER_TERMINAL",
        "provider_call": "unknown",
        "provider_attempts": attempts,
    }
    return {
        **body,
        "receipt_digest": derive_reels_factory_failure_receipt_digest_v1(body),
    }


@pytest.mark.parametrize(
    ("kind", "status", "provider_call", "error"),
    [
        ("progress", "rendering", "confirmed", None),
        ("failure", "failed", "unknown", "VIDEO_PROVIDER_TERMINAL"),
    ],
)
def test_v2_view_preserves_video_progress_and_failure(
    kind: str,
    status: str,
    provider_call: str,
    error: str | None,
) -> None:
    value = StarReelsViewV2.model_validate(
        {
            "contract_version": "StarReelsView.v2",
            "section": "RunStatus",
            "status": status,
            "revision": 2,
            "stage_output": None,
            "budget": _v2_budget(),
            "review_digest": None,
            "receipts": {
                "factory": _v2_factory_receipt(kind),
                "script_approval": None,
                "plan_approval": None,
            },
            "provider_call": provider_call,
            "error": error,
        }
    )

    assert value.receipts.factory.provider_attempts.video == 1

    tampered = _v2_factory_receipt(kind)
    tampered["provider_attempts"]["video"] = 2
    with pytest.raises(ValidationError, match="receipt_digest"):
        StarReelsViewV2.model_validate(
            {
                **value.model_dump(mode="json"),
                "receipts": {
                    "factory": tampered,
                    "script_approval": None,
                    "plan_approval": None,
                },
            }
        )
def _ready() -> dict:
    render_body = {
        "contract_version": "AtroposRenderReceipt.v1",
        "workspace_id": "00000000-0000-4000-8000-000000000001",
        "run_id": "00000000-0000-4000-8000-000000000002",
        "snapshot_digest": DIGEST,
        "output_url": "https://cdn.example/reel.mp4",
        "artifact": {
            "storage_key": "runs/reel.mp4",
            "artifact_sha256": DIGEST,
            "mime": "video/mp4",
            "bytes_len": 42,
        },
    }
    render = {
        **render_body,
        "receipt_digest": canonical_contract_digest_v1(render_body),
    }
    body = {
        "contract_version": "ReelsFactoryReceipt.v1",
        "workspace_id": "00000000-0000-4000-8000-000000000001",
        "run_id": "00000000-0000-4000-8000-000000000002",
        "factory_revision": 1,
        "idempotency_key": "star.reels.factory:one",
        "request_digest": DIGEST,
        "script_revision_digest": DIGEST,
        "beat_plan_revision_digest": DIGEST,
        "athena_receipt_digest": DIGEST,
        "voice_review": {},
        "media_receipt_digests": [DIGEST],
        "audio_receipt_digests": [DIGEST],
        "sfx_receipt_digest": DIGEST,
        "snapshot": {"snapshot_digest": DIGEST},
        "render_receipt": render,
        "provider_attempts": {
            "script": 1,
            "image": 1,
            "voice": 1,
            "render": 1,
        },
        "provider_replays": {
            "script": 0,
            "image": 0,
            "voice": 0,
            "render": 0,
        },
        "fallback_calls": 0,
    }
    return {**body, "receipt_digest": canonical_contract_digest_v1(body)}


def test_review_view_is_one_non_authoritative_projection() -> None:
    value = StarReelsViewV1.model_validate(
        {
            "contract_version": "StarReelsView.v1",
            "section": "ScriptReview",
            "status": "awaiting_script_approval",
            "revision": 2,
            "stage_output": {"script_revision": {"revision_digest": DIGEST}},
            "budget": _budget(),
            "review_digest": DIGEST,
            "receipts": {
                "factory": None,
                "script_approval": None,
                "plan_approval": None,
            },
            "provider_call": "confirmed",
            "error": None,
        }
    )

    assert value.section == "ScriptReview"
    assert value.budget.model_dump() == _budget()


def test_review_can_report_the_confirmed_script_attempt() -> None:
    value = StarReelsViewV1.model_validate(
        {
            "contract_version": "StarReelsView.v1",
            "section": "PlanReview",
            "status": "awaiting_plan_approval",
            "revision": 3,
            "stage_output": {"plan_revision": {"revision_digest": DIGEST}},
            "budget": _budget(),
            "review_digest": DIGEST,
            "receipts": {
                "factory": None,
                "script_approval": None,
                "plan_approval": None,
            },
            "provider_call": "confirmed",
            "error": None,
        }
    )

    assert value.provider_call == "confirmed"


def test_lock_gate_can_carry_one_no_provider_product_review() -> None:
    value = StarReelsViewV1.model_validate(
        {
            "contract_version": "StarReelsView.v1",
            "section": "LockGate",
            "status": "awaiting_product_approval",
            "revision": 0,
            "stage_output": _product_draft(),
            "budget": _budget(),
            "review_digest": _product_review_digest(),
            "receipts": {
                "factory": None,
                "script_approval": None,
                "plan_approval": None,
            },
            "provider_call": "none",
            "error": None,
        }
    )

    assert value.status == "awaiting_product_approval"
    assert value.stage_output.contract_version == (
        "ProductElementLockDraft.v1"
    )
    with pytest.raises(ValidationError):
        value.stage_output.claims[0].text = "mutated"


@pytest.mark.parametrize(
    "change",
    [
        {"stage_output": None},
        {"review_digest": None},
        {"provider_call": "confirmed"},
        {"stage_output": {"contract_version": "ProductElementLockDraft.v1"}},
    ],
)
def test_product_review_rejects_incomplete_or_provider_work(
    change: dict,
) -> None:
    value = {
        "contract_version": "StarReelsView.v1",
        "section": "LockGate",
        "status": "awaiting_product_approval",
        "revision": 0,
        "stage_output": _product_draft(),
        "budget": _budget(),
        "review_digest": _product_review_digest(),
        "receipts": {
            "factory": None,
            "script_approval": None,
            "plan_approval": None,
        },
        "provider_call": "none",
        "error": None,
    }

    with pytest.raises(ValidationError):
        StarReelsViewV1.model_validate({**value, **change})
    with pytest.raises(ValidationError):
        StarReelsViewV1.model_validate(
            {**value, "review_digest": DIGEST}
        )


@pytest.mark.parametrize(
    ("section", "status"),
    [
        ("LockGate", "missing"),
        ("LockGate", "awaiting_product_approval"),
        ("LockGate", "revoked"),
        ("LockGate", "digest_drift"),
        ("LockGate", "ready"),
        ("ScriptReview", "awaiting_script_approval"),
        ("PlanReview", "awaiting_plan_approval"),
        ("RunStatus", "pending"),
        ("RunStatus", "rendering"),
        ("RunStatus", "ready"),
        ("RunStatus", "failed"),
    ],
)
def test_view_supports_every_refreshable_factory_state(
    section: str,
    status: str,
) -> None:
    is_review = status.startswith("awaiting_")
    is_product_review = status == "awaiting_product_approval"
    is_failed = status == "failed"
    is_lock_error = section == "LockGate" and status in {
        "missing",
        "revoked",
        "digest_drift",
    }
    factory_receipt = (
        _progress()
        if status in {"pending", "rendering"}
        else _ready()
        if section == "RunStatus" and status == "ready"
        else _failure()
        if is_failed
        else None
    )
    StarReelsViewV1.model_validate(
        {
            "contract_version": "StarReelsView.v1",
            "section": section,
            "status": status,
            "revision": 1,
            "stage_output": (
                _product_draft()
                if is_product_review
                else {"revision": status}
                if is_review
                else None
            ),
            "budget": _budget(),
            "review_digest": (
                _product_review_digest()
                if is_product_review
                else DIGEST
                if is_review
                else None
            ),
            "receipts": {
                "factory": factory_receipt,
                "script_approval": None,
                "plan_approval": None,
            },
            "provider_call": (
                "unknown"
                if is_failed
                else "confirmed"
                if status in {"pending", "rendering"}
                or (is_review and not is_product_review)
                or (section == "RunStatus" and status == "ready")
                else "none"
            ),
            "error": (
                "FACTORY_FAILED"
                if is_failed
                else status.upper()
                if is_lock_error
                else None
            ),
        }
    )


def test_review_requires_exact_budget_and_review_digest() -> None:
    base = {
        "contract_version": "StarReelsView.v1",
        "section": "PlanReview",
        "status": "awaiting_plan_approval",
        "revision": 3,
        "stage_output": {"plan_revision": {"revision_digest": DIGEST}},
        "budget": _budget(),
        "review_digest": DIGEST,
        "receipts": {
            "factory": None,
            "script_approval": None,
            "plan_approval": None,
        },
        "provider_call": "none",
        "error": None,
    }

    with pytest.raises(ValidationError):
        StarReelsViewV1.model_validate(
            {**base, "budget": {**_budget(), "image": 2}}
        )
    with pytest.raises(ValidationError):
        StarReelsViewV1.model_validate({**base, "review_digest": None})


def test_failed_view_requires_error_and_non_failed_view_forbids_it() -> None:
    base = {
        "contract_version": "StarReelsView.v1",
        "section": "RunStatus",
        "status": "failed",
        "revision": 4,
        "stage_output": None,
        "budget": _budget(),
        "review_digest": None,
        "receipts": {
            "factory": _failure(),
            "script_approval": None,
            "plan_approval": None,
        },
        "provider_call": "unknown",
        "error": None,
    }

    with pytest.raises(ValidationError):
        StarReelsViewV1.model_validate(base)
    with pytest.raises(ValidationError):
        StarReelsViewV1.model_validate(
            {
                **base,
                "status": "ready",
                "provider_call": "none",
                "error": "STALE_ERROR",
            }
        )


def test_pending_rejects_terminal_receipt_and_ready_requires_mp4_url() -> None:
    base = {
        "contract_version": "StarReelsView.v1",
        "section": "RunStatus",
        "status": "pending",
        "revision": 1,
        "stage_output": None,
        "budget": _budget(),
        "review_digest": None,
        "receipts": {
            "factory": _failure(),
            "script_approval": None,
            "plan_approval": None,
        },
        "provider_call": "none",
        "error": None,
    }
    with pytest.raises(ValidationError):
        StarReelsViewV1.model_validate(base)

    ready = _ready()
    ready["render_receipt"] = {
        **ready["render_receipt"],
        "output_url": "",
    }
    with pytest.raises(ValidationError):
        StarReelsViewV1.model_validate(
            {
                **base,
                "status": "ready",
                "receipts": {
                    "factory": ready,
                    "script_approval": None,
                    "plan_approval": None,
                },
            }
        )


@pytest.mark.parametrize(
    ("status", "receipt", "provider_call"),
    [
        ("pending", _progress(), "none"),
        ("ready", _ready(), "none"),
        ("failed", _failure(), "confirmed"),
    ],
)
def test_provider_call_must_match_typed_receipt_ledger(
    status: str,
    receipt: dict,
    provider_call: str,
) -> None:
    with pytest.raises(ValidationError):
        StarReelsViewV1.model_validate(
            {
                "contract_version": "StarReelsView.v1",
                "section": "RunStatus",
                "status": status,
                "revision": 1,
                "stage_output": None,
                "budget": _budget(),
                "review_digest": None,
                "receipts": {
                    "factory": receipt,
                    "script_approval": None,
                    "plan_approval": None,
                },
                "provider_call": provider_call,
                "error": "FACTORY_FAILED" if status == "failed" else None,
            }
        )
