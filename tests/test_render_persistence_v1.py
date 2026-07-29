from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiob_contracts import RenderPersistenceV1


def test_ready_requires_durable_output_url() -> None:
    with pytest.raises(ValidationError, match="ready requires output_url"):
        RenderPersistenceV1(
            contract_version="RenderPersistence.v1",
            status="ready",
            output_url=None,
        )


def test_only_canonical_persistence_states_are_accepted() -> None:
    with pytest.raises(ValidationError):
        RenderPersistenceV1(
            contract_version="RenderPersistence.v1",
            status="completed",
            output_url="https://cdn.example/reel.mp4",
        )


@pytest.mark.parametrize("status", ["pending", "rendering", "failed"])
def test_non_ready_states_cannot_claim_an_output(status: str) -> None:
    with pytest.raises(ValidationError, match="only ready may set output_url"):
        RenderPersistenceV1(
            contract_version="RenderPersistence.v1",
            status=status,
            output_url="https://cdn.example/reel.mp4",
        )


def test_ready_with_https_output_url_is_success() -> None:
    value = RenderPersistenceV1(
        contract_version="RenderPersistence.v1",
        status="ready",
        output_url="https://cdn.example/reel.mp4",
    )

    assert value.is_success is True
