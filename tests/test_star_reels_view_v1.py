from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiob_contracts import StarReelsViewV1


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
            "receipts": {},
            "provider_call": "none",
            "error": None,
        }
    )

    assert value.section == "ScriptReview"
    assert value.budget.model_dump() == _budget()


@pytest.mark.parametrize(
    ("section", "status"),
    [
        ("RunStatus", "new"),
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
    StarReelsViewV1.model_validate(
        {
            "contract_version": "StarReelsView.v1",
            "section": section,
            "status": status,
            "revision": 1,
            "stage_output": {"revision": status} if is_review else None,
            "budget": _budget(),
            "review_digest": DIGEST if is_review else None,
            "receipts": (
                {"factory": {"contract_version": "test"}}
                if status in {"pending", "rendering", "ready", "failed"}
                else {}
            ),
            "provider_call": "unknown" if is_failed else "none",
            "error": "FACTORY_FAILED" if is_failed else None,
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
        "receipts": {},
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
        "receipts": {"factory": {"contract_version": "test"}},
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
