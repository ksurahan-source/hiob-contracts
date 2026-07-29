from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiob_contracts import (
    StarReelsViewV1,
    canonical_contract_digest_v1,
    derive_reels_factory_failure_receipt_digest_v1,
    derive_reels_factory_progress_receipt_digest_v1,
)


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
        "provider_call": "none",
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
            "provider_call": "none",
            "error": None,
        }
    )

    assert value.section == "ScriptReview"
    assert value.budget.model_dump() == _budget()


@pytest.mark.parametrize(
    ("section", "status"),
    [
        ("LockGate", "missing"),
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
    is_failed = status == "failed"
    is_lock_error = section == "LockGate" and status != "ready"
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
            "stage_output": {"revision": status} if is_review else None,
            "budget": _budget(),
            "review_digest": DIGEST if is_review else None,
            "receipts": {
                "factory": factory_receipt,
                "script_approval": None,
                "plan_approval": None,
            },
            "provider_call": "unknown" if is_failed else "none",
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
