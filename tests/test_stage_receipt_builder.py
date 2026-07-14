"""Tests for StageReceiptBuilder — verifying terminal stage receipt construction."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiob_contracts.factory import (
    StageReceiptBuilder,
    TERMINAL_STAGE_STATUSES,
    sha256_digest,
    is_digest,
)


def test_builder_succeeded_valid_receipt():
    """StageReceiptBuilder.build_succeeded produces valid terminal receipt."""
    builder = StageReceiptBuilder(
        operation_id="op-1",
        stage_id="stage-1",
        planet="parzifal",
        node_id="parzifal.consolidate",
        producer_revision="r1",
        contract_version="v1",
    )

    output_digest = sha256_digest({"target": "profile"})
    receipt = builder.build_succeeded(
        output_digests=(output_digest,),
        input_digests=(sha256_digest({"input": "data"}),),
    )

    assert receipt.status == "succeeded"
    assert receipt.is_terminal
    assert receipt.is_success
    assert receipt.output_digests == (output_digest,)
    assert receipt.error is None
    assert receipt.completed_at is not None


def test_builder_succeeded_requires_output_digests():
    """build_succeeded fails if no output_digests provided."""
    builder = StageReceiptBuilder(
        operation_id="op-1",
        stage_id="stage-1",
        planet="test",
        node_id="test.node",
        producer_revision="r1",
        contract_version="v1",
    )

    with pytest.raises(ValueError, match="must produce at least one output digest"):
        builder.build_succeeded(output_digests=())


def test_builder_failed_valid_receipt():
    """StageReceiptBuilder.build_failed produces valid error receipt."""
    builder = StageReceiptBuilder(
        operation_id="op-1",
        stage_id="stage-1",
        planet="athena",
        node_id="athena.visual",
        producer_revision="r1",
        contract_version="v1",
    )

    receipt = builder.build_failed(
        error_code="TIMEOUT",
        error_message="Visual generation timed out after 60s",
        retryable=True,
        error_details="lambda execution exceeded 60000ms",
        input_digests=(sha256_digest({"request": "data"}),),
    )

    assert receipt.status == "failed"
    assert receipt.is_terminal
    assert not receipt.is_success
    assert receipt.error is not None
    assert receipt.error.code == "TIMEOUT"
    assert receipt.error.retryable is True
    assert receipt.output_digests == ()
    assert receipt.completed_at is not None


def test_builder_blocked_valid_receipt():
    """StageReceiptBuilder.build_blocked produces blocked/cancelled receipt."""
    builder = StageReceiptBuilder(
        operation_id="op-1",
        stage_id="stage-1",
        planet="hephaestus",
        node_id="hephaestus.render",
        producer_revision="r1",
        contract_version="v1",
    )

    receipt = builder.build_blocked(
        reason="Final render not approved by user",
        input_digests=(sha256_digest({"composition": "data"}),),
    )

    assert receipt.status == "cancelled"
    assert receipt.is_terminal
    assert not receipt.is_success
    assert receipt.error is not None
    assert receipt.error.code == "BLOCKED"
    assert receipt.error.retryable is False
    assert receipt.output_digests == ()
    assert receipt.completed_at is not None


def test_builder_all_terminal_statuses_allowed():
    """Verify builder produces only terminal status receipts."""
    builder = StageReceiptBuilder(
        operation_id="op", stage_id="s", planet="p", node_id="n",
        producer_revision="r", contract_version="v",
    )

    rec_succeed = builder.build_succeeded(output_digests=(sha256_digest({}),))
    rec_fail = builder.build_failed(error_code="E", error_message="e")
    rec_block = builder.build_blocked()

    for receipt in [rec_succeed, rec_fail, rec_block]:
        assert receipt.status in TERMINAL_STAGE_STATUSES
        assert receipt.is_terminal
        assert receipt.completed_at is not None


def test_builder_respects_custom_timestamps():
    """Builder uses provided started_at timestamp."""
    custom_start = "2026-07-14T10:00:00Z"
    builder = StageReceiptBuilder(
        operation_id="op", stage_id="s", planet="p", node_id="n",
        producer_revision="r", contract_version="v",
    )

    receipt = builder.build_succeeded(
        output_digests=(sha256_digest({}),),
        started_at=custom_start,
    )

    assert receipt.started_at == custom_start
    assert receipt.completed_at != custom_start  # completed_at is always now


def test_builder_with_cost_metadata():
    """Builder can include cost metadata (e.g., API spend)."""
    builder = StageReceiptBuilder(
        operation_id="op", stage_id="s", planet="p", node_id="n",
        producer_revision="r", contract_version="v",
    )

    cost = {"llm_tokens": 1000, "image_api_calls": 3, "usd": 0.15}
    receipt = builder.build_succeeded(
        output_digests=(sha256_digest({}),),
        cost=cost,
    )

    assert receipt.cost == cost


def test_builder_with_warnings():
    """Builder can include non-fatal warnings in receipt."""
    builder = StageReceiptBuilder(
        operation_id="op", stage_id="s", planet="p", node_id="n",
        producer_revision="r", contract_version="v",
    )

    warnings = ("fallback to lower quality", "retry attempt 2 of 3")
    receipt = builder.build_succeeded(
        output_digests=(sha256_digest({}),),
        warnings=warnings,
    )

    assert receipt.warnings == warnings


def test_builder_with_image_digest():
    """Builder can include image_digest for visual stages."""
    builder = StageReceiptBuilder(
        operation_id="op", stage_id="s", planet="athena", node_id="n",
        producer_revision="r", contract_version="v",
    )

    img_digest = sha256_digest({"image": "metadata"})
    receipt = builder.build_succeeded(
        output_digests=(sha256_digest({}),),
        image_digest=img_digest,
    )

    assert receipt.image_digest == img_digest


def test_builder_failed_requires_error_code():
    """build_failed always creates a structured error."""
    builder = StageReceiptBuilder(
        operation_id="op", stage_id="s", planet="p", node_id="n",
        producer_revision="r", contract_version="v",
    )

    receipt = builder.build_failed(
        error_code="CUSTOM_ERROR",
        error_message="Something went wrong",
    )

    assert receipt.error is not None
    assert receipt.error.code == "CUSTOM_ERROR"
    # Message is part of the high-level description, details is for extra info
    assert receipt.error.retryable is False


def test_builder_multiple_output_digests():
    """build_succeeded accepts multiple output digests (fan-out)."""
    builder = StageReceiptBuilder(
        operation_id="op", stage_id="s", planet="p", node_id="n",
        producer_revision="r", contract_version="v",
    )

    d1 = sha256_digest({"output": 1})
    d2 = sha256_digest({"output": 2})
    d3 = sha256_digest({"output": 3})

    receipt = builder.build_succeeded(output_digests=(d1, d2, d3))

    assert receipt.output_digests == (d1, d2, d3)
    assert len(receipt.output_digests) == 3
